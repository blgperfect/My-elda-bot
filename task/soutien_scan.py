# commands/admin/soutien_scan.py
# complété
import discord
from discord.ext import commands
from config.mongo import soutien_collection

class SoutienListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        # Même serveur seulement
        if before.guild != after.guild:
            return

        cfg = await soutien_collection.find_one({"_id": after.guild.id})
        if not cfg:
            return

        phrase = cfg["phrase"].lower()
        role   = after.guild.get_role(cfg["role_id"])
        if not role:
            return

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
            # Ajout du rôle uniquement
            await after.add_roles(role, reason="Soutien activé")

        elif had and not has:
            # Retrait du rôle uniquement
            await after.remove_roles(role, reason="Soutien désactivé")

async def setup(bot: commands.Bot):
    await bot.add_cog(SoutienListener(bot))
