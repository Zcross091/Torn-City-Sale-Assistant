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

# Track users who accepted Terms of Service
ACCEPTED_USERS_FILE = "accepted_users.json"
if os.path.exists(ACCEPTED_USERS_FILE):
    with open(ACCEPTED_USERS_FILE, "r") as f:
        accepted_users = set(json.load(f))
else:
    accepted_users = set()

def save_accepted_users():
    with open(ACCEPTED_USERS_FILE, "w") as f:
        json.dump(list(accepted_users), f)

# ------------- Slash Commands -------------

@bot.tree.command(name="tos", description="View the bot's Terms of Service")
async def tos(interaction: discord.Interaction):
    tos_text = (
        "**\U0001F4DC Terms of Service**\n"
        "- Your Torn API key is used only to fetch your personal game data.\n"
        "- Your key is stored locally and never shared.\n"
        "- You are responsible for your own Torn account actions.\n"
        "- This bot is not affiliated with Torn.com.\n"
        "- By using this bot, you agree to these terms.\n\n"
        "Use `/accept_tos` to continue."
    )
    await interaction.response.send_message(tos_text, ephemeral=True)

@bot.tree.command(name="accept_tos", description="Accept the Terms of Service to use the bot")
async def accept_tos(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in accepted_users:
        await interaction.response.send_message("✅ You’ve already accepted the Terms of Service.", ephemeral=True)
        return

    accepted_users.add(user_id)
    save_accepted_users()
    await interaction.response.send_message("✅ ToS accepted! You can now use the bot's features.", ephemeral=True)

@bot.tree.command(name="start", description="Start using the Torn City bot")
async def start_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in accepted_users:
        await interaction.response.send_message("❌ You must accept the Terms of Service. Use `/tos`.", ephemeral=True)
        return
    await interaction.response.send_message("\U0001F44B Welcome! Please DM me your Torn API key using `/setkey`.", ephemeral=True)

@bot.tree.command(name="setkey", description="DM your Torn City API key to the bot")
@app_commands.describe(key="Your limited Torn City API key")
async def setkey(interaction: discord.Interaction, key: str):
    user_id = str(interaction.user.id)
    if user_id not in accepted_users:
        await interaction.response.send_message("❌ You must accept the Terms of Service. Use `/tos`.", ephemeral=True)
        return
    user_keys[user_id] = key
    save_keys()
    await interaction.response.send_message("✅ API key saved successfully!", ephemeral=True)

@bot.tree.command(name="changekey", description="Update your Torn API key")
@app_commands.describe(new_key="Your new Torn City API key")
async def changekey(interaction: discord.Interaction, new_key: str):
    user_id = str(interaction.user.id)
    if user_id not in accepted_users:
        await interaction.response.send_message("❌ You must accept the Terms of Service. Use `/tos`.", ephemeral=True)
        return
    user_keys[user_id] = new_key
    save_keys()
    await interaction.response.send_message("🔁 Your API key has been updated successfully.", ephemeral=True)

@bot.tree.command(name="removekey", description="Remove your saved Torn API key")
async def removekey(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in user_keys:
        del user_keys[user_id]
        save_keys()
        await interaction.response.send_message("🗑️ Your API key has been deleted.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ You have no saved API key.", ephemeral=True)

@bot.tree.command(name="profile", description="View your Torn City profile")
async def profile(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in accepted_users:
        await interaction.response.send_message("❌ You must accept the Terms of Service. Use `/tos`.", ephemeral=True)
        return
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

# ------------------ On Ready ------------------

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    await bot.tree.sync()
    print(f"✅ Bot is online as {bot.user}")

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
