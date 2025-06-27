# commands/mod/snipe.py

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
        # Initialisation du stockage si nécessaire
        if not hasattr(bot, "deleted_messages"):
            bot.deleted_messages: dict[int, discord.Message] = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # Ignorez les suppressions en DM
        if message.guild is None:
            return
        # Stockez le dernier message supprimé par salon
        self.bot.deleted_messages[message.channel.id] = message

    @app_commands.command(
        name="snipe",
        description="Récupère le dernier message supprimé de ce salon."
    )
    @app_commands.default_permissions(ban_members=True)
    async def snipe(self, interaction: discord.Interaction):
        # --- Vérification de permission (redondante mais permet un embed personnalisé) ---
        if not interaction.user.guild_permissions.ban_members:
            embed = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                description="🚫 Vous n'avez pas la permission d'utiliser cette commande.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # --- Préparation de la réponse ---
        await interaction.response.defer()

        msg = self.bot.deleted_messages.get(interaction.channel.id)
        if not msg:
            embed = discord.Embed(
                description="🚫 Aucun message supprimé trouvé dans ce salon.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.followup.send(embed=embed, ephemeral=True)

        # --- Construction de l'embed résultat ---
        embed = discord.Embed(
            color=EMBED_COLOR,
            description=msg.content or "_(Pas de contenu textuel)_"
        )
        embed.set_author(
            name=str(msg.author),
            icon_url=msg.author.display_avatar.url
        )
        embed.add_field(name="Salon", value=f"<#{msg.channel.id}>", inline=True)
        embed.add_field(name="ID du message", value=str(msg.id), inline=True)

        if msg.attachments:
            urls = "\n".join(att.url for att in msg.attachments)
            embed.add_field(name="Pièces jointes", value=urls, inline=False)

        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.timestamp = msg.created_at

        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Snipe(bot))
