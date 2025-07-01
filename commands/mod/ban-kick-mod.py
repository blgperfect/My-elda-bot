import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from datetime import datetime

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import moderation_collection


class ModLogView(View):
    def __init__(self, entries: list[dict], author_id: int):
        super().__init__(timeout=180)
        self.entries = entries
        self.page = 0
        self.author_id = author_id

    def make_embed(self) -> discord.Embed:
        entry = self.entries[self.page]
        embed = discord.Embed(
            title="📋 Logs de modération",
            description=f"Page {self.page+1}/{len(self.entries)}",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Action", value=entry["action"].capitalize(), inline=True)
        embed.add_field(name="Serveur", value=entry["guild_name"], inline=True)
        embed.add_field(name="Raison", value=entry["reason"], inline=False)
        embed.set_footer(
            text=f"{EMBED_FOOTER_TEXT} • {entry['timestamp'].strftime('%Y-%m-%d %H:%M UTC')}",
            icon_url=EMBED_FOOTER_ICON_URL
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Autorise uniquement l'auteur initial
        return interaction.user.id == self.author_id

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.make_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.entries) - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.make_embed(), view=self)
        else:
            await interaction.response.defer()


class Moderation(commands.Cog):
    """Cog pour gérer ban/kick et logs globaux."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ban", description="Ban un utilisateur (membre ou ID) et log l'action globalement.")
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str
    ):
        # Exécuter le ban même si l'utilisateur n'est pas sur le serveur
        try:
            await interaction.guild.ban(user, reason=reason)
        except discord.HTTPException as e:
            embed = discord.Embed(
                title=MESSAGES['INTERNAL_ERROR'],
                description=f"Impossible de bannir {user.mention}: {e}",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed)

        # Enregistrement en base
        await moderation_collection.update_one(
            {"_id": user.id},
            {"$push": {"actions": {
                "guild_id": interaction.guild.id,
                "guild_name": interaction.guild.name,
                "action": "ban",
                "reason": reason,
                "timestamp": datetime.utcnow()
            }}},
            upsert=True
        )
        # Embed de confirmation public
        embed = discord.Embed(
            title=EMOJIS.get('CHECK', '✅') + " Utilisateur banni",
            description=f"{user.mention} banni pour :\n> {reason}",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kick", description="Expulse un membre et log l'action globalement.")
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str
    ):
        try:
            await interaction.guild.kick(member, reason=reason)
        except discord.HTTPException as e:
            embed = discord.Embed(
                title=MESSAGES['INTERNAL_ERROR'],
                description=f"Impossible d'expulser {member.mention}: {e}",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed)

        await moderation_collection.update_one(
            {"_id": member.id},
            {"$push": {"actions": {
                "guild_id": interaction.guild.id,
                "guild_name": interaction.guild.name,
                "action": "kick",
                "reason": reason,
                "timestamp": datetime.utcnow()
            }}},
            upsert=True
        )
        embed = discord.Embed(
            title=EMOJIS.get('CHECK', '✅') + " Membre expulsé",
            description=f"{member.mention} expulsé pour :\n> {reason}",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="check", description="Affiche les bans et kicks d'un utilisateur.")
    @app_commands.default_permissions(view_audit_log=True)
    async def check(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        doc = await moderation_collection.find_one({"_id": member.id})
        if not doc or not doc.get('actions'):
            embed = discord.Embed(
                title=EMOJIS.get('INFO', 'ℹ️') + " Aucun log trouvé",
                description=f"Aucun ban/kick enregistré pour {member.mention}.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed)

        entries = sorted(doc['actions'], key=lambda a: a['timestamp'], reverse=True)
        view = ModLogView(entries, interaction.user.id)
        await interaction.response.send_message(embed=view.make_embed(), view=view)

    @ban.error
    async def ban_error(self, interaction: discord.Interaction, error):
        embed = discord.Embed(
            title=MESSAGES['INTERNAL_ERROR'],
            description=str(error),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)

    @kick.error
    async def kick_error(self, interaction: discord.Interaction, error):
        embed = discord.Embed(
            title=MESSAGES['INTERNAL_ERROR'],
            description=str(error),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)

    @check.error
    async def check_error(self, interaction: discord.Interaction, error):
        embed = discord.Embed(
            title=MESSAGES['INTERNAL_ERROR'],
            description=str(error),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
