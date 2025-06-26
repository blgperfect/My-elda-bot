# commands/avatar.py
import discord
from discord import app_commands
from discord.ext import commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, EMOJIS

class AvatarView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed]):
        super().__init__(timeout=60)  # active 60s
        self.embeds = embeds
        self.index = 0
        # Ajoute le bouton uniquement si plusieurs pages
        if len(embeds) > 1:
            self.add_item(self.NextButton())

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(style=discord.ButtonStyle.secondary, emoji=EMOJIS.get("ARROW", "➡️"))

        async def callback(self, interaction: discord.Interaction):
            view: AvatarView = self.view  # type: ignore
            view.index = (view.index + 1) % len(view.embeds)
            embed = view.embeds[view.index]
            # Met à jour le bouton (flèche gauche/droite selon page)
            if view.index == 0:
                # Retour à la première page : garde flèche droite
                self.emoji = EMOJIS.get("ARROW", "➡️")
            else:
                # Page suivante (index=1) : bouton retour
                self.emoji = EMOJIS.get("BACK", "⬅️")
            await interaction.response.edit_message(embed=embed, view=view)

class Avatar(commands.Cog):
    """Commande slash /avatar pour afficher l'avatar d'un membre."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="avatar",
        description="Affiche l'avatar d'un membre (serveur & global si présents)."
    )
    @app_commands.describe(member="Le membre dont vous voulez voir l'avatar")
    async def avatar(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None
    ):
        target = member or interaction.user

        # Récupère les URLs
        global_url = target.avatar.url if target.avatar else None
        server_url = getattr(target, "guild_avatar", None)
        server_url = server_url.url if server_url else None

        # Crée les embeds disponibles
        embeds: list[discord.Embed] = []
        title = f"Avatar de {target.mention}"

        # Embed du server avatar si présent
        if server_url:
            e = discord.Embed(
                title=title,
                description="**Avatar de serveur**",
                color=EMBED_COLOR
            )
            e.set_image(url=server_url)
            e.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            embeds.append(e)

        # Embed de l'avatar global si présent
        if global_url:
            e = discord.Embed(
                title=title,
                description="**Avatar global**" if server_url else None,
                color=EMBED_COLOR
            )
            e.set_image(url=global_url)
            e.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            embeds.append(e)

        # Si au moins un embed
        if embeds:
            view = AvatarView(embeds)
            await interaction.response.send_message(embed=embeds[0], view=view)
        else:
            # Cas improbable : pas d'avatar du tout
            await interaction.response.send_message(
                f"{EMOJIS.get('WARNING', '⚠️')} Impossible de trouver un avatar pour {target.mention}.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Avatar(bot))
