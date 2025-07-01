# commands/get_commands_cog.py
import discord
from discord.ext import commands

# Taille maximum safe pour Discord (1900 caractères)
MAX_CHARS = 1900

class GetCommandsCog(commands.Cog):
    """Cog pour lister tous les noms de commandes textuelles et slash du bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='get', help="Liste tous les noms de commandes textuelles et slash (owner only)")
    @commands.is_owner()
    async def get(self, ctx: commands.Context):
        # 1. Commandes textuelles (préfixées)
        text_cmds = sorted({cmd.name for cmd in self.bot.commands if not cmd.hidden})

        # 2. Commandes slash (app_commands)
        #    .get_commands() retourne tous les AppCommand enregistrés
        slash_cmds = sorted({c.name for c in self.bot.tree.get_commands()})

        if not text_cmds and not slash_cmds:
            return await ctx.reply("⚠️ Aucune commande trouvée.", mention_author=False)

        # Construit la sortie
        sections = []
        if text_cmds:
            sections.append("**Textuelles :**\n" + "\n".join(f"– {n}" for n in text_cmds))
        if slash_cmds:
            sections.append("**Slash :**\n" + "\n".join(f"– /{n}" for n in slash_cmds))

        # Pagination
        chunk = ""
        for sec in sections:
            for line in sec.splitlines(keepends=True):
                if len(chunk) + len(line) > MAX_CHARS:
                    await ctx.send(f"```json\n{chunk}```")
                    chunk = ""
                chunk += line
            # ajoute une ligne vide entre sections
            chunk += "\n"
        if chunk:
            await ctx.send(f"```json\n{chunk}```")

async def setup(bot: commands.Bot):
    await bot.add_cog(GetCommandsCog(bot))
