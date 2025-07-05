import discord
from discord import Embed, app_commands
from discord.ext import commands
from datetime import datetime

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    BOT_OWNER_ID,
)

# Contrôle d'accès : uniquement le propriétaire
def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == BOT_OWNER_ID

# Libellés par type de message
ANNOUNCE_TYPES = {
    "annonce":     "📢 Annonce",
    "maintenance": "🛠️ Maintenance",
    "update":      "✨ Mise à jour",
    "changement":  "🔄 Changement",
}

class MaintenanceCog(commands.Cog):
    """Commande /maintenance pour diffuser un message important dans tous les serveurs"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="maintenance",
        description="Envoyer un message important (annonce, maintenance, update, changement) dans tous les serveurs"
    )
    @app_commands.check(is_owner)
    @app_commands.describe(
        type="Type de message",
        message="Contenu du message à diffuser"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Annonce",     value="annonce"),
            app_commands.Choice(name="Maintenance", value="maintenance"),
            app_commands.Choice(name="Mise à jour", value="update"),
            app_commands.Choice(name="Changement",  value="changement"),
        ]
    )
    async def maintenance(
        self,
        interaction: discord.Interaction,
        type: app_commands.Choice[str],
        message: str
    ):
        """Diffuse un embed uniforme (couleur du bot) dans chaque serveur."""
        title = ANNOUNCE_TYPES[type.value]
        embed = Embed(
            title=title,
            description=message,
            color=EMBED_COLOR,  # utilisation de votre couleur unique
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        sent, failed = 0, 0
        for guild in self.bot.guilds:
            # Sélection du canal : system_channel ou premier canal texte envoyable
            channel = (
                guild.system_channel
                if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages
                else discord.utils.find(
                    lambda c: (
                        isinstance(c, discord.TextChannel)
                        and c.permissions_for(guild.me).send_messages
                    ),
                    guild.text_channels
                )
            )
            if not channel:
                failed += 1
                continue

            try:
                await channel.send(embed=embed)
                sent += 1
            except Exception:
                failed += 1

        # Retour au propriétaire
        await interaction.response.send_message(
            f"✅ Message envoyé sur **{sent}** serveurs."
            + (f" ❌ Échecs sur **{failed}** serveurs." if failed else ""),
            ephemeral=True
        )

    @maintenance.error
    async def maintenance_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ Accès refusé.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Une erreur est survenue.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MaintenanceCog(bot))
