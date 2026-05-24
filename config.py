import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def get_int(name: str, default: int = 0) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    return int(value, 0)


def get_int_list(name: str) -> List[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return []
    return [int(item.strip()) for item in value.split(",") if item.strip()]


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MODMAIL_CATEGORY_ID = get_int("MODMAIL_CATEGORY_ID")
LOG_CHANNEL_ID = get_int("LOG_CHANNEL_ID")
ALLOWED_GUILDS = get_int_list("ALLOWED_GUILDS")
EMBED_COLOR = get_int("EMBED_COLOR", 0x5865F2)
