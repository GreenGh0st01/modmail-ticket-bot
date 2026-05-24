from config import ALLOWED_GUILDS, BOT_TOKEN, EMBED_COLOR, LOG_CHANNEL_ID, MODMAIL_CATEGORY_ID
from modmail_bot import create_bot


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN in .env before running the bot.")

    if not MODMAIL_CATEGORY_ID:
        raise RuntimeError("Set MODMAIL_CATEGORY_ID in .env before running the bot.")

    if not LOG_CHANNEL_ID:
        raise RuntimeError("Set LOG_CHANNEL_ID in .env before running the bot.")

    if not ALLOWED_GUILDS:
        raise RuntimeError("Set ALLOWED_GUILDS in .env before running the bot.")

    bot = create_bot(
        embed_color=EMBED_COLOR,
        modmail_category_id=MODMAIL_CATEGORY_ID,
        log_channel_id=LOG_CHANNEL_ID,
        allowed_guild_ids=ALLOWED_GUILDS,
    )
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
