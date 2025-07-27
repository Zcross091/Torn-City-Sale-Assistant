
import os
import json
import discord
import requests
from discord.ext import commands
from discord import app_commands
import threading
import http.server
import socketserver

# Load environment variables
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# Set intents
intents = discord.Intents.default()
intents.message_content = True

# Define bot and command tree
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Load or initialize user API keys
API_KEY_FILE = "user_keys.json"
if os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, 'r') as f:
        user_keys = json.load(f)
else:
    user_keys = {}

def save_keys():
    with open(API_KEY_FILE, 'w') as f:
        json.dump(user_keys, f)

# ------------- Slash Commands -------------

@bot.tree.command(name="start", description="Start using the Torn City bot")
async def start_command(interaction: discord.Interaction):
    await interaction.response.send_message("👋 Welcome! Please DM me your Torn API key using `/setkey`.", ephemeral=True)

@bot.tree.command(name="setkey", description="DM your Torn City API key to the bot")
@app_commands.describe(key="Your limited Torn City API key")
async def setkey(interaction: discord.Interaction, key: str):
    user_id = str(interaction.user.id)
    user_keys[user_id] = key
    save_keys()
    await interaction.response.send_message("✅ API key saved successfully!", ephemeral=True)

@bot.tree.command(name="profile", description="View your Torn City profile")
async def profile(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in user_keys:
        await interaction.response.send_message("❌ You haven't set your API key yet. Use `/setkey` first.", ephemeral=True)
        return

    key = user_keys[user_id]
    url = f"https://api.torn.com/user/?selections=profile&key={key}"
    response = requests.get(url).json()

    if "error" in response:
        await interaction.response.send_message("⚠️ Error fetching data. Is your API key correct?", ephemeral=True)
        return

    name = response.get("name")
    level = response.get("level")
    status = response.get("status", {}).get("description", "Unknown")
    await interaction.response.send_message(f"**{name}** | Level {level}\nStatus: {status}", ephemeral=True)

@bot.tree.command(name="items", description="View your Torn inventory items")
async def items(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in user_keys:
        await interaction.response.send_message("❌ Set your API key first with `/setkey`.", ephemeral=True)
        return

    key = user_keys[user_id]
    url = f"https://api.torn.com/user/?selections=inventory&key={key}"
    response = requests.get(url).json()

    if "error" in response:
        await interaction.response.send_message("⚠️ Error fetching inventory.", ephemeral=True)
        return

    inventory = response.get("inventory", {})
    if not inventory:
        await interaction.response.send_message("📭 Your inventory is empty.", ephemeral=True)
        return

    msg = "**🎒 Your Inventory:**\n"
    for item_id, item in inventory.items():
        name = item.get("name")
        quantity = item.get("quantity")
        msg += f"- {name}: {quantity}\n"

    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="advise", description="Suggest profitable items from the market")
async def advise(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in user_keys:
        await interaction.response.send_message("❌ Set your API key first with `/setkey`.", ephemeral=True)
        return

    key = user_keys[user_id]
    url = f"https://api.torn.com/market/?selections=items&key={key}"
    market_data = requests.get(url).json()

    if "error" in market_data:
        await interaction.response.send_message("⚠️ Couldn't fetch market data. Check your API permissions.", ephemeral=True)
        return

    profitable = []
    for item_id, item in market_data.get("items", {}).items():
        market_price = item.get("market_price")
        item_value = item.get("item", {}).get("value")
        name = item.get("item", {}).get("name")

        if market_price and item_value and market_price < item_value:
            profit = item_value - market_price
            profitable.append((name, market_price, item_value, profit))

    if not profitable:
        await interaction.response.send_message("📉 No profitable items found right now.", ephemeral=True)
        return

    profitable.sort(key=lambda x: x[3], reverse=True)
    top = profitable[:5]

    msg = "**💸 Top Profitable Items:**\n"
    for name, market, value, profit in top:
        msg += f"- **{name}**: Buy for ${market:,}, Value ${value:,} → Profit: ${profit:,}\n"

    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="advise_stock", description="Suggest stocks that might be worth buying (based on price drop)")
async def advise_stock(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in user_keys:
        await interaction.response.send_message("❌ Set your API key first with `/setkey`.", ephemeral=True)
        return

    key = user_keys[user_id]
    url = f"https://api.torn.com/torn/?selections=stocks&key={key}"
    data = requests.get(url).json()

    if "error" in data:
        await interaction.response.send_message("⚠️ Couldn't fetch stock data. Check your API key permissions.", ephemeral=True)
        return

    suggestions = []
    for stock_id, stock in data.get("stocks", {}).items():
        current = stock.get("current_price")
        high = stock.get("highest_price")
        name = stock.get("name")

        if current and high and current < (0.85 * high):  # drop of 15%+
            drop = high - current
            suggestions.append((name, current, high, drop))

    if not suggestions:
        await interaction.response.send_message("📉 No undervalued stocks found at the moment.", ephemeral=True)
        return

    suggestions.sort(key=lambda x: x[3], reverse=True)
    top = suggestions[:5]

    msg = "**📉 Stocks Currently Cheap:**\n"
    for name, current, high, drop in top:
        msg += f"- **{name}**: ${current:,} (was ${high:,}) → Drop: ${drop:,}\n"

    await interaction.response.send_message(msg, ephemeral=True)

# ------------------ On Ready ------------------

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    await bot.tree.sync()

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

