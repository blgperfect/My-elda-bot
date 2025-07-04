# commands/moderation/clear.py

import discord
from discord import app_commands
from discord.ext import commands

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    EMOJIS,
    MESSAGES,
)

class Clear(commands.Cog):
    """Cog de modération : suppression de messages"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="clear",
        description="Supprime un nombre spécifié de messages dans ce canal",
    )
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(
        amount="Nombre de messages à supprimer (entre 1 et 100)"
    )
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: int,
    ) -> None:
        # On defer pour rester dans les clous de Discord
        await interaction.response.defer(ephemeral=True)

        # Validation de l'argument
        if not 1 <= amount <= 100:
            embed = discord.Embed(
                title=MESSAGES["INVALID_ARGUMENT"],
                description="Le nombre doit être compris entre 1 et 100.",
                color=EMBED_COLOR,
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.followup.send(embed=embed)

        # Suppression des messages
        deleted = await interaction.channel.purge(limit=amount)

        # Construction de l'embed de confirmation
        embed = discord.Embed(
            title=f"{EMOJIS['SUCCESS']} Suppression effectuée",
            description=f"{len(deleted)} message(s) supprimé(s) avec succès.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        # Ne pas planter si le serveur n’a pas d’icône
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        # Sinon, on peut laisser sans thumbnail ou utiliser une icône par défaut :
        # embed.set_thumbnail(url=EMBED_FOOTER_ICON_URL)

        embed.add_field(name="Canal", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        await interaction.followup.send(embed=embed)

    @clear.error
    async def clear_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        # Si l'erreur arrive avant defer, on tente de defer à nouveau
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # Choix du titre et description selon l’erreur
        if isinstance(error, app_commands.MissingPermissions):
            title = MESSAGES["PERMISSION_ERROR"]
            desc  = "Vous devez avoir la permission **Gérer les messages**."
        elif isinstance(error, app_commands.BotMissingPermissions):
            title = MESSAGES["BOT_PERMISSION_ERROR"]
            desc  = "Le bot a besoin de la permission **Gérer les messages**."
        else:
            title = MESSAGES["INTERNAL_ERROR"]
            desc  = None

        embed = discord.Embed(
            title=title,
            description=desc,
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        # Même vérification pour le thumbnail en cas d’erreur
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Clear(bot))
