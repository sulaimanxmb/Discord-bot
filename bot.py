import asyncio
import os
import logging
import time
import json
from typing import Dict, List, Optional

import aiohttp
import discord
from discord import Message
from dotenv import load_dotenv


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TARGET_CHANNEL_ID_RAW = os.getenv("TARGET_CHANNEL_ID")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "discord-channel-bot")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful Discord assistant. Keep replies concise and friendly.",
)
OWNER_SYSTEM_PROMPT = os.getenv("OWNER_SYSTEM_PROMPT", SYSTEM_PROMPT)
USER_COOLDOWN_SECONDS = 4.0
PREDEFINED_RESPONSES_FILE = os.getenv("PREDEFINED_RESPONSES_FILE", "predefined_responses.json")
OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", "814869741021560913"))

GENERIC_FAILURE_REPLY = "I couldn't generate a response right now. Please try again in a moment."
TOKEN_EXHAUSTED_REPLY = "Tokens exhausted for today"

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set.")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set.")
if not TARGET_CHANNEL_ID_RAW:
    raise ValueError("TARGET_CHANNEL_ID is not set.")

try:
    TARGET_CHANNEL_ID = int(TARGET_CHANNEL_ID_RAW)
except ValueError as exc:
    raise ValueError("TARGET_CHANNEL_ID must be a valid integer channel ID.") from exc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("discord-openrouter-bot")


def is_quota_or_limit_error(status_code: int, response_text: str) -> bool:
    lower_response = response_text.lower()
    phrases = [
        "exhausted",
        "quota",
        "insufficient",
        "credit",
        "rate limit",
        "limit reached",
        "daily limit",
    ]
    return status_code in {402, 429} or any(phrase in lower_response for phrase in phrases)


def load_predefined_responses(filepath: str) -> Dict[str, str]:
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("Predefined responses file must contain a JSON object: %s", filepath)
            return {}
        cleaned: Dict[str, str] = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str):
                key = k.strip().lower()
                if key:
                    cleaned[key] = v
        return cleaned
    except Exception as exc:
        logger.error("Failed to load predefined responses from %s: %s", filepath, exc)
        return {}


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        site_url: str = "",
        app_name: str = "discord-bot",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.site_url = site_url
        self.app_name = app_name
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=45)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def generate_reply(self, messages: List[Dict[str, str]]) -> str:
        if not self.session:
            raise RuntimeError("HTTP session is not initialized.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        async with self.session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response_text = await response.text()
            if response.status != 200:
                if is_quota_or_limit_error(response.status, response_text):
                    return TOKEN_EXHAUSTED_REPLY

                logger.error(
                    "OpenRouter error %s: %s",
                    response.status,
                    response_text,
                )
                return GENERIC_FAILURE_REPLY

            data = await response.json()
            choices = data.get("choices", [])
            if not choices:
                return "I couldn't find a response from the model."

            raw_content = choices[0].get("message", {}).get("content", "")
            if isinstance(raw_content, list):
                parts = []
                for chunk in raw_content:
                    if isinstance(chunk, dict) and chunk.get("type") == "text":
                        parts.append(chunk.get("text", ""))
                content = "".join(parts).strip()
            else:
                content = str(raw_content).strip()
            if not content:
                return "I received an empty response from the model."
            return content


class GroqClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=45)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def generate_reply(self, messages: List[Dict[str, str]]) -> str:
        if not self.session:
            raise RuntimeError("HTTP session is not initialized.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        async with self.session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response_text = await response.text()
            if response.status != 200:
                logger.error("Groq error %s: %s", response.status, response_text)
                return GENERIC_FAILURE_REPLY

            data = await response.json()
            choices = data.get("choices", [])
            if not choices:
                return "I couldn't find a response from the model."

            raw_content = choices[0].get("message", {}).get("content", "")
            if isinstance(raw_content, list):
                parts = []
                for chunk in raw_content:
                    if isinstance(chunk, dict) and chunk.get("type") == "text":
                        parts.append(chunk.get("text", ""))
                content = "".join(parts).strip()
            else:
                content = str(raw_content).strip()
            if not content:
                return "I received an empty response from the model."
            return content


def build_prompt_messages(
    user_text: str,
    system_prompt: str,
) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]


def get_target_user_mention(message: Message) -> Optional[str]:
    for mentioned_user in message.mentions:
        if not mentioned_user.bot:
            return f"<@{mentioned_user.id}>"
    return None


