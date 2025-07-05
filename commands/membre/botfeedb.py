import discord
from discord.ext import commands
from discord import app_commands, Embed, Webhook
from discord.ui import View, Button
from datetime import datetime
import platform
import re
import aiohttp
import logging

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    BOT_INVITE,
    BOT_OWNER_ID,
    WEBHOOK_FEEDBACK_URL,
)

URL_REGEX = re.compile(r"^https?://")
logger = logging.getLogger(__name__)

class BotInfoCog(commands.Cog):
    """Cog pour les commandes /bot info et /bot feedback"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    # Groupe slash /bot
    group = app_commands.Group(name="bot", description="Commandes liées au bot")

    @group.command(name="info", description="Affiche des informations sur le bot 📊")
    async def info(self, interaction: discord.Interaction):
        # Calcul de l'uptime
        delta = datetime.utcnow() - self.start_time
        days, rem = divmod(delta.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime = f"🕒 {int(days)}j {int(hours)}h {int(minutes)}m {int(seconds)}s"

        # Statistiques de slash commands
        total_slash = len(self.bot.tree.get_commands())
        total_guilds = len(self.bot.guilds)
        total_members = sum(g.member_count for g in self.bot.guilds)

        embed = Embed(title="🤖 • Bot Information", color=EMBED_COLOR)
        # Section GENERAL
        embed.add_field(name="🛠️ GENERAL", value="​", inline=False)
        embed.add_field(name="🤖 Nom",            value=self.bot.user.name,              inline=True)
        embed.add_field(name="🆔 ID",             value=self.bot.user.id,                inline=True)
        embed.add_field(name="👤 Développeur",    value="xxmissr",                       inline=True)
        embed.add_field(name="⚙️ Slash Commands",value=str(total_slash),                inline=True)
        embed.add_field(name="🌐 Serveurs",       value=str(total_guilds),               inline=True)
        embed.add_field(name="👥 Membres totaux", value=str(total_members),              inline=True)
        embed.add_field(
            name="📅 Créé le",
            value=self.bot.user.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            inline=True
        )
        # Section SYSTÈME
        embed.add_field(name="​", value="​", inline=False)
        embed.add_field(name="💻 SYSTÈME", value="​", inline=False)
        embed.add_field(name="⌛ Uptime",    value=uptime,                       inline=True)
        embed.add_field(name="🐍 Python",    value=platform.python_version(),    inline=True)

        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # Bouton invite
        view = View()
        if isinstance(BOT_INVITE, str) and URL_REGEX.match(BOT_INVITE):
            view.add_item(Button(label="🔗 Inviter le bot", url=BOT_INVITE))
        else:
            logger.warning(f"BOT_INVITE invalide: {BOT_INVITE}")

        await interaction.response.send_message(embed=embed, view=view)

    @group.command(name="feedback", description="Envoyer un feedback au développeur 💬")
    @app_commands.describe(message="Votre message de feedback")
    async def feedback(self, interaction: discord.Interaction, message: str):
        # Construction de l'embed de feedback
        dm = Embed(title="💬 Nouveau Feedback", color=EMBED_COLOR)
        dm.add_field(
            name="👤 De",
            value=f"{interaction.user} ({interaction.user.id})",
            inline=False
        )
        # Info serveur si disponible
        if interaction.guild:
            dm.add_field(
                name="🌐 Serveur",
                value=f"{interaction.guild.name} ({interaction.guild.id})",
                inline=False
            )
            # Génération d'un lien d'invitation non-expirable
            try:
                channel = interaction.guild.system_channel or next((c for c in interaction.guild.text_channels if c.permissions_for(interaction.guild.me).create_instant_invite), None)
                if channel:
                    invite = await channel.create_invite(max_age=0, max_uses=0, unique=False)
                    dm.add_field(
                        name="🔗 Invitation (permanente)",
                        value=invite.url,
                        inline=False
                    )
            except Exception as e:
                logger.error(f"Erreur création invitation: {e}")

        dm.add_field(name="✉️ Message", value=message, inline=False)
        # Date locale
        local_date = interaction.created_at.astimezone()
        dm.add_field(
            name="📅 Date",
            value=local_date.strftime("%Y-%m-%d %H:%M:%S"),
            inline=False
        )
        dm.set_footer(text="Feedback reçu", icon_url=EMBED_FOOTER_ICON_URL)

        # Envoi via webhook
        try:
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(WEBHOOK_FEEDBACK_URL, session=session)
                await webhook.send(embed=dm)
        except Exception as e:
            logger.error(f"Erreur envoi feedback webhook: {e}")

        # Confirmation éphémère
        await interaction.response.send_message(
            "✅ Votre feedback a bien été envoyé au salon dédié !",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(BotInfoCog(bot))
