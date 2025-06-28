# commands/admin/configurations/confession_settings.py

import datetime
import discord
from discord import app_commands
from discord.ext import commands

from config.mongo import confession_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES

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
        # Permission admin
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        gid = interaction.guild.id
        act = action.value

        # block/unblock requièrent un user
        if act in ("block", "unblock") and user is None:
            return await interaction.response.send_message(
                MESSAGES["MISSING_ARGUMENT"], ephemeral=True
            )

        if act == "block":
            await confession_collection.update_one(
                {"kind": "block", "guild_id": gid, "user_id": user.id},
                {"$set": {"timestamp": datetime.datetime.utcnow()}},
                upsert=True
            )
            return await interaction.response.send_message(
                f"🚫 {user.mention} est désormais bloqué·e.", ephemeral=True
            )

        if act == "unblock":
            await confession_collection.delete_one({
                "kind": "block", "guild_id": gid, "user_id": user.id
            })
            return await interaction.response.send_message(
                f"✅ {user.mention} a été débloqué·e.", ephemeral=True
            )

        # list
        cursor = confession_collection.find({"kind": "block", "guild_id": gid})
        blocked = [f"<@{doc['user_id']}>" async for doc in cursor]
        desc = "\n".join(blocked) if blocked else "Aucun utilisateur bloqué."
        embed = discord.Embed(
            title="🔒 Bloqués pour confessions",
            description=desc,
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionSettings(bot))
