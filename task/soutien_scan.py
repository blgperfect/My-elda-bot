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
        # Ne traiter que si même guild
        if before.guild != after.guild:
            return

        cfg = await soutien_collection.find_one({"_id": after.guild.id})
        if not cfg:
            return

        phrase = cfg["phrase"].lower()
        role   = after.guild.get_role(cfg["role_id"])
        chan   = after.guild.get_channel(cfg["channel_id"])
        if not role or not chan:
            return

        # Extraire le Custom Status
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
            # Ajout du rôle
            await after.add_roles(role, reason="Soutien activé")
            # Envoi du DM de remerciement
            try:
                await after.send(
                    f"🎉 Merci de soutenir **{after.guild.name}** ! Vous avez obtenu votre rôle **{role.name}**."
                )
            except discord.Forbidden:
                pass
            # Message public
            await chan.send(f"{EMOJIS.get('PARTY','🎉')} {after.mention} a activé le soutien !")

        elif had and not has:
            # Retrait du rôle
            await after.remove_roles(role, reason="Soutien désactivé")
            await chan.send(f"{EMOJIS.get('CROSS','✖️')} {after.mention} a désactivé le soutien !")

async def setup(bot: commands.Bot):
    await bot.add_cog(SoutienListener(bot))
