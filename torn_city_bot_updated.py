import os
import discord
import requests
from discord.ext import commands, tasks
from discord import app_commands, ui
import threading
import http.server
import socketserver
import asyncio

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
TORN_API_KEY = "etqdem2Fp1VlhfGB"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

accepted_users = set()
last_prices = {}  # stock_id -> price
stock_channels = {}  # guild_id -> channel_id
stock_tasks = {}  # guild_id -> asyncio.Task
stock_messages = {}  # guild_id -> {stock_id: message_id}

# ------------------ UI ------------------

class ToSView(ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @ui.button(label="I AGREE", style=discord.ButtonStyle.success)
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        accepted_users.add(self.user_id)
        await interaction.response.send_message("✅ Terms accepted!", ephemeral=True)

        intro = (
            "👋 **Thanks for using Torn Assistant!**\n"
            "This bot has two key features:\n"
            "1. **Stock Alerts** – Track every Torn stock and get real-time price updates in a dedicated channel.\n"
            "2. **Travel Profits** – Use `/travel` to view items you can buy overseas and sell for profit in Torn City.\n\n"
            "🔧 To start:\n"
            "- Create a text channel named `#stock-exchange`\n"
            "- Go there and use `/stock` to activate tracking.\n"
            "- You can stop it anytime using `/stop`."
        )
        await interaction.followup.send(intro, ephemeral=True)

# ------------------ Commands ------------------

@tree.command(name="start", description="Start using the bot")
async def start(interaction: discord.Interaction):
    await send_tos(interaction)

@tree.command(name="stock", description="Start live stock updates in this channel")
async def stock(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    user_id = interaction.user.id

    if user_id not in accepted_users:
        await send_tos(interaction)
        return

    if interaction.channel.name != "stock-exchange":
        await interaction.response.send_message("❗ Please use this command in the `#stock-exchange` channel.", ephemeral=True)
        return

    stock_channels[guild_id] = interaction.channel.id
    stock_messages.setdefault(guild_id, {})

    if guild_id not in stock_tasks:
        stock_tasks[guild_id] = asyncio.create_task(stock_watcher(guild_id))

    await interaction.response.send_message("✅ Stock updates activated in this channel!", ephemeral=False)

@tree.command(name="stop", description="Stop stock updates")
async def stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    stock_channels.pop(guild_id, None)
    stock_messages.pop(guild_id, None)

    task = stock_tasks.pop(guild_id, None)
    if task:
        task.cancel()

    await interaction.response.send_message("🛑 Stock updates have been stopped.", ephemeral=True)

@tree.command(name="invite", description="Invite the bot to your server")
async def invite(interaction: discord.Interaction):
    link = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot+applications.commands&permissions=534723950656"
    await interaction.response.send_message(f"🤖 [Click here to invite this bot to your server]({link})", ephemeral=True)

# ------------------ ToS ------------------

async def send_tos(interaction: discord.Interaction):
    tos_text = (
        "**📄 Terms of Service**\n"
        "- This bot uses a shared Torn API key to fetch public stock data.\n"
        "- No personal Torn API keys are collected.\n"
        "- You are responsible for how this bot is used on your server.\n"
        "- The bot is not affiliated with Torn.com."
    )
    await interaction.response.send_message(tos_text, ephemeral=True, view=ToSView(interaction.user.id))

# ------------------ Stock Tracker ------------------

async def stock_watcher(guild_id):
    try:
        while guild_id in stock_channels:
            url = f"https://api.torn.com/torn/?selections=stocks&key={TORN_API_KEY}"
            response = requests.get(url).json()

            channel = bot.get_channel(stock_channels[guild_id])
            if not channel:
                await asyncio.sleep(30)
                continue

            messages = stock_messages.setdefault(guild_id, {})

            for stock_id, stock in response.get("stocks", {}).items():
                name = stock.get("name")
                price = stock.get("current_price")
                if not name or price is None:
                    continue

                prev = last_prices.get(stock_id)
                content = f"**{name}**: ${price:,}"
                if prev is not None and abs(price - prev) >= 0.0001:
                    emoji = "📈" if price > prev else "📉"
                    change = price - prev
                    content += f" ({emoji} {change:+.4f})"

                last_prices[stock_id] = price

                if stock_id in messages:
                    try:
                        msg = await channel.fetch_message(messages[stock_id])
                        await msg.edit(content=content)
                    except discord.NotFound:
                        msg = await channel.send(content)
                        messages[stock_id] = msg.id
                else:
                    msg = await channel.send(content)
                    messages[stock_id] = msg.id

            await asyncio.sleep(30)

    except asyncio.CancelledError:
        print(f"❌ Cancelled stock watcher for guild {guild_id}")
    except Exception as e:
        print(f"❌ Stock fetch failed for guild {guild_id}: {e}")

@tree.command(name="travel", description="Find travel-based profit opportunities")
async def travel(interaction: discord.Interaction):
    if interaction.user.id not in accepted_users:
        await send_tos(interaction)
        return

    try:
        url = f"https://api.torn.com/torn/?selections=travel&key={TORN_API_KEY}"
        response = requests.get(url).json()

        if "error" in response:
            await interaction.response.send_message("❌ Torn account of the bot is not LVL-15 yet.", ephemeral=True)
            return

        travel_items = response.get("travel", {}).get("items", {})
        profitable = []

        for item_id, item in travel_items.items():
            name = item.get("name")
            cost = item.get("cost")
            market_value = item.get("market_value")
            country = item.get("location")

            if name and cost and market_value and market_value > cost:
                profit = market_value - cost
                profitable.append((profit, name, cost, market_value, country))

        if not profitable:
            await interaction.response.send_message("📉 No profitable travel items found right now.", ephemeral=True)
            return

        profitable.sort(reverse=True)
        top = profitable[:5]
        msg = "**🧳 Travel Profit Opportunities:**\n"

        for profit, name, cost, value, location in top:
            msg += f"- **{name}** from {location}: Buy for ${cost:,}, Sells for ${value:,} → Profit: ${profit:,}\n"

        await interaction.response.send_message(msg, ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"⚠️ Error checking travel items: {e}", ephemeral=True)

# ------------------ Events ------------------

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    await tree.sync()
    print(f"✅ Synced global commands")

# ------------------ Keep Alive Server ------------------

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"⚙️ Dummy server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive).start()

# ------------------ Run Bot ------------------

if __name__ == "__main__":
    bot.run(TOKEN)
