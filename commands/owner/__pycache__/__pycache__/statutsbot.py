# commands/status_cog.py
import discord
from discord import app_commands
from discord.ext import commands

import elda  # pour accéder et modifier elda.STATUS_MESSAGE
from config.params import BOT_OWNER_ID

# Check pour slash commands réservée à l'owner
def owner_only(interaction: discord.Interaction) -> bool:
    if interaction.user.id != BOT_OWNER_ID:
        raise app_commands.CheckFailure("Vous n'êtes pas propriétaire du bot.")
    return True

class StatusCog(commands.Cog):
    """Cog pour changer dynamiquement le statut du bot via une commande slash (owner only)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setstatus",
        description="(Owner only) Change le statut du bot en live."
    )
    @app_commands.check(owner_only)
    async def setstatus(self, interaction: discord.Interaction, nouveau_statut: str):
        """
        - Vérifie que c’est bien l’owner (via BOT_OWNER_ID).
        - Met à jour STATUS_MESSAGE dans elda et la présence du bot immédiatement.
        """
        # Mise à jour de la constante dans le module elda
        elda.STATUS_MESSAGE = nouveau_statut
        # Mise à jour de la présence sur Discord
        await self.bot.change_presence(activity=discord.CustomActivity(elda.STATUS_MESSAGE))
        # Réponse éphémère pour l'owner uniquement
        await interaction.response.send_message(
            f"✅ Nouveau statut : « {elda.STATUS_MESSAGE} »", ephemeral=True
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Gestion des erreurs pour les commandes de ce cog."""
        if isinstance(error, app_commands.CheckFailure):
            # Permission refusée
            await interaction.response.send_message(
                "❌ Vous n'avez pas la permission d'utiliser cette commande.",
                ephemeral=True
            )
        else:
            # Autres erreurs
            await interaction.response.send_message(
                f"❌ Une erreur est survenue : {error}",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(StatusCog(bot))
