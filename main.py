import io
from datetime import datetime
from typing import Dict, List, Optional, Set

import discord
from discord.ext import commands

from config import *

PREFIX = "TVD"
USER_TOPIC_PREFIX = "modmail_user_id:"
TYPE_TOPIC_PREFIX = "ticket_type:"
CLAIMER_TOPIC_PREFIX = "claimer:"

TICKET_TYPES = {
    "partnership": {
        "label": "Partnership",
        "emoji": "\U0001F91D",
        "channel_prefix": "partnership",
    },
    "questions": {
        "label": "Questions",
        "emoji": "\u2753",
        "channel_prefix": "questions",
    },
    "report": {
        "label": "Report Member",
        "emoji": "\U0001F6A8",
        "channel_prefix": "report",
    },
}

user_to_channel: Dict[int, int] = {}
channel_to_user: Dict[int, int] = {}
claimed_by: Dict[int, int] = {}
blocked_users: Set[int] = set()

pending_messages: Dict[int, List[Dict[str, object]]] = {}
ticket_logs: Dict[int, List[str]] = {}


def build_basic_embed(description: str, title: Optional[str] = None) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=EMBED_COLOR)


def build_status_embed(title: str, description: str) -> discord.Embed:
    return build_basic_embed(description=description, title=title)


def build_user_info_embed(user: discord.User) -> discord.Embed:
    embed = discord.Embed(title="User Information", color=EMBED_COLOR)
    embed.add_field(name="Username", value=str(user), inline=False)
    embed.add_field(name="ID", value=str(user.id), inline=False)
    embed.add_field(
        name="Account Created",
        value=discord.utils.format_dt(user.created_at, style="F"),
        inline=False,
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed


def format_message_text(content: str, attachments: List[Dict[str, str]]) -> str:
    parts: List[str] = []

    if content:
        parts.append(content)

    if attachments:
        parts.append("\n".join(item["url"] for item in attachments))

    return "\n\n".join(parts) if parts else "(No text content)"


def serialize_message(message: discord.Message) -> Dict[str, object]:
    return {
        "content": message.content,
        "attachments": [
            {"filename": attachment.filename, "url": attachment.url}
            for attachment in message.attachments
        ],
        "created_at": message.created_at,
    }


def build_user_message_embed(
    user: discord.User, payload: Dict[str, object]
) -> discord.Embed:
    description = format_message_text(
        payload["content"],
        payload["attachments"],
    )
    embed = discord.Embed(
        description=description,
        color=EMBED_COLOR,
        timestamp=payload["created_at"],
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    return embed


def build_staff_message_embed(
    author: discord.abc.User, description: str
) -> discord.Embed:
    embed = discord.Embed(description=description, color=EMBED_COLOR)
    embed.set_author(name=str(author), icon_url=author.display_avatar.url)
    return embed


def build_transcript_embed(
    user: discord.User,
    closer: discord.abc.User,
    reason: str,
    ticket_type: str,
    claimer_id: Optional[int],
) -> discord.Embed:
    ticket_label = TICKET_TYPES.get(ticket_type, {}).get("label", ticket_type.title())
    embed = discord.Embed(title="Modmail Transcript", color=EMBED_COLOR)
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


def add_log_entry(
    channel_id: int,
    actor: str,
    content: str,
    created_at: Optional[datetime] = None,
) -> None:
    timestamp = created_at or discord.utils.utcnow()
    line = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}] {actor}: {content}"
    ticket_logs.setdefault(channel_id, []).append(line)


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


def parse_channel_topic(topic: Optional[str]) -> Optional[Dict[str, object]]:
    if not topic:
        return None

    data: Dict[str, object] = {"user_id": None, "ticket_type": None, "claimer_id": None}
    for part in topic.split("|"):
        if part.startswith(USER_TOPIC_PREFIX):
            value = part[len(USER_TOPIC_PREFIX) :]
            if value.isdigit():
                data["user_id"] = int(value)
        elif part.startswith(TYPE_TOPIC_PREFIX):
            value = part[len(TYPE_TOPIC_PREFIX) :]
            if value in TICKET_TYPES:
                data["ticket_type"] = value
        elif part.startswith(CLAIMER_TOPIC_PREFIX):
            value = part[len(CLAIMER_TOPIC_PREFIX) :]
            if value.isdigit():
                data["claimer_id"] = int(value)

    if data["user_id"] is None or data["ticket_type"] is None:
        return None

    return data


