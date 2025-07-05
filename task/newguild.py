import discord
from discord.ext import commands
from discord import Embed, Webhook
from datetime import datetime
import aiohttp
import logging

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    WEBHOOK_JOIN_URL,
)

logger = logging.getLogger(__name__)

class GuildJoinNotifier(commands.Cog):
    """Cog pour notifier via webhook lorsqu'un nouveau serveur ajoute le bot"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Construction de l'embed de notification
        embed = Embed(
            title="🤝 Un nouveau serveur a ajouté Elda !",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🌐 Nom du serveur", value=guild.name, inline=False)
        embed.add_field(name="🆔 ID du serveur", value=str(guild.id), inline=True)
        embed.add_field(name="👥 Membres", value=str(guild.member_count), inline=True)

        # Création d'une invitation permanente
        try:
            channel = guild.system_channel or next(
                (c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite),
                None
            )
            if channel:
                invite = await channel.create_invite(max_age=0, max_uses=0, unique=False)
                embed.add_field(name="🔗 Invitation (permanente)", value=invite.url, inline=False)
        except Exception as e:
            logger.error(f"Erreur création invitation sur guild_join: {e}")

        # Total de serveurs actuels
        total = len(self.bot.guilds)
        embed.add_field(name="📊 Total serveurs", value=str(total), inline=False)

        # Envoi via webhook
        try:
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(WEBHOOK_JOIN_URL, session=session)
                await webhook.send(embed=embed)
        except Exception as e:
            logger.error(f"Erreur envoi join webhook: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(GuildJoinNotifier(bot))
