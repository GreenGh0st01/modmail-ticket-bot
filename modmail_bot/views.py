from typing import Awaitable, Callable

import discord


SelectionHandler = Callable[[discord.Interaction, str], Awaitable[None]]


class SupportTypeView(discord.ui.View):
    def __init__(self, on_select: SelectionHandler, disabled: bool = False) -> None:
        super().__init__(timeout=None)
        self.on_select = on_select
        for item in self.children:
            item.disabled = disabled

    async def handle_selection(
        self, interaction: discord.Interaction, ticket_type: str
    ) -> None:
        await interaction.response.defer()
        await self.on_select(interaction, ticket_type)

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
