# commands/admin/role.py

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, RoleSelect, Button

from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES
from config.mongo import role_config_collection


class RoleConfigView(View):
    """Vue interactive pour sélectionner et sauvegarder les rôles autorisés."""
    def __init__(self, author: discord.Member, guild: discord.Guild, initial: list[int]):
        super().__init__(timeout=180)
        self.author = author
        self.guild = guild
        # IDs des rôles pré-sélectionnés
        self.selected: list[int] = initial.copy()

        # Sélecteur de rôles
        sel = RoleSelect(
            placeholder="🔍 Sélectionnez un ou plusieurs rôles…",
            min_values=0,
            max_values=len(guild.roles),
            row=0
        )
        sel.callback = self.select_roles
        self.add_item(sel)

        # Bouton de confirmation
        finish = Button(style=discord.ButtonStyle.success, emoji="✅")
        finish.callback = self.finish
        self.add_item(finish)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )
            return False
        return True

    async def select_roles(self, interaction: discord.Interaction):
        """Met à jour l’aperçu des rôles sélectionnés."""
        sel = next(c for c in self.children if isinstance(c, RoleSelect))  # type: ignore
        self.selected = [r.id for r in sel.values]  # type: ignore

        roles_list = (
            "\n".join(f"- {self.guild.get_role(rid).mention}" for rid in self.selected)
            or "Aucun rôle sélectionné."
        )
        embed = discord.Embed(
            title="⚙️ Configuration des rôles autorisés",
            description=(
                "Les rôles suivants seront autorisés à utiliser `/role give` et `/role remove` :\n\n"
                f"{roles_list}"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=embed, view=self)

    async def finish(self, interaction: discord.Interaction):
        """Sauvegarde la configuration en base et confirme l’opération."""
        try:
            await role_config_collection.update_one(
                {"_id": self.guild.id},
                {"$set": {"roles": self.selected}},
                upsert=True
            )
        except Exception:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            description=MESSAGES["ACTION_SUCCESS"],
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Désactive le composant
        for comp in self.children:
            comp.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)


class RoleManager(commands.Cog):
    """Cog pour gérer la configuration et l'attribution de rôles via slash commands."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    role = app_commands.Group(name="role", description="Gestion des rôles via le bot")

    @role.command(
        name="config",
        description="Configure les rôles autorisés pour `/role give` et `/role remove`."
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        """Permet aux administrateurs de définir quels rôles peuvent utiliser `/role give` et `/role remove`."""
        # Récupération de la config existante
        try:
            data = await role_config_collection.find_one({"_id": interaction.guild.id})
        except Exception:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        current = data.get("roles", []) if data else []

        embed = discord.Embed(
            title="🔧 Configuration des accès `/role give` & `/role remove`",
            description=(
                "Bienvenue dans la configuration des accès aux commandes `/role give` et `/role remove`.\n"
                "Merci de sélectionner ci-dessous les rôles de votre serveur qui auront le droit d’utiliser "
                "`/role give` et `/role remove` en plus des administrateurs.\n\n"
                "Cliquez sur ✅ lorsque vous avez terminé votre sélection."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        view = RoleConfigView(interaction.user, interaction.guild, current)
        view.message = await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

    @role.command(
        name="give",
        description="Donne un rôle à un membre."
    )
    async def give(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role
    ):
        """Attribue un rôle à un membre, si l’exécuteur est autorisé."""
        # Chargement de la config
        try:
            data = await role_config_collection.find_one({"_id": interaction.guild.id})
        except Exception:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        allowed = (
            interaction.user.guild_permissions.administrator
            or any(r.id in (data.get("roles") or []) for r in interaction.user.roles)
        )
        if not allowed:
            embed = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Vérification de la hiérarchie Discord
        if interaction.user.top_role <= member.top_role:
            embed = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                description="🚫 Vous ne pouvez pas attribuer un rôle à un membre ayant un rôle supérieur ou égal au vôtre.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Tentative d’assignation
        try:
            await member.add_roles(role, reason=f"Role donné par {interaction.user}")
        except discord.Forbidden:
            embed = discord.Embed(
                title=MESSAGES["BOT_PERMISSION_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Succès
        embed = discord.Embed(
            description=MESSAGES["ROLE_ASSIGNED"],
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)

    @role.command(
        name="remove",
        description="Retire un rôle à un membre."
    )
    async def remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role
    ):
        """Retire un rôle à un membre, si l’exécuteur est autorisé."""
        # Chargement de la config
        try:
            data = await role_config_collection.find_one({"_id": interaction.guild.id})
        except Exception:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        allowed = (
            interaction.user.guild_permissions.administrator
            or any(r.id in (data.get("roles") or []) for r in interaction.user.roles)
        )
        if not allowed:
            embed = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Vérification de la hiérarchie Discord
        if interaction.user.top_role <= member.top_role:
            embed = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                description="🚫 Vous ne pouvez pas retirer un rôle à un membre ayant un rôle supérieur ou égal au vôtre.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Tentative de retrait
        try:
            await member.remove_roles(role, reason=f"Role retiré par {interaction.user}")
        except discord.Forbidden:
            embed = discord.Embed(
                title=MESSAGES["BOT_PERMISSION_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Succès
        embed = discord.Embed(
            description="✅ Rôle retiré avec succès.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleManager(bot))
