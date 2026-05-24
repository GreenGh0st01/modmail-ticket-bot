# Modmail/Ticket Bot

A button-based modmail and ticket bot built with `discord.py`.

## Project Files

- `main.py`
- `config.py`
- `requirements.txt`
- `.env`
- `.env.example`

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Fill in `.env` with your bot settings. A safe template is included in `.env.example`.

4. Enable the Message Content intent for your bot in the Discord Developer Portal.

5. Start the bot:

```bash
python3 main.py
```

## Environment Variables

`.env` uses this format:

```env
BOT_TOKEN=your_token_here
MODMAIL_CATEGORY_ID=1498624427699470356
LOG_CHANNEL_ID=1498630534467817503
ALLOWED_GUILDS=1496877640194199624,1351646444775407769
EMBED_COLOR=0x5865F2
```

## Features

- First user DM shows buttons for Partnership, Questions, or Report Member
- Button click creates the matching ticket channel
- Existing tickets are always reused
- All user and staff messages are sent as embeds
- `TVDreply <message>` sends an embed reply to the user
- `TVDclose <reason>` closes the ticket and logs a transcript
- `TVDclaim` claims the ticket and renames the channel
- `TVDblock` blocks the linked user from opening new tickets
- Ticket ownership rebuilds from channel topics after restart

## Open Source Safety

- `config.py` only loads values from environment variables
- `.env` is ignored by git
- `.env.example` is safe to publish

## Notes

- `discord.py==2.7.1` is pinned in `requirements.txt`
- `python-dotenv` loads values from `.env`
