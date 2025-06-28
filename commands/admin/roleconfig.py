# commands/admin/role_config.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, RoleSelect

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import role_config_collection


class RoleConfigView(View):
    def __init__(self, author: discord.Member, existing: list[int] | None = None):
        super().__init__(timeout=180)
        self.author = author
        self.guild = author.guild
        # IDs des rôles déjà configurés (venant de la DB)
        self.allowed_ids: list[int] = existing or []
        self.message: discord.Message | None = None

    async def update_embed(self, interaction: discord.Interaction):
        # Reconstruit l'embed pour afficher l'état actuel
        desc = (
            "**Rôles autorisés :** "
            + (
                ", ".join(f"<@&{rid}>" for rid in self.allowed_ids)
                if self.allowed_ids
                else "❌ non définis"
            )
        )
        embed = discord.Embed(
            title="⚙️ Configuration des rôles autorisés",
            description=desc + "\n\n1️⃣ Cliquez sur **Sélectionner** pour choisir.",
            color=EMBED_COLOR,
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # Active le bouton Terminer seulement si on a au moins 1 rôle
        finish_btn: Button = next(
            b for b in self.children if getattr(b, "custom_id", None) == "finish"
        )  # type: ignore
        finish_btn.disabled = not bool(self.allowed_ids)

        # Édite le message
        if self.message:
            await self.message.edit(embed=embed, view=self)
        else:
            # fallback
            await interaction.response.send_message(embed=embed, view=self)

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True
        if self.message:
            await self.message.edit(
                content="⏱️ Menu expiré. Relancez `/roleconfig`.",
                embed=None,
                view=self
            )

    @discord.ui.button(
        label="Sélectionner",
        style=discord.ButtonStyle.primary,
        emoji=EMOJIS.get("STAR", "⭐"),
        custom_id="select"
    )
    async def _select(
        self, interaction: discord.Interaction, button: Button
    ):
        # Seul l'auteur initial peut interagir
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        # Vue temporaire pour choisir les rôles
        temp = View(timeout=60)
        sel = RoleSelect(
            placeholder="🔍 Sélectionnez un ou plusieurs rôles…",
            min_values=1,
            max_values=25
        )

        async def sel_cb(resp: discord.Interaction):
            # On stocke les IDs et on met à jour l'embed parent
            self.allowed_ids = [r.id for r in sel.values]
            await self.update_embed(resp)
            # On supprime le message temporaire
            await resp.delete_original_response()

        sel.callback = sel_cb
        temp.add_item(sel)

        await interaction.response.send_message(
            "Choisissez les rôles :", view=temp, ephemeral=True
        )

    @discord.ui.button(
        label="✅ Terminer",
        style=discord.ButtonStyle.success,
        custom_id="finish",
        disabled=True
    )
    async def _finish(
        self, interaction: discord.Interaction, button: Button
    ):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        # Sauvegarde en base MongoDB
        await role_config_collection.update_one(
            {"guild_id": self.guild.id},
            {"$set": {"allowed_roles": self.allowed_ids}},
            upsert=True
        )

        # Confirmation finale
        embed2 = discord.Embed(
            title=MESSAGES["ACTION_SUCCESS"],
            description=(
                f"{EMOJIS['SUCCESS']} Rôles autorisés : "
                + ", ".join(f"<@&{rid}>" for rid in self.allowed_ids)
            ),
            color=EMBED_COLOR
        )
        embed2.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # Désactive les boutons et édite le message
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(embed=embed2, view=self)


class RoleConfig(commands.Cog):
    """Cog pour configurer les rôles autorisés à /rolegive et /roleremove."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="roleconfig",
        description="Configurer les rôles autorisés"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def roleconfig(self, interaction: discord.Interaction):
        # Charge la config existante
        cfg = await role_config_collection.find_one(
            {"guild_id": interaction.guild.id}
        ) or {}
        existing = cfg.get("allowed_roles", [])

        view = RoleConfigView(interaction.user, existing)
        embed = discord.Embed(
            title="⚙️ Configuration des rôles autorisés",
            description=(
                "**Rôles autorisés :** "
                + (
                    ", ".join(f"<@&{rid}>" for rid in existing)
                    if existing
                    else "❌ non définis"
                )
                + "\n\n1️⃣ Cliquez sur **Sélectionner** pour choisir."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @roleconfig.error
    async def roleconfig_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            embed = discord.Embed(
                description=MESSAGES["PERMISSION_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleConfig(bot))
