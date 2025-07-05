import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select
from datetime import datetime

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import moderation_collection

# Collection pour les réglages (salon des logs)
settings_collection = moderation_collection.database['settings']


class ModLogView(View):
    """Vue paginée pour afficher les logs de modération et les compteurs de warns."""

    def __init__(self, entries: list[dict], author_id: int, total_warns: int, guild_warns: int):
        super().__init__(timeout=180)
        self.entries = entries
        self.page = 0
        self.author_id = author_id
        self.total_warns = total_warns
        self.guild_warns = guild_warns

    def make_embed(self) -> discord.Embed:
        # Clamp de la page pour éviter les IndexError
        self.page = max(0, min(self.page, len(self.entries) - 1))
        entry = self.entries[self.page]
        embed = discord.Embed(
            title="📋 Logs de modération",
            description=f"Page {self.page + 1}/{len(self.entries)}",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Action", value=entry["action"].capitalize(), inline=True)
        embed.add_field(name="Serveur", value=entry["guild_name"], inline=True)
        embed.add_field(name="Warns totaux", value=str(self.total_warns), inline=True)
        embed.add_field(name="Warns ce serveur", value=str(self.guild_warns), inline=True)
        embed.add_field(name="Raison", value=entry["reason"], inline=False)
        embed.set_footer(
            text=f"{EMBED_FOOTER_TEXT} • {entry['timestamp'].strftime('%Y-%m-%d %H:%M UTC')}",
            icon_url=EMBED_FOOTER_ICON_URL
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.defer()
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.make_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.defer()
        if self.page < len(self.entries) - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.make_embed(), view=self)
        else:
            await interaction.response.defer()


class Moderation(commands.Cog):
    """Cog pour gérer les commandes mod: ban, kick, warn, warn-reset, check et setup."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    mod = app_commands.Group(name="mod", description="Commandes de modération")

    def _can_override_hierarchy(self, member: discord.Member) -> bool:
        return member.guild_permissions.manage_guild

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed):
        settings = await settings_collection.find_one({"guild_id": guild.id})
        if settings and settings.get("mod_log_channel"):
            channel = guild.get_channel(settings["mod_log_channel"])
            if channel:
                await channel.send(embed=embed)

    @mod.command(name="ban", description="Ban un utilisateur et log globalement.")
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str
    ):
        target = interaction.guild.get_member(user.id)
        if target and not self._can_override_hierarchy(interaction.user) and \
           (target == interaction.guild.owner or target.top_role >= interaction.user.top_role):
            embed = discord.Embed(
                title=EMOJIS.get('ERROR', '❌') + " Hiérarchie",
                description="Vous ne pouvez pas bannir ce membre (hiérarchie trop haute).",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            await interaction.guild.ban(user, reason=reason)
        except discord.HTTPException as e:
            embed = discord.Embed(
                title=MESSAGES['INTERNAL_ERROR'],
                description=f"Impossible de bannir {user.mention}: {e}",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        now = datetime.utcnow()
        await moderation_collection.update_one(
            {"_id": user.id},
            {"$push": {"actions": {
                "guild_id": interaction.guild.id,
                "guild_name": interaction.guild.name,
                "action": "ban",
                "reason": reason,
                "timestamp": now
            }}},
            upsert=True
        )

        embed_log = discord.Embed(
            title=EMOJIS.get('CHECK', '✅') + " Utilisateur banni",
            description=f"**Membre**: {user.mention}\n**Raison**: {reason}",
            color=EMBED_COLOR,
            timestamp=now
        )
        embed_log.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await self._send_log(interaction.guild, embed_log)
        await interaction.response.send_message(embed=embed_log, ephemeral=True)

    @mod.command(name="kick", description="Expulse un membre et log globalement.")
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str
    ):
        if not self._can_override_hierarchy(interaction.user) and \
           (member == interaction.guild.owner or member.top_role >= interaction.user.top_role):
            embed = discord.Embed(
                title=EMOJIS.get('ERROR', '❌') + " Hiérarchie",
                description="Vous ne pouvez pas expulser ce membre (hiérarchie trop haute).",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            await interaction.guild.kick(member, reason=reason)
        except discord.HTTPException as e:
            embed = discord.Embed(
                title=MESSAGES['INTERNAL_ERROR'],
                description=f"Impossible d'expulser {member.mention}: {e}",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        now = datetime.utcnow()
        await moderation_collection.update_one(
            {"_id": member.id},
            {"$push": {"actions": {
                "guild_id": interaction.guild.id,
                "guild_name": interaction.guild.name,
                "action": "kick",
                "reason": reason,
                "timestamp": now
            }}},
            upsert=True
        )

        embed_log = discord.Embed(
            title=EMOJIS.get('CHECK', '✅') + " Membre expulsé",
            description=f"**Membre**: {member.mention}\n**Raison**: {reason}",
            color=EMBED_COLOR,
            timestamp=now
        )
        embed_log.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await self._send_log(interaction.guild, embed_log)
        await interaction.response.send_message(embed=embed_log, ephemeral=True)

    @mod.command(name="warn", description="Avertit un membre. À 3 warns, expulsion auto.")
    @app_commands.default_permissions(kick_members=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str
    ):
        now = datetime.utcnow()
        await moderation_collection.update_one(
            {"_id": member.id},
            {"$push": {"actions": {
                "guild_id": interaction.guild.id,
                "guild_name": interaction.guild.name,
                "action": "warn",
                "reason": reason,
                "timestamp": now
            }}},
            upsert=True
        )

        doc = await moderation_collection.find_one({"_id": member.id})
        all_warns = [a for a in doc['actions'] if a['action'] == 'warn']
        total_warns = len(all_warns)
        guild_warns = len([a for a in all_warns if a['guild_id'] == interaction.guild.id])

        title = EMOJIS.get('CHECK', '✅') + f" Avertissement #{guild_warns}"
        desc = f"{member.mention} averti pour :\n> {reason}"
        embed_log = discord.Embed(title=title, description=desc, color=EMBED_COLOR, timestamp=now)
        embed_log.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await self._send_log(interaction.guild, embed_log)

        try:
            dm = await member.create_dm()
            await dm.send(
                f"Bonjour {member.display_name},\n"
                f"{desc}\n"
                f"Warns dans **{interaction.guild.name}**  : {guild_warns}\n"
                f"Warns totaux (tous serveurs) : {total_warns}"
            )
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            f"Avertissement envoyé à {member.mention}. Warns actuels : {guild_warns}.",
            ephemeral=True
        )

        if guild_warns >= 3:
            await interaction.guild.kick(member, reason="3 warns atteints")
            now_kick = datetime.utcnow()
            await moderation_collection.update_one(
                {"_id": member.id},
                {"$push": {"actions": {
                    "guild_id": interaction.guild.id,
                    "guild_name": interaction.guild.name,
                    "action": "kick",
                    "reason": "3 warns atteints",
                    "timestamp": now_kick
                }}}
            )
            embed_kick = discord.Embed(
                title=EMOJIS.get('CHECK', '✅') + " Membre expulsé",
                description=f"{member.mention} expulsé après 3 warns.",
                color=EMBED_COLOR,
                timestamp=now_kick
            )
            embed_kick.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await self._send_log(interaction.guild, embed_kick)

    @mod.command(name="warn-reset", description="Remet à zéro les warns d'un membre sur ce serveur.")
    @app_commands.default_permissions(kick_members=True)
    async def warn_reset(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        await moderation_collection.update_one(
            {"_id": member.id},
            {"$pull": {"actions": {"action": "warn", "guild_id": interaction.guild.id}}}
        )
        doc = await moderation_collection.find_one({"_id": member.id})
        remaining = len([a for a in doc.get('actions', []) if a['action'] == 'warn' and a['guild_id'] == interaction.guild.id])
        now = datetime.utcnow()
        await moderation_collection.update_one(
            {"_id": member.id},
            {"$push": {"actions": {
                "guild_id": interaction.guild.id,
                "guild_name": interaction.guild.name,
                "action": "warn-reset",
                "reason": "Réinitialisation des warns",
                "timestamp": now
            }}}
        )

        embed_log = discord.Embed(
            title=EMOJIS.get('CHECK', '✅') + " Warns réinitialisés",
            description=f"Les warns de {member.mention} sur ce serveur ont été remis à zéro.",
            color=EMBED_COLOR,
            timestamp=now
        )
        embed_log.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await self._send_log(interaction.guild, embed_log)

        await interaction.response.send_message(
            f"Les warns de {member.mention} ont été réinitialisés. Restants : {remaining}.",
            ephemeral=True
        )

    @mod.command(name="check", description="Affiche les logs de modération d'un utilisateur.")
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
                description=f"Aucun log pour {member.mention}.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        all_warns = [a for a in doc['actions'] if a['action'] == 'warn']
        total_warns = len(all_warns)
        guild_warns = len([a for a in all_warns if a['guild_id'] == interaction.guild.id])

        entries = sorted(
            [a for a in doc['actions'] if a['action'] in ('kick', 'ban')],
            key=lambda a: a['timestamp'],
            reverse=True
        )
        if not entries:
            embed = discord.Embed(
                title=EMOJIS.get('INFO', 'ℹ️') + " Aucun kick/ban trouvé",
                description=f"{member.mention} n'a subi aucun kick ni ban sur ce serveur.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        view = ModLogView(entries, interaction.user.id, total_warns, guild_warns)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @mod.command(name="setup", description="Configure le salon des logs de modération.")
    @app_commands.default_permissions(administrator=True)
    async def setup(
        self,
        interaction: discord.Interaction
    ):
        options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in interaction.guild.text_channels]
        select = Select(placeholder="Sélectionnez le salon des logs…", options=options)

        async def callback(select_i: discord.Interaction):
            channel_id = int(select.values[0])
            await settings_collection.update_one(
                {"guild_id": interaction.guild.id},
                {"$set": {"mod_log_channel": channel_id}},
                upsert=True
            )
            await select_i.response.edit_message(content=f"Salon des logs défini : <#{channel_id}>", view=None)

        select.callback = callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Merci de sélectionner le salon des logs pour kick/ban/warn :", view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
