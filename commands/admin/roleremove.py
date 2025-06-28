# commands/admin/role_remove.py
import discord
from discord import app_commands
from discord.ext import commands

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import role_config_collection


class RoleRemove(commands.Cog):
    """Retire un rôle si l’utilisateur est admin ou a un rôle configuré."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roleremove", description="Retirer un rôle à un membre")
    @app_commands.describe(member="Membre cible", role="Rôle à retirer")
    async def roleremove(
        self, interaction: discord.Interaction, member: discord.Member, role: discord.Role
    ):
        # Récupère la config en base
        cfg = await role_config_collection.find_one(
            {"guild_id": interaction.guild.id}
        ) or {}
        allowed = cfg.get("allowed_roles", [])
        user = interaction.user

        # Vérifie les droits
        if not (
            user.guild_permissions.administrator
            or any(r.id in allowed for r in user.roles)
        ):
            embed = discord.Embed(
                description=MESSAGES["PERMISSION_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Hiérarchie : pas plus haut que soi-même
        if role.position >= user.top_role.position:
            embed = discord.Embed(
                description=f"{EMOJIS['ERROR']} Vous ne pouvez pas retirer un rôle supérieur au vôtre.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Cible trop élevée
        if member.top_role.position >= user.top_role.position:
            embed = discord.Embed(
                description=f"{EMOJIS['ERROR']} Vous ne pouvez pas retirer un rôle à ce membre.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Retrait du rôle
        await member.remove_roles(role)
        embed = discord.Embed(
            description=f"{EMOJIS['SUCCESS']} {role.mention} retiré à {member.mention}.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleRemove(bot))
