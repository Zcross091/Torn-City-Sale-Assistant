import os
import discord
import requests
from discord.ext import commands, tasks
from discord import app_commands, ui
import threading
import http.server
import socketserver

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
TORN_API_KEY = "fcZtiOzWSKSJQNmy"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

accepted_users = set()
last_prices = {}
stock_channels = {}  # guild_id -> channel_id
stock_messages = {}  # guild_id -> {stock_id: message_id}

# ------------------ UI ------------------

class ToSView(ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @ui.button(label="I AGREE", style=discord.ButtonStyle.success)
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        accepted_users.add(self.user_id)
        await interaction.response.send_message(
            "✅ Terms accepted!\n\n📌 **Instructions:**\n1. Create a channel named `#stock-exchange`.\n2. Go there and use `/stock` to start updates.\n3. Use `/stop` to stop them.",
            ephemeral=True
        )

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
    if not stock_watcher.is_running():
        stock_watcher.start()
    await interaction.response.send_message("✅ Stock updates activated in this channel!", ephemeral=False)

@tree.command(name="stop", description="Stop stock updates")
async def stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    stock_channels.pop(guild_id, None)
    stock_messages.pop(guild_id, None)
    if not stock_channels and stock_watcher.is_running():
        stock_watcher.stop()
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

@tasks.loop(seconds=30)
async def stock_watcher():
    global last_prices
    url = f"https://api.torn.com/torn/?selections=stocks&key={TORN_API_KEY}"
    try:
        response = requests.get(url).json()

        for guild_id, channel_id in stock_channels.items():
            channel = bot.get_channel(channel_id)
            if not channel:
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

    except Exception as e:
        print(f"❌ Stock fetch failed: {e}")

@tree.command(name="travel", description="Find travel-based profit opportunities")
async def travel(interaction: discord.Interaction):
    if interaction.user.id not in accepted_users:
        await send_tos(interaction)
        return

    try:
        url = f"https://api.torn.com/torn/?selections=travel&key={TORN_API_KEY}"
        response = requests.get(url).json()

        if "error" in response:
            await interaction.response.send_message("❌ Failed to fetch data from Torn API.", ephemeral=True)
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
