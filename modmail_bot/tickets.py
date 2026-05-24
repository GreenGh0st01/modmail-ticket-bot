from datetime import datetime
from typing import Collection, Optional

import discord

from .constants import (
    CLAIMER_TOPIC_PREFIX,
    TICKET_TYPES,
    TYPE_TOPIC_PREFIX,
    USER_TOPIC_PREFIX,
)
from .state import AttachmentPayload, MessagePayload, ModmailState, TicketTopicData


def format_message_text(content: str, attachments: Collection[AttachmentPayload]) -> str:
    parts = []

    if content:
        parts.append(content)

    if attachments:
        parts.append("\n".join(item["url"] for item in attachments))

    return "\n\n".join(parts) if parts else "(No text content)"


def serialize_message(message: discord.Message) -> MessagePayload:
    return {
        "content": message.content,
        "attachments": [
            {"filename": attachment.filename, "url": attachment.url}
            for attachment in message.attachments
        ],
        "created_at": message.created_at,
    }


def add_log_entry(
    state: ModmailState,
    channel_id: int,
    actor: str,
    content: str,
    created_at: Optional[datetime] = None,
) -> None:
    timestamp = created_at or discord.utils.utcnow()
    line = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}] {actor}: {content}"
    state.ticket_logs.setdefault(channel_id, []).append(line)


def make_safe_name(name: str) -> str:
    cleaned = name.lower().replace(" ", "-")
    cleaned = "".join(
        character for character in cleaned if character.isalnum() or character == "-"
    ).strip("-")
    return cleaned or "user"


def build_ticket_channel_name(ticket_type: str, user: discord.User) -> str:
    prefix = TICKET_TYPES[ticket_type]["channel_prefix"]
    return f"{prefix}-{make_safe_name(user.name)}"[:100]


def build_claimed_channel_name(user: discord.User) -> str:
    return f"claimed-{make_safe_name(user.name)}"[:100]


def build_channel_topic(
    user_id: int, ticket_type: str, claimer_id: Optional[int] = None
) -> str:
    parts = [f"{USER_TOPIC_PREFIX}{user_id}", f"{TYPE_TOPIC_PREFIX}{ticket_type}"]
    if claimer_id is not None:
        parts.append(f"{CLAIMER_TOPIC_PREFIX}{claimer_id}")
    return "|".join(parts)


def parse_channel_topic(topic: Optional[str]) -> Optional[TicketTopicData]:
    if not topic:
        return None

    user_id = None
    ticket_type = None
    claimer_id = None

    for part in topic.split("|"):
        if part.startswith(USER_TOPIC_PREFIX):
            value = part[len(USER_TOPIC_PREFIX) :]
            if value.isdigit():
                user_id = int(value)
        elif part.startswith(TYPE_TOPIC_PREFIX):
            value = part[len(TYPE_TOPIC_PREFIX) :]
            if value in TICKET_TYPES:
                ticket_type = value
        elif part.startswith(CLAIMER_TOPIC_PREFIX):
            value = part[len(CLAIMER_TOPIC_PREFIX) :]
            if value.isdigit():
                claimer_id = int(value)

    if user_id is None or ticket_type is None:
        return None

    return {
        "user_id": user_id,
        "ticket_type": ticket_type,
        "claimer_id": claimer_id,
    }


def is_ticket_channel(
    state: ModmailState,
    channel: discord.abc.GuildChannel,
    modmail_category_id: int,
    allowed_guild_ids: Collection[int],
) -> bool:
    return (
        isinstance(channel, discord.TextChannel)
        and channel.category_id == modmail_category_id
        and channel.guild.id in allowed_guild_ids
        and channel.id in state.channel_to_user
    )
