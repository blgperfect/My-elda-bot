import re, datetime
import discord
from discord import app_commands
from discord.ext import commands

# on importe la collection directement
from config.mongo import blacklist_collection
from config.params import (
    BOT_OWNER_ID,
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    EMBED_IMAGE_URL,
    EMOJIS,
)

INVITE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?discord(?:app)?\.com/invite/([A-Za-z0-9\-]+)"
)

class Blacklist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # n’utilise plus bot.db, on fait référence à la collection importée
        self.collection = blacklist_collection  

    async def cog_app_command_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message(
                f"{EMOJIS['WARNING_SIGN']} Vous n'êtes pas autorisé·e à utiliser cette commande.",
                ephemeral=True
            )
            return False
        return True

    blacklist = app_commands.Group(
        name="blacklist", description="Gérer la blacklist des serveurs"
    )

    @blacklist.command(name="add", description="➕ Ajouter un serveur à la blacklist")
    @app_commands.describe(server="ID du serveur ou lien d'invitation", reason="Raison")
    async def add(self, interaction: discord.Interaction, server: str, reason: str):
        await interaction.response.defer(thinking=True)
        # — Résoudre ID …
        m = INVITE_REGEX.match(server)
        if m:
            code = m.group(1)
            try:
                invite = await self.bot.fetch_invite(code, with_counts=False)
                guild_id = invite.guild.id
            except discord.NotFound:
                return await interaction.followup.send(
                    f"{EMOJIS['REPORT']} Invite invalide ou expirée.", ephemeral=True
                )
        elif server.isdigit():
            guild_id = int(server)
        else:
            return await interaction.followup.send(
                f"{EMOJIS['REPORT']} Doit être un ID ou un lien d'invite.", ephemeral=True
            )

        # — Vérifier l’existant
        if await self.collection.find_one({"guild_id": guild_id}):
            return await interaction.followup.send(
                f"{EMOJIS['WARNING_SIGN']} Le serveur `{guild_id}` est déjà blacklisté.",
                ephemeral=True
            )

        # — Insert
        await self.collection.insert_one({
            "guild_id": guild_id,
            "reason": reason,
            "date": datetime.datetime.utcnow()
        })

        # — Embed confirmation
        embed = discord.Embed(
            title=f"{EMOJIS['STAR']} Serveur blacklisté",
            color=EMBED_COLOR,
            description=f"**ID :** `{guild_id}`\n**Raison :** {reason}"
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.set_image(url=EMBED_IMAGE_URL)
        await interaction.followup.send(embed=embed)

        # — Quitter si déjà présent
        guild = self.bot.get_guild(guild_id)
        if guild:
            try:
                owner = guild.owner or await self.bot.fetch_user(guild.owner_id)
                await owner.send(
                    f"{EMOJIS['INBOX']} Je quitte **{guild.name}** (`{guild.id}`) : blacklist.\n"
                    f"Raison : {reason}"
                )
            except:
                pass
            await guild.leave()

    @blacklist.command(name="remove", description="➖ Retirer un serveur")
    @app_commands.describe(guild_id="ID du serveur")
    async def remove(self, interaction: discord.Interaction, guild_id: int):
        await interaction.response.defer(thinking=True)
        res = await self.collection.delete_one({"guild_id": guild_id})
        if res.deleted_count == 0:
            return await interaction.followup.send(
                f"{EMOJIS['REPORT']} Aucun `{guild_id}` dans la blacklist.", ephemeral=True
            )
        embed = discord.Embed(
            title=f"{EMOJIS['UP']} Serveur retiré",
            color=EMBED_COLOR,
            description=f"**ID :** `{guild_id}`"
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.set_image(url=EMBED_IMAGE_URL)
        await interaction.followup.send(embed=embed)

    @blacklist.command(name="list", description="📜 Lister les serveurs")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        docs = await self.collection.find().to_list(length=None)
        if not docs:
            return await interaction.followup.send(
                f"{EMOJIS['STAR']} La blacklist est vide.", ephemeral=True
            )

        # Pagination en pages de 10
        pages, chunk = [], 10
        for i in range(0, len(docs), chunk):
            emb = discord.Embed(
                title=f"{EMOJIS['LINK']} Blacklist — page {i//chunk+1}/{(len(docs)-1)//chunk+1}",
                color=EMBED_COLOR
            )
            for e in docs[i:i+chunk]:
                date = e["date"].strftime("%Y-%m-%d")
                emb.add_field(name=f"`{e['guild_id']}`", value=f"{e['reason']} — *{date}*", inline=False)
            emb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            pages.append(emb)

        view = _BlacklistPaginator(pages)
        await interaction.followup.send(embed=pages[0], view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        rec = await self.collection.find_one({"guild_id": guild.id})
        if rec:
            reason = rec["reason"]
            try:
                owner = guild.owner or await self.bot.fetch_user(guild.owner_id)
                await owner.send(
                    f"{EMOJIS['INBOX']} Je quitte **{guild.name}** (`{guild.id}`) : blacklist.\n"
                    f"Raison : {reason}"
                )
            except:
                pass
            await guild.leave()

class _BlacklistPaginator(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.current = 0

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction, button):
        if self.current > 0:
            self.current -= 1
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)
    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)

async def setup(bot: commands.Bot):
    await bot.add_cog(Blacklist(bot))
