from typing import Optional

import discord

from .constants import TICKET_TYPES
from .state import MessagePayload
from .tickets import format_message_text


def build_basic_embed(
    embed_color: int, description: str, title: Optional[str] = None
) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=embed_color)


def build_status_embed(embed_color: int, title: str, description: str) -> discord.Embed:
    return build_basic_embed(embed_color=embed_color, title=title, description=description)


def build_user_info_embed(user: discord.User, embed_color: int) -> discord.Embed:
    embed = discord.Embed(title="User Information", color=embed_color)
    embed.add_field(name="Username", value=str(user), inline=False)
    embed.add_field(name="ID", value=str(user.id), inline=False)
    embed.add_field(
        name="Account Created",
        value=discord.utils.format_dt(user.created_at, style="F"),
        inline=False,
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed


def build_user_message_embed(
    user: discord.User, payload: MessagePayload, embed_color: int
) -> discord.Embed:
    embed = discord.Embed(
        description=format_message_text(payload["content"], payload["attachments"]),
        color=embed_color,
        timestamp=payload["created_at"],
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    return embed


def build_staff_message_embed(
    author: discord.abc.User, description: str, embed_color: int
) -> discord.Embed:
    embed = discord.Embed(description=description, color=embed_color)
    embed.set_author(name=str(author), icon_url=author.display_avatar.url)
    return embed


def build_transcript_embed(
    user: discord.User,
    closer: discord.abc.User,
    reason: str,
    ticket_type: str,
    claimer_id: Optional[int],
    embed_color: int,
) -> discord.Embed:
    ticket_label = TICKET_TYPES.get(ticket_type, {}).get("label", ticket_type.title())
    embed = discord.Embed(title="Modmail Transcript", color=embed_color)
    embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
    embed.add_field(name="Ticket Type", value=ticket_label, inline=False)
    embed.add_field(name="Closed By", value=f"{closer} ({closer.id})", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(
        name="Claimed By",
        value=f"<@{claimer_id}> ({claimer_id})" if claimer_id else "Not claimed",
        inline=False,
    )
    embed.timestamp = discord.utils.utcnow()
    return embed
