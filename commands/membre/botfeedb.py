# commands/membre/bot_info_feedback.py

import discord
from discord.ext import commands
from discord import app_commands, Embed
from discord.ui import View, Button
from datetime import datetime
import platform
import re

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    BOT_INVITE,
    BOT_OWNER_ID,
)

URL_REGEX = re.compile(r"^https?://")

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

        # Statistiques
        total_commands = len(self.bot.commands)
        total_guilds   = len(self.bot.guilds)
        total_members  = sum(g.member_count for g in self.bot.guilds)

        embed = Embed(title="🤖 • Bot Information", color=EMBED_COLOR)
        # Section GENERAL
        embed.add_field(name="🛠️ GENERAL", value="\u200b", inline=False)
        embed.add_field(name="🤖 Nom",            value=self.bot.user.name, inline=True)
        embed.add_field(name="🆔 ID",             value=self.bot.user.id,   inline=True)
        embed.add_field(name="👤 Développeur",    value="xxmissr",           inline=True)
        embed.add_field(name="⚙️ Commandes",      value=str(total_commands), inline=True)
        embed.add_field(name="🌐 Serveurs",       value=str(total_guilds),   inline=True)
        embed.add_field(name="👥 Membres totaux", value=str(total_members),  inline=True)
        embed.add_field(
            name="📅 Créé le",
            value=self.bot.user.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            inline=True
        )
        # Section SYSTÈME
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="💻 SYSTÈME", value="\u200b", inline=False)
        embed.add_field(name="⌛ Uptime",    value=uptime,                    inline=True)
        embed.add_field(name="🐍 Python",    value=platform.python_version(), inline=True)

        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # Bouton invite
        view = View()
        if isinstance(BOT_INVITE, str) and URL_REGEX.match(BOT_INVITE):
            view.add_item(Button(label="🔗 Inviter le bot", url=BOT_INVITE))
        else:
            self.bot.logger.warning(f"BOT_INVITE invalide: {BOT_INVITE}")

        await interaction.response.send_message(embed=embed, view=view)

    @group.command(name="feedback", description="Envoyer un feedback au développeur 💬")
    @app_commands.describe(message="Votre message de feedback")
    async def feedback(self, interaction: discord.Interaction, message: str):
        # Envoi en DM au propriétaire
        owner = await self.bot.fetch_user(BOT_OWNER_ID)
        dm = Embed(
            title="💬 Nouveau Feedback",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        dm.add_field(name="👤 De",      value=f"{interaction.user} ({interaction.user.id})", inline=False)
        dm.add_field(name="✉️ Message", value=message,                                 inline=False)
        dm.set_footer(text="Feedback reçu", icon_url=EMBED_FOOTER_ICON_URL)

        try:
            await owner.send(embed=dm)
        except discord.Forbidden:
            # Le propriétaire a désactivé les MP
            ...

        # Confirmation éphémère
        await interaction.response.send_message(
            "✅ Votre feedback a bien été envoyé au développeur !",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(BotInfoCog(bot))
