# commands/admin/soutien_scan.py

import discord
from discord.ext import commands
from config.mongo import soutien_collection
from config.params import EMOJIS

class SoutienListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        # Même guild seulement
        if before.guild != after.guild:
            return

        cfg = await soutien_collection.find_one({"_id": after.guild.id})
        if not cfg:
            return

        phrase       = cfg["phrase"].lower()
        role         = after.guild.get_role(cfg["role_id"])
        announce_ch  = after.guild.get_channel(cfg["announce_ch_id"])
        if not role or not announce_ch:
            return

        # Choix du salon pour les logs d’activations/désactivations
        log_ch = None
        if cfg.get("log_enabled", False):
            log_ch = after.guild.get_channel(cfg.get("log_ch_id"))
        target = log_ch or announce_ch

        # Extraction du Custom Status
        def extract_status(member: discord.Member) -> str:
            for act in member.activities:
                if isinstance(act, discord.CustomActivity):
                    return (act.state or "").lower()
            return ""

        prev = extract_status(before)
        post = extract_status(after)
        had  = phrase in prev
        has  = phrase in post

        if has and not had:
            # Ajout du rôle + DM
            await after.add_roles(role, reason="Soutien activé")
            try:
                await after.send(f"🎉 Merci de soutenir **{after.guild.name}** ! Rôle **{role.name}** ajouté.")
            except discord.Forbidden:
                pass
            # **Log**  
            await target.send(f"{EMOJIS.get('PARTY','🎉')} {after.mention} soutien le server !")

        elif had and not has:
            # Retrait du rôle
            await after.remove_roles(role, reason="Soutien désactivé")
            # **Log**
            await target.send(f"{EMOJIS.get('CROSS','✖️')} {after.mention} ne soutien plus le server !")

async def setup(bot: commands.Bot):
    await bot.add_cog(SoutienListener(bot))