def is_ticket_channel(channel: discord.abc.GuildChannel) -> bool:
    return (
        isinstance(channel, discord.TextChannel)
        and channel.category_id == MODMAIL_CATEGORY_ID
        and channel.guild.id in ALLOWED_GUILDS
        and channel.id in channel_to_user
    )


class SupportTypeView(discord.ui.View):
    def __init__(self, bot: "ModmailBot", disabled: bool = False) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        for item in self.children:
            item.disabled = disabled

    async def handle_selection(
        self, interaction: discord.Interaction, ticket_type: str
    ) -> None:
        await interaction.response.defer()
        await self.bot.handle_ticket_selection(interaction, ticket_type)

    @discord.ui.button(
        label="Partnership",
        emoji="\U0001F91D",
        style=discord.ButtonStyle.primary,
        custom_id="tvd_modmail_partnership",
    )
    async def partnership(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.handle_selection(interaction, "partnership")

    @discord.ui.button(
        label="Questions",
        emoji="\u2753",
        style=discord.ButtonStyle.secondary,
        custom_id="tvd_modmail_questions",
    )
    async def questions(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.handle_selection(interaction, "questions")

    @discord.ui.button(
        label="Report Member",
        emoji="\U0001F6A8",
        style=discord.ButtonStyle.danger,
        custom_id="tvd_modmail_report",
    )
    async def report(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.handle_selection(interaction, "report")


class ModmailBot(commands.Bot):
    async def setup_hook(self) -> None:
        self.add_view(SupportTypeView(self))

    async def on_ready(self) -> None:
        self.rebuild_ticket_maps()
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("Button-based modmail bot is ready.")

    def get_modmail_category(self) -> Optional[discord.CategoryChannel]:
        category = self.get_channel(MODMAIL_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            return None

        if category.guild.id not in ALLOWED_GUILDS:
            return None

        return category

    def get_log_channel(self) -> Optional[discord.TextChannel]:
        channel = self.get_channel(LOG_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return None

        if channel.guild.id not in ALLOWED_GUILDS:
            return None

        return channel

    def rebuild_ticket_maps(self) -> None:
        user_to_channel.clear()
        channel_to_user.clear()
        claimed_by.clear()

        category = self.get_modmail_category()
        if category is None:
            print("Warning: Modmail category not found in an allowed guild.")
            return

        for channel in category.text_channels:
            data = parse_channel_topic(channel.topic)
            if data is None:
                continue

            user_id = data["user_id"]
            user_to_channel[user_id] = channel.id
            channel_to_user[channel.id] = user_id
            ticket_logs.setdefault(channel.id, [])

            claimer_id = data["claimer_id"]
            if claimer_id is not None:
                claimed_by[channel.id] = claimer_id

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if message.guild is None:
            await self.handle_user_dm(message)
            return

        if message.guild.id not in ALLOWED_GUILDS:
            return

        if is_ticket_channel(message.channel) and not message.content.startswith(PREFIX):
            await self.forward_staff_message(message)

        await self.process_commands(message)

    async def handle_user_dm(self, message: discord.Message) -> None:
        if message.author.id in blocked_users:
            return

        ticket_channel = self.get_existing_ticket_channel(message.author.id)
        payload = serialize_message(message)

        if ticket_channel is not None:
            await ticket_channel.send(embed=build_user_message_embed(message.author, payload))
            add_log_entry(
                ticket_channel.id,
                f"User {message.author}",
                format_message_text(payload["content"], payload["attachments"]),
                payload["created_at"],
            )
            return

        pending_messages.setdefault(message.author.id, []).append(payload)

        if len(pending_messages[message.author.id]) == 1:
            await message.author.send(
                embed=build_status_embed(
                    "TVD Support",
                    "What type of support do you need?",
                ),
                view=SupportTypeView(self),
            )
            return

        await message.author.send(
            embed=build_status_embed(
                "Support Type Needed",
                "Please choose one of the support buttons above so I can create your ticket.",
            )
        )

    async def handle_ticket_selection(
        self, interaction: discord.Interaction, ticket_type: str
    ) -> None:
        user = interaction.user

        if user.id in blocked_users:
            await interaction.followup.send(
                embed=build_status_embed(
                    "Blocked",
                    "You are blocked from opening modmail tickets.",
                )
            )
            return

        existing_channel = self.get_existing_ticket_channel(user.id)
        if existing_channel is not None:
            await interaction.followup.send(
                embed=build_status_embed(
                    "Ticket Already Open",
                    "You already have an open ticket. Please continue messaging here.",
                )
            )
            return

        queued_messages = pending_messages.pop(user.id, None)
        if not queued_messages:
            await interaction.followup.send(
                embed=build_status_embed(
                    "No Pending Message",
                    "Send me a DM first so I can create your ticket.",
                )
            )
            return

        channel = await self.create_ticket_channel(user, ticket_type)
        if channel is None:
            pending_messages[user.id] = queued_messages
            await interaction.followup.send(
                embed=build_status_embed(
                    "Configuration Error",
                    "I could not find the modmail category in an allowed guild.",
                )
            )
            return

        await interaction.message.edit(view=SupportTypeView(self, disabled=True))
        await channel.send(embed=build_user_info_embed(user))

        add_log_entry(
            channel.id,
            "System",
            f"Ticket created for {user} ({user.id}) as {ticket_type}.",
        )

        for payload in queued_messages:
            await channel.send(embed=build_user_message_embed(user, payload))
            add_log_entry(
                channel.id,
                f"User {user}",
                format_message_text(payload["content"], payload["attachments"]),
                payload["created_at"],
            )

        await user.send(
            embed=build_status_embed(
                "Ticket Created",
                "Your ticket has been created!",
            )
        )

    def get_existing_ticket_channel(self, user_id: int) -> Optional[discord.TextChannel]:
        channel_id = user_to_channel.get(user_id)
        if channel_id is None:
            return None

        channel = self.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            if channel.category_id == MODMAIL_CATEGORY_ID and channel.guild.id in ALLOWED_GUILDS:
                return channel

        user_to_channel.pop(user_id, None)
        channel_to_user.pop(channel_id, None)
        claimed_by.pop(channel_id, None)
        return None

    async def create_ticket_channel(
        self, user: discord.User, ticket_type: str
    ) -> Optional[discord.TextChannel]:
        category = self.get_modmail_category()
        if category is None:
            return None

        channel = await category.guild.create_text_channel(
            name=build_ticket_channel_name(ticket_type, user),
            category=category,
            topic=build_channel_topic(user.id, ticket_type),
        )
        user_to_channel[user.id] = channel.id
        channel_to_user[channel.id] = user.id
        ticket_logs[channel.id] = []
        return channel

    async def forward_staff_message(self, message: discord.Message) -> None:
        user_id = channel_to_user.get(message.channel.id)
        if user_id is None:
            return

        claimer_id = claimed_by.get(message.channel.id)
        if claimer_id is not None and message.author.id != claimer_id:
            return

        user = self.get_user(user_id) or await self.fetch_user(user_id)
        description = format_message_text(
            message.content,
            [
                {"filename": attachment.filename, "url": attachment.url}
                for attachment in message.attachments
            ],
        )

        sent = await self.send_user_dm(user, message.author, description)
        if sent:
            add_log_entry(
                message.channel.id,
                f"Staff {message.author}",
                description,
                message.created_at,
            )

    async def send_user_dm(
        self, user: discord.User, author: discord.abc.User, description: str
    ) -> bool:
        dm_channel = user.dm_channel or await user.create_dm()
        try:
            async with dm_channel.typing():
                await dm_channel.send(embed=build_staff_message_embed(author, description))
            return True
        except discord.Forbidden:
            return False

    def ticket_type_for_channel(self, channel: discord.TextChannel) -> str:
        data = parse_channel_topic(channel.topic)
        if data is None:
            return "questions"
        return data["ticket_type"]

    async def update_claim_state(
        self, channel: discord.TextChannel, claimer_id: Optional[int]
    ) -> None:
        user_id = channel_to_user.get(channel.id)
        if user_id is None:
            return

        ticket_type = self.ticket_type_for_channel(channel)
        await channel.edit(topic=build_channel_topic(user_id, ticket_type, claimer_id))

    async def send_transcript_log(
        self,
        channel: discord.TextChannel,
        user: discord.User,
        closer: discord.abc.User,
        reason: str,
    ) -> None:
        log_channel = self.get_log_channel()
        if log_channel is None:
            return

        transcript_lines = ticket_logs.get(channel.id, [])
        if not transcript_lines:
            transcript_lines = ["No messages were recorded for this ticket."]

        ticket_type = self.ticket_type_for_channel(channel)
        transcript_text = "\n".join(transcript_lines)
        transcript_file = discord.File(
            io.BytesIO(transcript_text.encode("utf-8")),
            filename=f"{channel.name}-transcript.txt",
        )

        await log_channel.send(
            embed=build_transcript_embed(
                user=user,
                closer=closer,
                reason=reason,
                ticket_type=ticket_type,
                claimer_id=claimed_by.get(channel.id),
            ),
            file=transcript_file,
        )

    async def close_ticket(
        self, channel: discord.TextChannel, closer: discord.abc.User, reason: str
    ) -> None:
        user_id = channel_to_user.get(channel.id)
        if user_id is None:
            await channel.send(
                embed=build_status_embed(
                    "No Linked User",
                    "I could not find a linked user for this ticket.",
                )
            )
            return

        user = self.get_user(user_id) or await self.fetch_user(user_id)
        add_log_entry(
            channel.id,
            f"Staff {closer}",
            f"Closed ticket. Reason: {reason}",
        )

        try:
            await user.send(
                embed=build_status_embed(
                    "Ticket Closed",
                    f"Your ticket has been closed by the support team.\n\nReason: {reason}",
                )
            )
        except discord.Forbidden:
            pass

        await self.send_transcript_log(channel, user, closer, reason)

        claimed_by.pop(channel.id, None)
        channel_to_user.pop(channel.id, None)
        user_to_channel.pop(user_id, None)
        ticket_logs.pop(channel.id, None)
        await channel.delete(reason=f"Modmail ticket closed by {closer}")

    def other_claimer_has_ticket(self, channel_id: int, author_id: int) -> bool:
        claimer_id = claimed_by.get(channel_id)
        return claimer_id is not None and claimer_id != author_id


intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.message_content = True

bot = ModmailBot(command_prefix=PREFIX, intents=intents)


@bot.command(name="reply")
async def reply(ctx: commands.Context, *, message_text: str) -> None:
    if not is_ticket_channel(ctx.channel):
        await ctx.send(
            embed=build_status_embed(
                "Wrong Channel",
                "This command can only be used inside ticket channels.",
            )
        )
        return

    if bot.other_claimer_has_ticket(ctx.channel.id, ctx.author.id):
        await ctx.send(
            embed=build_status_embed(
                "Ticket Claimed",
                "This ticket is claimed by another staff member.",
            )
        )
        return

    user_id = channel_to_user.get(ctx.channel.id)
    if user_id is None:
        await ctx.send(
            embed=build_status_embed(
                "No Linked User",
                "I could not find a linked user for this ticket.",
            )
        )
        return

    user = bot.get_user(user_id) or await bot.fetch_user(user_id)
    sent = await bot.send_user_dm(user, ctx.author, message_text)
    if not sent:
        await ctx.send(
            embed=build_status_embed(
                "DM Failed",
                "I could not send a DM to that user.",
            )
        )
        return

    add_log_entry(
        ctx.channel.id,
        f"Staff {ctx.author}",
        message_text,
        ctx.message.created_at,
    )
    await ctx.send(
        embed=build_status_embed(
            "Reply Sent",
            "Your reply has been sent to the user.",
        )
    )


@bot.command(name="close")
async def close(ctx: commands.Context, *, reason: str) -> None:
    if not is_ticket_channel(ctx.channel):
        await ctx.send(
            embed=build_status_embed(
                "Wrong Channel",
                "This command can only be used inside ticket channels.",
            )
        )
        return

    if bot.other_claimer_has_ticket(ctx.channel.id, ctx.author.id):
        await ctx.send(
            embed=build_status_embed(
                "Ticket Claimed",
                "This ticket is claimed by another staff member.",
            )
        )
        return

    await bot.close_ticket(ctx.channel, ctx.author, reason)


@bot.command(name="claim")
async def claim(ctx: commands.Context) -> None:
    if not is_ticket_channel(ctx.channel):
        await ctx.send(
            embed=build_status_embed(
                "Wrong Channel",
                "This command can only be used inside ticket channels.",
            )
        )
        return

    current_claimer = claimed_by.get(ctx.channel.id)
    if current_claimer == ctx.author.id:
        await ctx.send(
            embed=build_status_embed(
                "Already Claimed",
                "You have already claimed this ticket.",
            )
        )
        return

    if current_claimer is not None:
        await ctx.send(
            embed=build_status_embed(
                "Already Claimed",
                f"This ticket is already claimed by <@{current_claimer}>.",
            )
        )
        return

    user_id = channel_to_user.get(ctx.channel.id)
    if user_id is None:
        await ctx.send(
            embed=build_status_embed(
                "No Linked User",
                "I could not find a linked user for this ticket.",
            )
        )
        return

    user = bot.get_user(user_id) or await bot.fetch_user(user_id)
    claimed_by[ctx.channel.id] = ctx.author.id
    await bot.update_claim_state(ctx.channel, ctx.author.id)
    await ctx.channel.edit(name=build_claimed_channel_name(user))

    add_log_entry(
        ctx.channel.id,
        "System",
        f"{ctx.author} claimed this ticket.",
        ctx.message.created_at,
    )
    await ctx.send(
        embed=build_status_embed(
            "Ticket Claimed",
            f"This ticket is now claimed by {ctx.author.mention}.",
        )
    )


@bot.command(name="block")
async def block(ctx: commands.Context) -> None:
    if not is_ticket_channel(ctx.channel):
        await ctx.send(
            embed=build_status_embed(
                "Wrong Channel",
                "This command can only be used inside ticket channels.",
            )
        )
        return

    if bot.other_claimer_has_ticket(ctx.channel.id, ctx.author.id):
        await ctx.send(
            embed=build_status_embed(
                "Ticket Claimed",
                "This ticket is claimed by another staff member.",
            )
        )
        return

    user_id = channel_to_user.get(ctx.channel.id)
    if user_id is None:
        await ctx.send(
            embed=build_status_embed(
                "No Linked User",
                "I could not find a linked user for this ticket.",
            )
        )
        return

    blocked_users.add(user_id)
    add_log_entry(
        ctx.channel.id,
        "System",
        f"{ctx.author} blocked user {user_id}.",
        ctx.message.created_at,
    )
    await ctx.send(
        embed=build_status_embed(
            "User Blocked",
            f"User `{user_id}` has been blocked from opening new tickets.",
        )
    )


@reply.error
async def reply_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            embed=build_status_embed(
                "Usage",
                f"Use `{PREFIX}reply <message>`.",
            )
        )
        return
    raise error


@close.error
async def close_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            embed=build_status_embed(
                "Usage",
                f"Use `{PREFIX}close <reason>`.",
            )
        )
        return
    raise error


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN in .env before running the bot.")

    if not MODMAIL_CATEGORY_ID:
        raise RuntimeError("Set MODMAIL_CATEGORY_ID in .env before running the bot.")

    if not LOG_CHANNEL_ID:
        raise RuntimeError("Set LOG_CHANNEL_ID in .env before running the bot.")

    if not ALLOWED_GUILDS:
        raise RuntimeError("Set ALLOWED_GUILDS in .env before running the bot.")

    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
