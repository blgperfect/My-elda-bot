# commands/avatar.py
import discord
from discord import app_commands
from discord.ext import commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, EMOJIS

class AvatarView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed]):
        super().__init__(timeout=60)  # 60s avant expiration
        self.embeds = embeds
        self.index = 0
        # si plus d’une page, on ajoute le bouton
        if len(embeds) > 1:
            self.next_button = self.NextButton()
            self.add_item(self.next_button)

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                emoji=EMOJIS.get("ARROW", "➡️"),
                disabled=False,
            )

        async def callback(self, interaction: discord.Interaction):
            view: AvatarView = self.view  # type: ignore
            view.index = (view.index + 1) % len(view.embeds)
            embed = view.embeds[view.index]
            # bascule l'emoji
            if view.index == 0:
                self.emoji = EMOJIS.get("ARROW", "➡️")
            else:
                self.emoji = EMOJIS.get("BACK", "⬅️")
            await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        # désactive tous les boutons à l'expiration
        for item in self.children:
            item.disabled = True
        # édite le message pour refléter la désactivation
        try:
            await self.message.edit(view=self)  # type: ignore
        except Exception:
            pass  # si échec, on ignore

class Avatar(commands.Cog):
    """Commande slash /avatar pour afficher l'avatar d'un membre."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="avatar",
        description="Affiche l'avatar d'un membre (serveur & global si disponibles)."
    )
    @app_commands.describe(member="Le membre dont vous voulez voir l'avatar")
    async def avatar(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None
    ):
        target = member or interaction.user

        # Récupère avatars
        global_url = getattr(target, "avatar", None)
        global_url = global_url.url if global_url else None

        server_url = getattr(target, "guild_avatar", None)
        server_url = server_url.url if server_url else None

        # si pas d’avatar du tout
        if not global_url and not server_url:
            return await interaction.response.send_message(
                f"{EMOJIS.get('WARNING', '⚠️')} Impossible de récupérer l'avatar de {target.mention}.",
                ephemeral=True
            )

        # titre
        title = f"Avatar de {target.mention}"
        embeds: list[discord.Embed] = []

        if server_url:
            e = discord.Embed(
                title=title,
                description="**Avatar de serveur**",
                color=EMBED_COLOR
            )
            e.set_image(url=server_url)
            e.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            embeds.append(e)

        if global_url:
            e = discord.Embed(
                title=title,
                description="**Avatar global**" if server_url else None,
                color=EMBED_COLOR
            )
            e.set_image(url=global_url)
            e.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            embeds.append(e)

        # envoi
        view = AvatarView(embeds)
        await interaction.response.send_message(embed=embeds[0], view=view)
        # on récupère le message pour pouvoir éditer à l'expiration
        view.message = await interaction.original_response()

async def setup(bot: commands.Bot):
    await bot.add_cog(Avatar(bot))
