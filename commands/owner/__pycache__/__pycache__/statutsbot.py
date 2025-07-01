# commands/status_cog.py
import discord
from discord.ext import commands

import elda  # pour accéder et modifier elda.STATUS_MESSAGE

class StatusCog(commands.Cog):
    """Cog pour changer dynamiquement le statut du bot via une commande prefix (owner only)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="setstatus",
        aliases=["ss"],
        help="(Owner only) Change le statut du bot en live."
    )
    @commands.is_owner()
    async def setstatus(self, ctx: commands.Context, *, nouveau_statut: str):
        """
        - Vérifie que c’est bien l’owner (via @commands.is_owner).
        - Met à jour elda.STATUS_MESSAGE et la présence du bot immédiatement.
        """
        # Mise à jour de la constante dans le module elda
        elda.STATUS_MESSAGE = nouveau_statut
        # Mise à jour de la présence sur Discord
        await self.bot.change_presence(activity=discord.CustomActivity(elda.STATUS_MESSAGE))
        # Réponse pour l'owner
        await ctx.reply(
            f"✅ Nouveau statut : « {elda.STATUS_MESSAGE} »", mention_author=False
        )

    @setstatus.error
    async def setstatus_error(self, ctx: commands.Context, error: commands.CommandError):
        """Gestion des erreurs pour la commande setstatus."""
        if isinstance(error, commands.NotOwner):
            # Permission refusée
            await ctx.reply(
                "❌ Vous n'avez pas la permission d'utiliser cette commande.",
                mention_author=False
            )
        else:
            # Autres erreurs
            await ctx.reply(
                f"❌ Une erreur est survenue : {error}",
                mention_author=False
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(StatusCog(bot))
