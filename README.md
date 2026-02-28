# Discord OpenRouter Bot (Python)

Python Discord bot that listens to one channel and replies using OpenRouter.

## Quick Start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## `.env` (required)
```env
DISCORD_TOKEN=your_discord_bot_token
OPENROUTER_API_KEY=your_openrouter_api_key
TARGET_CHANNEL_ID=123456789012345678
OPENROUTER_MODEL=openrouter/free
```

## Optional settings
```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
OWNER_USER_ID=814869741021560913
PREDEFINED_RESPONSES_FILE=predefined_responses.json
SYSTEM_PROMPT=You are a helpful Discord assistant. Keep replies concise and friendly.
MEMORY_MAX_TURNS=4
MEMORY_MAX_INPUT_TOKENS=500
```

## Owner override command
- If `OWNER_USER_ID` sends a message that starts with `!`, the bot replies with the exact text after `!`.
- Example: `!hello there` -> bot replies `hello there`.
- This response does not ping anyone and does not call OpenRouter.
- If `OWNER_USER_ID` sends the bot a DM, that DM text is forwarded directly to `TARGET_CHANNEL_ID`.

## Predefined Responses (editable)
Edit `predefined_responses.json` to add message -> response pairs:

```json
{
  "hello": "Hey! How can I help you?",
  "hi": "Hi there!"
}
```

Rules:
- Exact match on user message (case-insensitive).
- If a predefined match exists, bot replies with it and skips OpenRouter.
- If no predefined match, bot uses OpenRouter as normal.

## Discord setup
1. Create bot in Discord Developer Portal.
2. Enable `Message Content Intent`.
3. Invite bot to your server.
4. Turn on Discord `Developer Mode`, right-click target channel, `Copy Channel ID`, and set `TARGET_CHANNEL_ID`.

## Notes
- Bot responds only in `TARGET_CHANNEL_ID` for normal AI/predefined behavior.
- 4-second cooldown per user is enabled.
- If OpenRouter quota/rate limit is exhausted and `GROQ_API_KEY` is set, bot automatically falls back to Groq.
- If OpenRouter quota/rate limit is exhausted and `GROQ_API_KEY` is not set, bot replies: `Tokens exhausted for today`.
- Lower memory values are faster/cheaper.
- Do not commit `.env`.

## Run on Raspberry Pi with systemd
1. Update the service file values in `discord-bot.service`:
   - `User=pi`
   - `WorkingDirectory=/home/pi/Discord-bot-new`
   - `ExecStart=/home/pi/Discord-bot-new/.venv/bin/python /home/pi/Discord-bot-new/bot.py`
2. Copy service file:
```bash
sudo cp discord-bot.service /etc/systemd/system/discord-bot.service
```
3. Reload systemd and enable autostart:
```bash
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
```
4. Start the bot service:
```bash
sudo systemctl start discord-bot
```
5. Check status/logs:
```bash
sudo systemctl status discord-bot
journalctl -u discord-bot -f
```
