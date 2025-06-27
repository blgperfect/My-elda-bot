import discord
from discord.ext import commands
from config.mongo import soutien_collection
from config.params import EMOJIS, EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

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

        phrase      = cfg["phrase"].lower()
        role        = after.guild.get_role(cfg["role_id"])
        announce_ch = after.guild.get_channel(cfg["announce_ch_id"])
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

            # Embed de log pour activation
            embed = discord.Embed(
                title="🎉 Soutien activé",
                color=EMBED_COLOR,
                description=f"{EMOJIS.get('PARTY','🎉')} {after.mention} soutient le serveur !"
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await target.send(embed=embed)

        elif had and not has:
            # Retrait du rôle
            await after.remove_roles(role, reason="Soutien désactivé")

            # Embed de log pour désactivation
            embed = discord.Embed(
                title="✖️ Soutien désactivé",
                color=EMBED_COLOR,
                description=f"{EMOJIS.get('CROSS','✖️')} {after.mention} ne soutient plus le serveur !"
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await target.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SoutienListener(bot))
