import io
from typing import Collection, Optional

import discord
from discord.ext import commands

from .commands import register_commands
from .constants import DEFAULT_TICKET_TYPE, PREFIX
from .embeds import (
    build_staff_message_embed,
    build_status_embed,
    build_transcript_embed,
    build_user_info_embed,
    build_user_message_embed,
)
from .state import ModmailState
from .tickets import (
    add_log_entry,
    build_channel_topic,
    build_ticket_channel_name,
    format_message_text,
    is_ticket_channel,
    parse_channel_topic,
    serialize_message,
)
from .views import SupportTypeView


class ModmailBot(commands.Bot):
    def __init__(
        self,
        *,
        embed_color: int,
        modmail_category_id: int,
        log_channel_id: int,
        allowed_guild_ids: Collection[int],
    ) -> None:
        intents = discord.Intents.default()
        intents.messages = True
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=PREFIX, intents=intents)
        self.embed_color = embed_color
        self.modmail_category_id = modmail_category_id
        self.log_channel_id = log_channel_id
        self.allowed_guild_ids = set(allowed_guild_ids)
        self.state = ModmailState()
        register_commands(self)

    async def setup_hook(self) -> None:
        self.add_view(SupportTypeView(self.handle_ticket_selection))

    async def on_ready(self) -> None:
        self.rebuild_ticket_maps()
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("Button-based modmail bot is ready.")

    def get_modmail_category(self) -> Optional[discord.CategoryChannel]:
        category = self.get_channel(self.modmail_category_id)
        if not isinstance(category, discord.CategoryChannel):
            return None

        if category.guild.id not in self.allowed_guild_ids:
            return None

        return category

    def get_log_channel(self) -> Optional[discord.TextChannel]:
        channel = self.get_channel(self.log_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None

        if channel.guild.id not in self.allowed_guild_ids:
            return None

        return channel

    def rebuild_ticket_maps(self) -> None:
        self.state.user_to_channel.clear()
        self.state.channel_to_user.clear()
        self.state.claimed_by.clear()

        category = self.get_modmail_category()
        if category is None:
            print("Warning: Modmail category not found in an allowed guild.")
            return

        for channel in category.text_channels:
            data = parse_channel_topic(channel.topic)
            if data is None:
                continue

            user_id = data["user_id"]
            self.state.user_to_channel[user_id] = channel.id
            self.state.channel_to_user[channel.id] = user_id
            self.state.ticket_logs.setdefault(channel.id, [])

            claimer_id = data["claimer_id"]
            if claimer_id is not None:
                self.state.claimed_by[channel.id] = claimer_id

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if message.guild is None:
            await self.handle_user_dm(message)
            return

        if message.guild.id not in self.allowed_guild_ids:
            return

        if is_ticket_channel(
            self.state,
            message.channel,
            self.modmail_category_id,
            self.allowed_guild_ids,
        ) and not message.content.startswith(PREFIX):
            await self.forward_staff_message(message)

        await self.process_commands(message)

    async def handle_user_dm(self, message: discord.Message) -> None:
        if message.author.id in self.state.blocked_users:
            return

        ticket_channel = self.get_existing_ticket_channel(message.author.id)
        payload = serialize_message(message)

        if ticket_channel is not None:
            await ticket_channel.send(
                embed=build_user_message_embed(
                    message.author,
                    payload,
                    self.embed_color,
                )
            )
            add_log_entry(
                self.state,
                ticket_channel.id,
                f"User {message.author}",
                format_message_text(payload["content"], payload["attachments"]),
                payload["created_at"],
            )
            return

        self.state.pending_messages.setdefault(message.author.id, []).append(payload)

        if len(self.state.pending_messages[message.author.id]) == 1:
            await message.author.send(
                embed=build_status_embed(
                    self.embed_color,
                    "TVD Support",
                    "What type of support do you need?",
                ),
                view=SupportTypeView(self.handle_ticket_selection),
            )
            return

        await message.author.send(
            embed=build_status_embed(
                self.embed_color,
                "Support Type Needed",
                "Please choose one of the support buttons above so I can create your ticket.",
            )
        )

    async def handle_ticket_selection(
        self, interaction: discord.Interaction, ticket_type: str
    ) -> None:
        user = interaction.user

        if user.id in self.state.blocked_users:
            await interaction.followup.send(
                embed=build_status_embed(
                    self.embed_color,
                    "Blocked",
                    "You are blocked from opening modmail tickets.",
                )
            )
            return

        existing_channel = self.get_existing_ticket_channel(user.id)
        if existing_channel is not None:
            await interaction.followup.send(
                embed=build_status_embed(
                    self.embed_color,
                    "Ticket Already Open",
                    "You already have an open ticket. Please continue messaging here.",
                )
            )
            return

        queued_messages = self.state.pending_messages.pop(user.id, None)
        if not queued_messages:
            await interaction.followup.send(
                embed=build_status_embed(
                    self.embed_color,
                    "No Pending Message",
                    "Send me a DM first so I can create your ticket.",
                )
            )
            return

        channel = await self.create_ticket_channel(user, ticket_type)
        if channel is None:
            self.state.pending_messages[user.id] = queued_messages
            await interaction.followup.send(
                embed=build_status_embed(
                    self.embed_color,
                    "Configuration Error",
                    "I could not find the modmail category in an allowed guild.",
                )
            )
            return

        if interaction.message is not None:
            await interaction.message.edit(
                view=SupportTypeView(self.handle_ticket_selection, disabled=True)
            )

        await channel.send(embed=build_user_info_embed(user, self.embed_color))

        add_log_entry(
            self.state,
            channel.id,
            "System",
            f"Ticket created for {user} ({user.id}) as {ticket_type}.",
        )

        for payload in queued_messages:
            await channel.send(
                embed=build_user_message_embed(user, payload, self.embed_color)
            )
            add_log_entry(
                self.state,
                channel.id,
                f"User {user}",
                format_message_text(payload["content"], payload["attachments"]),
                payload["created_at"],
            )

        await user.send(
            embed=build_status_embed(
                self.embed_color,
                "Ticket Created",
                "Your ticket has been created!",
            )
        )

    def get_existing_ticket_channel(self, user_id: int) -> Optional[discord.TextChannel]:
        channel_id = self.state.user_to_channel.get(user_id)
        if channel_id is not None:
            channel = self.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                if (
                    channel.category_id == self.modmail_category_id
                    and channel.guild.id in self.allowed_guild_ids
                ):
                    return channel

            self.state.user_to_channel.pop(user_id, None)
            self.state.channel_to_user.pop(channel_id, None)
            self.state.claimed_by.pop(channel_id, None)

        category = self.get_modmail_category()
        if category is None:
            return None

        for channel in category.text_channels:
            data = parse_channel_topic(channel.topic)
            if data is None or data["user_id"] != user_id:
                continue

            self.state.user_to_channel[user_id] = channel.id
            self.state.channel_to_user[channel.id] = user_id
            self.state.ticket_logs.setdefault(channel.id, [])

            claimer_id = data["claimer_id"]
            if claimer_id is not None:
                self.state.claimed_by[channel.id] = claimer_id

            return channel

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
        self.state.user_to_channel[user.id] = channel.id
        self.state.channel_to_user[channel.id] = user.id
        self.state.ticket_logs[channel.id] = []
        return channel

    async def forward_staff_message(self, message: discord.Message) -> None:
        user_id = self.state.channel_to_user.get(message.channel.id)
        if user_id is None:
            return

        claimer_id = self.state.claimed_by.get(message.channel.id)
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
                self.state,
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
                await dm_channel.send(
                    embed=build_staff_message_embed(
                        author,
                        description,
                        self.embed_color,
                    )
                )
            return True
        except discord.Forbidden:
            return False

    def ticket_type_for_channel(self, channel: discord.TextChannel) -> str:
        data = parse_channel_topic(channel.topic)
        if data is None:
            return DEFAULT_TICKET_TYPE
        return data["ticket_type"]

    async def update_claim_state(
        self, channel: discord.TextChannel, claimer_id: Optional[int]
    ) -> None:
        user_id = self.state.channel_to_user.get(channel.id)
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

        transcript_lines = self.state.ticket_logs.get(channel.id, [])
        if not transcript_lines:
            transcript_lines = ["No messages were recorded for this ticket."]

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
                ticket_type=self.ticket_type_for_channel(channel),
                claimer_id=self.state.claimed_by.get(channel.id),
                embed_color=self.embed_color,
            ),
            file=transcript_file,
        )

    async def close_ticket(
        self, channel: discord.TextChannel, closer: discord.abc.User, reason: str
    ) -> None:
        user_id = self.state.channel_to_user.get(channel.id)
        if user_id is None:
            await channel.send(
                embed=build_status_embed(
                    self.embed_color,
                    "No Linked User",
                    "I could not find a linked user for this ticket.",
                )
            )
            return

        user = self.get_user(user_id) or await self.fetch_user(user_id)
        add_log_entry(
            self.state,
            channel.id,
            f"Staff {closer}",
            f"Closed ticket. Reason: {reason}",
        )

        try:
            await user.send(
                embed=build_status_embed(
                    self.embed_color,
                    "Ticket Closed",
                    f"Your ticket has been closed by the support team.\n\nReason: {reason}",
                )
            )
        except discord.Forbidden:
            pass

        await self.send_transcript_log(channel, user, closer, reason)

        self.state.claimed_by.pop(channel.id, None)
        self.state.channel_to_user.pop(channel.id, None)
        self.state.user_to_channel.pop(user_id, None)
        self.state.ticket_logs.pop(channel.id, None)
        await channel.delete(reason=f"Modmail ticket closed by {closer}")

    def other_claimer_has_ticket(self, channel_id: int, author_id: int) -> bool:
        claimer_id = self.state.claimed_by.get(channel_id)
        return claimer_id is not None and claimer_id != author_id


def create_bot(
    *,
    embed_color: int,
    modmail_category_id: int,
    log_channel_id: int,
    allowed_guild_ids: Collection[int],
) -> ModmailBot:
    return ModmailBot(
        embed_color=embed_color,
        modmail_category_id=modmail_category_id,
        log_channel_id=log_channel_id,
        allowed_guild_ids=allowed_guild_ids,
    )
