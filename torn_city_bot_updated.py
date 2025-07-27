import os import discord import requests from discord.ext import commands, tasks from discord import app_commands, ui import threading import http.server import socketserver

TOKEN = os.environ.get("DISCORD_BOT_TOKEN") TORN_API_KEY = "etqdem2Fp1VlhfGB"

intents = discord.Intents.default() intents.message_content = True bot = commands.Bot(command_prefix="!", intents=intents) tree = bot.tree

accepted_users = set() stock_channel_id = None last_prices = {}

------------------ UI ------------------

class ToSView(ui.View): def init(self, user_id): super().init(timeout=60) self.user_id = user_id

@ui.button(label="I AGREE", style=discord.ButtonStyle.success)
async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
    accepted_users.add(self.user_id)
    await interaction.response.send_message(
        "✅ Terms accepted!\n\n📌 **Instructions:**\n1. Create a channel named `#stock-exchange`.\n2. Go there and use `/stock` to start updates.\n3. Use `/stop` to stop them.",
        ephemeral=True
    )

------------------ Commands ------------------

@tree.command(name="start", description="Start using the bot") async def start(interaction: discord.Interaction): await send_tos(interaction)

@tree.command(name="stock", description="Start live stock updates in this channel") async def stock(interaction: discord.Interaction): global stock_channel_id user_id = interaction.user.id if user_id not in accepted_users: await send_tos(interaction) return

if interaction.channel.name != "stock-exchange":
    await interaction.response.send_message("❗ Please use this command in the `#stock-exchange` channel.", ephemeral=True)
    return

stock_channel_id = interaction.channel.id
stock_watcher.start()
await interaction.response.send_message("✅ Stock updates activated in this channel!", ephemeral=False)

@tree.command(name="stop", description="Stop stock updates") async def stop(interaction: discord.Interaction): global stock_channel_id stock_channel_id = None if stock_watcher.is_running(): stock_watcher.stop() await interaction.response.send_message("🛑 Stock updates have been stopped.", ephemeral=True)

@tree.command(name="invite", description="Invite the bot to your server") async def invite(interaction: discord.Interaction): link = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot+applications.commands&permissions=534723950656" await interaction.response.send_message(f"🤖 Click here to invite this bot to your server", ephemeral=True)

------------------ ToS ------------------

async def send_tos(interaction: discord.Interaction): tos_text = ( "📄 Terms of Service\n" "- This bot uses a shared Torn API key to fetch public stock data.\n" "- No personal Torn API keys are collected.\n" "- You are responsible for how this bot is used on your server.\n" "- The bot is not affiliated with Torn.com." ) await interaction.response.send_message(tos_text, ephemeral=True, view=ToSView(interaction.user.id))

------------------ Stock Tracker ------------------

@tasks.loop(seconds=30) async def stock_watcher(): global last_prices if not stock_channel_id: return

url = f"https://api.torn.com/torn/?selections=stocks&key={TORN_API_KEY}"
try:
    response = requests.get(url).json()
    changes = []
    for stock_id, stock in response.get("stocks", {}).items():
        name = stock.get("name")
        price = stock.get("current_price")
        if not name or price is None:
            continue
        prev = last_prices.get(stock_id)
        if prev is not None and abs(price - prev) >= 0.0001:
            emoji = "📈" if price > prev else "📉"
            change = price - prev
            changes.append(f"{emoji} **{name}**: ${prev:,} → ${price:,} ({change:+.4f})")
        last_prices[stock_id] = price

    if changes:
        channel = bot.get_channel(stock_channel_id)
        if channel:
            await channel.send("**📊 Stock Market Update:**\n" + "\n".join(changes))
except Exception as e:
    print(f"Stock fetch failed: {e}")

------------------ Events ------------------

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    await tree.sync()
    print(f"✅ Bot is online as {bot.user}")

------------------ Keep Alive Server ------------------

def keep_alive(): port = int(os.environ.get("PORT", 10000)) handler = http.server.SimpleHTTPRequestHandler with socketserver.TCPServer(("", port), handler) as httpd: print(f"⚙️ Dummy server running on port {port}") httpd.serve_forever()

threading.Thread(target=keep_alive).start()

------------------ Main ------------------

if name == "main": bot.run(TOKEN)

