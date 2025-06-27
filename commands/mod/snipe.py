#ce code sert a récupéré le dernier message supprimé d'un salon. c'est quand meme
# utiles si vous n'aviez pas programé de log pour sa.

import datetime
import discord
from discord import app_commands
from discord.ext import commands
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
)

class Snipe(commands.Cog):
    """Récupère et affiche le dernier message supprimé dans un salon."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Mapping channel_id -> (Message, deletion_time)
        if not hasattr(bot, "deleted_messages"):
            bot.deleted_messages: dict[int, tuple[discord.Message, datetime.datetime]] = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # Ignorez les suppressions en DM
        if message.guild is None:
            return
        # Stocke le message + timestamp local
        self.bot.deleted_messages[message.channel.id] = (
            message,
            datetime.datetime.now()
        )

    @app_commands.command(
        name="snipe",
        description="Récupère le dernier message supprimé de ce salon."
    )
    @app_commands.default_permissions(ban_members=True)
    async def snipe(self, interaction: discord.Interaction):
        # Vérification de permission
        if not interaction.user.guild_permissions.ban_members:
            embed = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                description="🚫 Vous n'avez pas la permission d'utiliser cette commande.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Défer pour pouvoir follow-up
        await interaction.response.defer()

        entry = self.bot.deleted_messages.get(interaction.channel.id)
        if not entry:
            embed = discord.Embed(
                description="🚫 Aucun message supprimé trouvé dans ce salon.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.followup.send(embed=embed, ephemeral=True)

        msg, deleted_at = entry

        # Construction de l'embed résultat
        embed = discord.Embed(
            color=EMBED_COLOR,
            description=msg.content or "_(Pas de contenu textuel)_"
        )
        embed.set_author(
            name=f"{msg.author} ({msg.author.id})",
            icon_url=msg.author.display_avatar.url
        )

        # Footer avec heure de suppression (locale)
        time_str = deleted_at.strftime("%H:%M:%S")
        embed.set_footer(
            text=f"{EMBED_FOOTER_TEXT} • Supprimé à {time_str}",
            icon_url=EMBED_FOOTER_ICON_URL
        )

        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Snipe(bot))
