import discord
from discord.ext import tasks, commands
from config.mongo import soutien_collection
from config.params import EMOJIS

class SoutienScanner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_bios.start()

    @tasks.loop(minutes=5.0)
    async def check_bios(self):
        for guild in self.bot.guilds:
            cfg = await soutien_collection.find_one({"_id": guild.id})
            if not cfg:
                continue

            phrase = cfg["phrase"]
            role   = guild.get_role(cfg["role_id"])
            chan   = guild.get_channel(cfg["channel_id"])
            if not role or not chan:
                continue

            for member in guild.members:
                # Récupérer la bio
                try:
                    route = discord.http.Route("GET", "/users/{user_id}/profile", user_id=member.id)
                    data  = await self.bot.http.request(route)
                    bio   = data.get("bio", "") or ""
                except:
                    continue

                has = phrase in bio
                in_role = role in member.roles

                if has and not in_role:
                    await member.add_roles(role, reason="Soutien activé")
                    await chan.send(f"{EMOJIS.get('PARTY','🎉')} {member.mention} a activé le soutien !")
                elif not has and in_role:
                    await member.remove_roles(role, reason="Soutien désactivé")
                    await chan.send(f"{EMOJIS.get('CROSS','✖️')} {member.mention} a désactivé le soutien !")

    @check_bios.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(SoutienScanner(bot))
