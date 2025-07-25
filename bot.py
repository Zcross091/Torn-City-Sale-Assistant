import os
import json
import discord
import requests
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# Set intents
intents = discord.Intents.default()
intents.message_content = True  # For prefix commands if needed in future

# Define bot and app_commands tree
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # ✅ This is what was missing

# Load or initialize API key storage
API_KEY_FILE = "user_keys.json"
if os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, 'r') as f:
        user_keys = json.load(f)
else:
    user_keys = {}

def save_keys():
    with open(API_KEY_FILE, 'w') as f:
        json.dump(user_keys, f)

# ----------------- Slash Commands ------------------

@tree.command(name="start", description="Start using the Torn City bot")
async def start_command(interaction: discord.Interaction):
    await interaction.response.send_message("Welcome! Please DM me your Torn API key using `/setkey`.", ephemeral=True)

@tree.command(name="setkey", description="DM your Torn City API key to the bot")
@app_commands.describe(key="Your limited Torn City API key")
async def setkey(interaction: discord.Interaction, key: str):
    user_id = str(interaction.user.id)
    user_keys[user_id] = key
    save_keys()
    await interaction.response.send_message("✅ API key saved successfully!", ephemeral=True)

@tree.command(name="profile", description="View your Torn City profile")
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

@tree.command(name="items", description="View your Torn inventory items")
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
        await interaction.response.send_message("Your inventory is empty.", ephemeral=True)
        return

    msg = "**Your Inventory:**\n"
    for item_id, item in inventory.items():
        name = item.get("name")
        quantity = item.get("quantity")
        msg += f"- {name}: {quantity}\n"

    await interaction.response.send_message(msg, ephemeral=True)

# ------------------ On Ready ------------------

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot is online as {bot.user}")

# ------------------ Run Bot ------------------

bot.run(TOKEN)