async def get_target_channel() -> Optional[discord.abc.Messageable]:
    channel = client.get_channel(TARGET_CHANNEL_ID)
    if channel is not None:
        return channel
    try:
        fetched = await client.fetch_channel(TARGET_CHANNEL_ID)
        if isinstance(fetched, discord.abc.Messageable):
            return fetched
    except Exception as exc:
        logger.error("Failed to fetch target channel %s: %s", TARGET_CHANNEL_ID, exc)
    return None


intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
openrouter = OpenRouterClient(
    api_key=OPENROUTER_API_KEY,
    model=OPENROUTER_MODEL,
    site_url=OPENROUTER_SITE_URL,
    app_name=OPENROUTER_APP_NAME,
)
groq_client: Optional[GroqClient] = (
    GroqClient(api_key=GROQ_API_KEY, model=GROQ_MODEL) if GROQ_API_KEY else None
)
channel_lock = asyncio.Lock()
user_last_message_ts: Dict[int, float] = {}
predefined_responses: Dict[str, str] = load_predefined_responses(PREDEFINED_RESPONSES_FILE)


@client.event
async def on_ready() -> None:
    await openrouter.start()
    if groq_client is not None:
        await groq_client.start()
    logger.info("Logged in as %s (id=%s)", client.user, getattr(client.user, "id", None))
    logger.info("Listening to channel ID: %s", TARGET_CHANNEL_ID)
    logger.info("Predefined responses loaded: %s entries", len(predefined_responses))
    logger.info("Groq fallback enabled: %s", bool(groq_client))


@client.event
async def on_message(message: Message) -> None:
    if message.author.bot:
        return

    user_text = message.content.strip()
    if not user_text:
        return

    # Owner DM relay: any DM sent by owner is forwarded to TARGET_CHANNEL_ID as-is.
    if message.author.id == OWNER_USER_ID and message.guild is None:
        target_channel = await get_target_channel()
        if target_channel is None:
            await message.reply("Could not find target channel.", mention_author=False)
            return
        await target_channel.send(user_text, allowed_mentions=discord.AllowedMentions.none())
        await message.reply("Sent to target channel.", mention_author=False)
        return

    # Owner-only raw echo command: "!text" -> "text" with no mentions.
    if message.author.id == OWNER_USER_ID and user_text.startswith("!"):
        raw_reply = user_text[1:].strip()
        if raw_reply:
            await message.reply(
                raw_reply,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        return

    if message.channel.id != TARGET_CHANNEL_ID:
        return

    target_mention = get_target_user_mention(message)
    allowed_mentions = discord.AllowedMentions(
        everyone=False,
        roles=False,
        users=True,
        replied_user=True,
    )

    predefined_reply = predefined_responses.get(user_text.lower())
    if predefined_reply is not None:
        final_predefined = (
            f"{target_mention} {predefined_reply}" if target_mention else predefined_reply
        )
        await message.reply(
            final_predefined,
            mention_author=True,
            allowed_mentions=allowed_mentions,
        )
        return

    now = time.monotonic()
    user_id = message.author.id
    last_ts = user_last_message_ts.get(user_id)
    if last_ts is not None:
        remaining = USER_COOLDOWN_SECONDS - (now - last_ts)
        if remaining > 0:
            await message.reply(
                f"Please wait {remaining:.1f}s before sending another message.",
                mention_author=True,
                allowed_mentions=allowed_mentions,
            )
            return
    user_last_message_ts[user_id] = now

    async with channel_lock:
        system_prompt = (
            OWNER_SYSTEM_PROMPT if message.author.id == OWNER_USER_ID else SYSTEM_PROMPT
        )
        model_user_text = (
            f"Address this user in your reply: {target_mention}\n\n{user_text}"
            if target_mention
            else user_text
        )
        prompt_messages = build_prompt_messages(
            user_text=model_user_text,
            system_prompt=system_prompt,
        )

        async with message.channel.typing():
            reply = await openrouter.generate_reply(prompt_messages)
            if reply == TOKEN_EXHAUSTED_REPLY and groq_client is not None:
                logger.info("OpenRouter exhausted/limited, falling back to Groq.")
                reply = await groq_client.generate_reply(prompt_messages)

        if target_mention and not reply.startswith(target_mention):
            reply = f"{target_mention} {reply}"

    await message.reply(reply, mention_author=True, allowed_mentions=allowed_mentions)


async def main() -> None:
    try:
        await client.start(DISCORD_TOKEN)
    finally:
        await openrouter.close()
        if groq_client is not None:
            await groq_client.close()


if __name__ == "__main__":
    asyncio.run(main())
