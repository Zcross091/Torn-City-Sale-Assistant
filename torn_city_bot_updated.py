import os
import json
import discord
import requests
from discord.ext import commands
from discord import app_commands, ui
import threading
import http.server
import socketserver

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

API_KEY_FILE = "user_keys.json"
if os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, 'r') as f:
        user_keys = json.load(f)
else:
    user_keys = {}

def save_keys():
    with open(API_KEY_FILE, 'w') as f:
        json.dump(user_keys, f)

ACCEPTED_USERS_FILE = "accepted_users.json"
if os.path.exists(ACCEPTED_USERS_FILE):
    with open(ACCEPTED_USERS_FILE, "r") as f:
        accepted_users = set(json.load(f))
else:
    accepted_users = set()

def save_accepted_users():
    with open(ACCEPTED_USERS_FILE, "w") as f:
        json.dump(list(accepted_users), f)

# ---------------- MODALS ------------------

class APIKeyModal(ui.Modal, title="Enter Your Torn API Key"):
    api_key = ui.TextInput(label="Your Torn API Key", style=discord.TextStyle.short)

    def __init__(self, user_id):
        super().__init__()
        self.user_id = str(user_id)

    async def on_submit(self, interaction: discord.Interaction):
        user_keys[self.user_id] = self.api_key.value
        save_keys()
        await interaction.response.send_message("✅ Your API key has been saved!", ephemeral=True)

class ToSView(ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = str(user_id)

    @ui.button(label="I AGREE", style=discord.ButtonStyle.success)
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        accepted_users.add(self.user_id)
        save_accepted_users()
        await interaction.response.send_modal(APIKeyModal(self.user_id))

# ---------------- SLASH COMMANDS ------------------

@tree.command(name="setkey", description="Agree to Terms and Set Your Torn API Key")
async def setkey(interaction: discord.Interaction):
    tos_text = (
        "**📄 Terms of Service**\n"
        "- Your Torn API key is used only to fetch your personal game data.\n"
        "- Your key is stored locally and never shared.\n"
        "- You are responsible for your own Torn account actions.\n"
        "- This bot is not affiliated with Torn.com.\n"
        "- By using this bot, you agree to these terms."
    )
    await interaction.response.send_message(tos_text, ephemeral=True, view=ToSView(interaction.user.id))

# ---------------- EXAMPLE: PROFILE ------------------
@tree.command(name="profile", description="View your Torn City profile")
async def profile(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in accepted_users:
        await interaction.response.send_message("❌ You must accept the Terms of Service using `/setkey`.", ephemeral=True)
        return
    if user_id not in user_keys:
        await interaction.response.send_message("❌ You haven't set your API key yet.", ephemeral=True)
        return

    key = user_keys[user_id]
    url = f"https://api.torn.com/user/?selections=profile&key={key}"
    response = requests.get(url).json()

    if "error" in response:
        await interaction.response.send_message("⚠️ Error fetching profile. Check your API key.", ephemeral=True)
        return

    name = response.get("name")
    level = response.get("level")
    status = response.get("status", {}).get("description", "Unknown")
    await interaction.response.send_message(f"**{name}** | Level {level}\nStatus: {status}", ephemeral=True)

# ---------------- READY EVENT ------------------

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    await tree.sync()
    print(f"✅ Bot is online as {bot.user}")

# ---------------- KEEP ALIVE ------------------

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"⚙️ Dummy server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive).start()

# ---------------- MAIN ------------------

if __name__ == "__main__":
    bot.run(TOKEN)
