from typing import TYPE_CHECKING

from discord.ext import commands

from .constants import PREFIX
from .embeds import build_status_embed
from .tickets import add_log_entry, build_claimed_channel_name, is_ticket_channel

if TYPE_CHECKING:
    from .bot import ModmailBot


def register_commands(bot: "ModmailBot") -> None:
    @bot.command(name="reply")
    async def reply(ctx: commands.Context, *, message_text: str) -> None:
        if not is_ticket_channel(
            bot.state,
            ctx.channel,
            bot.modmail_category_id,
            bot.allowed_guild_ids,
        ):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Wrong Channel",
                    "This command can only be used inside ticket channels.",
                )
            )
            return

        if bot.other_claimer_has_ticket(ctx.channel.id, ctx.author.id):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Ticket Claimed",
                    "This ticket is claimed by another staff member.",
                )
            )
            return

        user_id = bot.state.channel_to_user.get(ctx.channel.id)
        if user_id is None:
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
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
                    bot.embed_color,
                    "DM Failed",
                    "I could not send a DM to that user.",
                )
            )
            return

        add_log_entry(
            bot.state,
            ctx.channel.id,
            f"Staff {ctx.author}",
            message_text,
            ctx.message.created_at,
        )
        await ctx.send(
            embed=build_status_embed(
                bot.embed_color,
                "Reply Sent",
                "Your reply has been sent to the user.",
            )
        )

    @bot.command(name="close")
    async def close(ctx: commands.Context, *, reason: str) -> None:
        if not is_ticket_channel(
            bot.state,
            ctx.channel,
            bot.modmail_category_id,
            bot.allowed_guild_ids,
        ):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Wrong Channel",
                    "This command can only be used inside ticket channels.",
                )
            )
            return

        if bot.other_claimer_has_ticket(ctx.channel.id, ctx.author.id):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Ticket Claimed",
                    "This ticket is claimed by another staff member.",
                )
            )
            return

        await bot.close_ticket(ctx.channel, ctx.author, reason)

    @bot.command(name="claim")
    async def claim(ctx: commands.Context) -> None:
        if not is_ticket_channel(
            bot.state,
            ctx.channel,
            bot.modmail_category_id,
            bot.allowed_guild_ids,
        ):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Wrong Channel",
                    "This command can only be used inside ticket channels.",
                )
            )
            return

        current_claimer = bot.state.claimed_by.get(ctx.channel.id)
        if current_claimer == ctx.author.id:
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Already Claimed",
                    "You have already claimed this ticket.",
                )
            )
            return

        if current_claimer is not None:
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Already Claimed",
                    f"This ticket is already claimed by <@{current_claimer}>.",
                )
            )
            return

        user_id = bot.state.channel_to_user.get(ctx.channel.id)
        if user_id is None:
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "No Linked User",
                    "I could not find a linked user for this ticket.",
                )
            )
            return

        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        bot.state.claimed_by[ctx.channel.id] = ctx.author.id
        await bot.update_claim_state(ctx.channel, ctx.author.id)
        await ctx.channel.edit(name=build_claimed_channel_name(user))

        add_log_entry(
            bot.state,
            ctx.channel.id,
            "System",
            f"{ctx.author} claimed this ticket.",
            ctx.message.created_at,
        )
        await ctx.send(
            embed=build_status_embed(
                bot.embed_color,
                "Ticket Claimed",
                f"This ticket is now claimed by {ctx.author.mention}.",
            )
        )

    @bot.command(name="block")
    async def block(ctx: commands.Context) -> None:
        if not is_ticket_channel(
            bot.state,
            ctx.channel,
            bot.modmail_category_id,
            bot.allowed_guild_ids,
        ):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Wrong Channel",
                    "This command can only be used inside ticket channels.",
                )
            )
            return

        if bot.other_claimer_has_ticket(ctx.channel.id, ctx.author.id):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "Ticket Claimed",
                    "This ticket is claimed by another staff member.",
                )
            )
            return

        user_id = bot.state.channel_to_user.get(ctx.channel.id)
        if user_id is None:
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
                    "No Linked User",
                    "I could not find a linked user for this ticket.",
                )
            )
            return

        bot.state.blocked_users.add(user_id)
        add_log_entry(
            bot.state,
            ctx.channel.id,
            "System",
            f"{ctx.author} blocked user {user_id}.",
            ctx.message.created_at,
        )
        await ctx.send(
            embed=build_status_embed(
                bot.embed_color,
                "User Blocked",
                f"User `{user_id}` has been blocked from opening new tickets.",
            )
        )

    @reply.error
    async def reply_error(ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=build_status_embed(
                    bot.embed_color,
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
                    bot.embed_color,
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
