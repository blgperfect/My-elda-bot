import math
import logging
from datetime import datetime

import discord
from discord import Embed, app_commands
from discord.ext import commands

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    BOT_OWNER_ID,
)

# Logger configuration
logger = logging.getLogger(__name__)


def is_owner(interaction: discord.Interaction) -> bool:
    """Vérifie si l'utilisateur est le propriétaire du bot."""
    return interaction.user.id == BOT_OWNER_ID


def build_stats_embed(view: "BotStatPaginationView") -> Embed:
    """Construit un embed de statistiques pour la page actuelle avec mise en forme améliorée."""
    total_servers = len(view.bot.guilds)
    total_members = sum(g.member_count for g in view.bot.guilds)
    page = view.current_page + 1
    total_pages = view.total_pages()

    embed = Embed(
        title=f"📊 Statistiques du Bot — Page {page}/{total_pages}",
        color=EMBED_COLOR,
        timestamp=datetime.utcnow()
    )
    # Informations générales
    embed.add_field(name="🌐 Serveurs totaux", value=str(total_servers), inline=True)
    embed.add_field(name="👥 Membres totaux", value=str(total_members), inline=True)
    embed.add_field(name="────", value="────", inline=False)

    # Détail des serveurs
    start = view.current_page * view.items_per_page
    end = start + view.items_per_page
    page_guilds = view.sorted_guilds[start:end]

    if page_guilds:
        for guild in page_guilds:
            owner = guild.owner.name if guild.owner else "Inconnu"
            embed.add_field(
                name=f"{guild.name} ({guild.id})",
                value=f"👥 {guild.member_count} • 🏷️ {owner}",
                inline=False
            )
    else:
        embed.add_field(name="Aucune donnée", value="Aucun serveur à afficher.", inline=False)

    # Esthétique
    if view.bot.user.avatar:
        embed.set_thumbnail(url=view.bot.user.avatar.url)
    embed.set_footer(text=f"{EMBED_FOOTER_TEXT} | Page {page}/{total_pages}", icon_url=EMBED_FOOTER_ICON_URL)
    return embed


class BotStatPaginationView(discord.ui.View):
    """Vue interactive pour naviguer dans les statistiques des serveurs."""

    def __init__(self, bot: commands.Bot, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.items_per_page = 10
        self.current_page = 0
        self.sorted_guilds: list[discord.Guild] = []

    def total_pages(self) -> int:
        """Retourne le nombre total de pages."""
        count = len(self.sorted_guilds)
        return max(1, math.ceil(count / self.items_per_page))

    async def refresh_data(self) -> None:
        """Trie les guildes par taille et met à jour les états de boutons."""
        self.sorted_guilds = sorted(
            self.bot.guilds, key=lambda g: g.member_count, reverse=True
        )
        self._update_buttons()

    def _update_buttons(self) -> None:
        """Active ou désactive les boutons selon la page actuelle."""
        total = self.total_pages()
        for btn in (b for b in self.children if isinstance(b, discord.ui.Button)):
            if btn.custom_id == "prev":
                btn.disabled = (self.current_page <= 0)
            elif btn.custom_id == "next":
                btn.disabled = (self.current_page >= total - 1)

    @discord.ui.button(label="◀️ Précédent", style=discord.ButtonStyle.primary, custom_id="prev")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_stats_embed(self), view=self)

    @discord.ui.button(label="🔄 Rafraîchir", style=discord.ButtonStyle.secondary, custom_id="refresh")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.refresh_data()
        await interaction.response.edit_message(embed=build_stats_embed(self), view=self)

    @discord.ui.button(label="Suivant ▶️", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = min(self.total_pages() - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_stats_embed(self), view=self)


class BotStatCog(commands.Cog):
    """Cog proposant la commande /botstat réservée au propriétaire du bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="botstat", description="Affiche les statistiques paginées du bot")
    @app_commands.check(is_owner)
    async def botstat(self, interaction: discord.Interaction) -> None:
        """Commande owners-only pour afficher les stats du bot avec pagination."""
        view = BotStatPaginationView(self.bot)
        await view.refresh_data()
        embed = build_stats_embed(view)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @botstat.error
    async def botstat_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Gestion des erreurs pour /botstat."""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True
            )
        else:
            logger.exception("Erreur inattendue dans /botstat", exc_info=error)
            await interaction.response.send_message(
                "⚠️ Une erreur est survenue lors de l'exécution de la commande.", ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotStatCog(bot))
