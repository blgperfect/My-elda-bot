# commands/admin/configurations/confession_settings.py

import datetime
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

from config.mongo import confession_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES

PAGE_SIZE = 10  # Nombre d’utilisateurs listés par page

class BlockedListView(View):
    def __init__(self, blocked: list[str]):
        super().__init__(timeout=120)
        # Découper en pages
        self.pages = [blocked[i:i + PAGE_SIZE] for i in range(0, len(blocked), PAGE_SIZE)]
        if not self.pages:
            self.pages = [[]]
        self.current = 0
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        prev = Button(label="◀️", style=discord.ButtonStyle.secondary, custom_id="prev_block")
        next = Button(label="▶️", style=discord.ButtonStyle.secondary, custom_id="next_block")
        prev.disabled = (self.current == 0)
        next.disabled = (self.current == len(self.pages) - 1)
        prev.callback = self.on_prev
        next.callback = self.on_next
        self.add_item(prev)
        self.add_item(next)

    def make_embed(self) -> discord.Embed:
        chunk = self.pages[self.current]
        description = "\n".join(chunk) if chunk else "Aucun utilisateur bloqué."
        embed = discord.Embed(
            title="🔒 Bloqués pour confessions",
            description=description,
            color=EMBED_COLOR
        )
        embed.set_footer(
            text=f"{EMBED_FOOTER_TEXT} — Page {self.current + 1}/{len(self.pages)}",
            icon_url=EMBED_FOOTER_ICON_URL
        )
        return embed

    async def on_prev(self, interaction: discord.Interaction):
        self.current -= 1
        self._build_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def on_next(self, interaction: discord.Interaction):
        self.current += 1
        self._build_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


class ConfessionSettings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="confession_settings",
        description="Gérer le blocage/déblocage ou lister les utilisateurs bloqués."
    )
    @app_commands.describe(
        action="Action à effectuer : block | unblock | list",
        user="Utilisateur à bloquer/débloquer (requis pour block/unblock)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="block",   value="block"),
        app_commands.Choice(name="unblock", value="unblock"),
        app_commands.Choice(name="list",    value="list"),
    ])
    async def confession_settings(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        user: discord.Member = None
    ):
        # 🔐 Vérification permissions administrateur
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        gid = interaction.guild.id
        act = action.value

        # ❗ block/unblock nécessitent un utilisateur mentionné
        if act in ("block", "unblock") and user is None:
            return await interaction.response.send_message(
                MESSAGES["MISSING_ARGUMENT"], ephemeral=True
            )

        # ➡️ Blocage
        if act == "block":
            await confession_collection.update_one(
                {"kind": "block", "guild_id": gid, "user_id": user.id},
                {"$set": {"timestamp": datetime.datetime.utcnow()}},
                upsert=True
            )
            return await interaction.response.send_message(
                f"🚫 {user.mention} est désormais bloqué·e.", ephemeral=True
            )

        # ↩️ Déblocage
        if act == "unblock":
            await confession_collection.delete_one({
                "kind": "block", "guild_id": gid, "user_id": user.id
            })
            return await interaction.response.send_message(
                f"✅ {user.mention} a été débloqué·e.", ephemeral=True
            )

        # 📋 Listing avec pagination
        cursor = confession_collection.find({"kind": "block", "guild_id": gid})
        blocked = [f"<@{doc['user_id']}>" async for doc in cursor]

        view = BlockedListView(blocked)
        embed = view.make_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionSettings(bot))
