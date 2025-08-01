import discord
from discord.ext import commands
import openai
import os

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

openai.api_key = os.getenv("OPENAI_API_KEY")  # Place your OpenAI key in .env or Render secrets

@bot.event
async def on_ready():
    print(f'🤖 Logged in as {bot.user.name}')

@bot.command()
async def talk(ctx, *, prompt):
    await ctx.trigger_typing()
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a sarcastic video game NPC named Kronos."},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content
        await ctx.reply(reply)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
