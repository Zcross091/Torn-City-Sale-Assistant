# Kronos Bot – AI Chatting NPC for Discord

A Discord bot that acts like a sarcastic NPC using OpenAI's GPT model.

## Features
- Responds to `/talk your message`
- Acts like a game character
- Built with `discord.py` + OpenAI GPT

## Setup

1. Create a `.env` file or set environment variables:
```
DISCORD_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
```

2. Install requirements:
```
pip install -r requirements.txt
```

3. Run the bot:
```
python main.py
```

## Customize the Bot's Personality
Edit the `"system"` message in `main.py` to change the personality.

## Hosting
You can host it on:
- [Render](https://render.com)
- Replit
- Railway
- Your own server
