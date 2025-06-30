# commands/admin/roles/reactionrole.py

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select, RoleSelect

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import role_panel_collection


class CategoryModal(Modal, title="Ajouter une catégorie"):
    """Modal pour saisir le nom d'une nouvelle catégorie."""
    name = TextInput(label="Nom de la catégorie", max_length=50)

    def __init__(self, parent_view: "SetupView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        val = self.name.value.strip()
        if val and val not in sess["categories"]:
            sess["categories"].append(val)
            sess["roles"][val] = []
        await self.parent_view.update_embed(interaction)


class SetupView(View):
    """View privée pour gérer l'assistant pas-à-pas."""
    def __init__(self, author: discord.Member, cog: commands.Cog, guild_id: int):
        super().__init__(timeout=180)
        self.author = author
        self.cog = cog
        self.guild_id = guild_id
        self.message: discord.Message | None = None
        self._update_buttons()  # initialise l'état des boutons

    def _update_buttons(self):
        sess = self.cog.sessions[self.guild_id]
        for btn in self.children:
            cid = getattr(btn, "custom_id", "")
            if cid == "category":
                btn.disabled = len(sess["categories"]) >= 5 or sess["action"] != "create"
            elif cid == "roles":
                btn.disabled = not sess["categories"] or sess["action"] != "create"
            elif cid == "finish":
                incomplete = any(not sess["roles"].get(cat) for cat in sess["categories"])
                btn.disabled = not sess["categories"] or incomplete or sess["action"] != "create"
            elif cid == "modify":
                btn.disabled = sess["action"] != "modify"
            elif cid == "delete":
                btn.disabled = sess["action"] != "modify"

    async def update_embed(self, interaction: discord.Interaction):
        sess = self.cog.sessions[self.guild_id]
        if sess["categories"]:
            lines = [
                f"**{cat}** : " +
                (" ".join(f"<@&{rid}>" for rid in sess["roles"].get(cat, [])) or "_(vide)_")
                for cat in sess["categories"]
            ]
            desc = "\n".join(lines)
        else:
            desc = "Aucune catégorie définie pour l’instant"

        embed = discord.Embed(
            title="⚙️ Configuration du panneau de rôles",
            description=desc,
            color=EMBED_COLOR
        ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        self._update_buttons()
        if self.message:
            await self.message.edit(embed=embed, view=self)
        if not interaction.response.is_done():
            await interaction.response.defer()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True
        if self.message:
            await self.message.edit(content="⏱️ Configuration expirée.", view=self)

    @discord.ui.button(
        label="➕ Ajouter catégorie",
        style=discord.ButtonStyle.primary,
        emoji=EMOJIS.get("PLUS", "➕"),
        custom_id="category",
    )
    async def _category(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await interaction.response.send_modal(CategoryModal(self))

    @discord.ui.button(
        label="➕ Ajouter des rôles",
        style=discord.ButtonStyle.primary,
        emoji=EMOJIS.get("STAR", "⭐"),
        custom_id="roles",
    )
    async def _roles(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        parent_view = self
        sess = self.cog.sessions[self.guild_id]
        options = [discord.SelectOption(label=c, value=c) for c in sess["categories"]]

        class CatSelect(Select):
            def __init__(self):
                super().__init__(
                    placeholder="Sélectionnez une catégorie…",
                    min_values=1, max_values=1,
                    options=options,
                )

            async def callback(self, inner: discord.Interaction):
                cat = self.values[0]
                v2 = View(timeout=60)
                v2.parent_view = parent_view
                role_sel = RoleSelect(
                    placeholder=f"Rôles pour {cat}", min_values=1, max_values=10
                )

                async def role_cb(resp: discord.Interaction):
                    pv = v2.parent_view
                    sess2 = pv.cog.sessions[pv.guild_id]
                    # type: ignore on values since RoleSelect.values is List[Role]
                    sess2["roles"][cat] = [r.id for r in role_sel.values]  
                    await pv.update_embed(resp)
                    await resp.delete_original_response()

                role_sel.callback = role_cb
                v2.add_item(role_sel)
                await inner.response.send_message(
                    f"Choisissez jusqu’à 10 rôles pour **{cat}**",
                    view=v2,
                    ephemeral=True
                )

        v = View(timeout=60)
        v.add_item(CatSelect())
        await interaction.response.send_message(
            "Sélectionnez la catégorie à configurer :", view=v, ephemeral=True
        )

    @discord.ui.button(
        label="✅ Envoyer le panneau",
        style=discord.ButtonStyle.success,
        custom_id="finish",
    )
    async def _finish(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await self.cog.finalize_panel(self.guild_id, interaction)

    @discord.ui.button(
        label="♻️ Modifier",
        style=discord.ButtonStyle.secondary,
        custom_id="modify",
    )
    async def _modify(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await self.cog.start_modify(interaction)

    @discord.ui.button(
        label="🗑️ Supprimer",
        style=discord.ButtonStyle.danger,
        custom_id="delete",
    )
    async def _delete(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await self.cog.delete_panel(interaction)


class ReactionRole(commands.Cog):
    """Cog pour /rolesetup → création, modification et suppression d’un panneau de rôles."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, dict] = {}

    @app_commands.command(
        name="rolesetup",
        description="Créer un panneau de rôles interactif"
    )
    @app_commands.default_permissions(administrator=True)
    async def rolesetup(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        self.sessions[guild_id] = {
            "action": "create",
            "categories": [],
            "roles": {},
            "view": None,
            "panel_ch": None,
            "panel_msg": None,
        }
        view = SetupView(interaction.user, self, guild_id)
        self.sessions[guild_id]["view"] = view

        embed = discord.Embed(
            title="⚙️ Configuration du panneau de rôles",
            description="Aucune catégorie définie pour l’instant",
            color=EMBED_COLOR
        ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    async def finalize_panel(self, guild_id: int, interaction: discord.Interaction):
        sess = self.sessions[guild_id]
        # Embed public
        embed = discord.Embed(
            title="📜 Panneau de rôles",
            description="Cliquez sur un bouton pour toggler vos rôles !",
            color=discord.Color.blue()
        )
        for cat in sess["categories"]:
            mention = (
                " ".join(f"<@&{rid}>" for rid in sess["roles"].get(cat, []))
                or "_(vide)_"
            )
            embed.add_field(name=cat, value=mention, inline=False)

        public_view = View(timeout=None)
        for cat in sess["categories"]:
            btn = Button(
                label=cat,
                style=discord.ButtonStyle.secondary,
                custom_id=f"toggle_{cat}"
            )
            public_view.add_item(btn)

        channel = interaction.channel  # type: ignore
        msg = await channel.send(embed=embed, view=public_view)
        await msg.pin()

        await role_panel_collection.insert_one({
            "guild_id": guild_id,
            "channel_id": channel.id,
            "message_id": msg.id,
            "categories": [
                {"name": c, "roles": sess["roles"][c]}
                for c in sess["categories"]
            ]
        })

        sess["action"] = "modify"
        sess["panel_ch"] = channel.id
        sess["panel_msg"] = msg.id

        await interaction.response.send_message("✅ Panneau envoyé et épinglé.", ephemeral=True)
        # Mise à jour de la view privée
        await sess["view"].update_embed(interaction)

    async def start_modify(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        doc = await role_panel_collection.find_one({"guild_id": guild_id})
        if not doc:
            return await interaction.response.send_message(
                MESSAGES["NOT_FOUND_PANEL"], ephemeral=True
            )

        cats = [c["name"] for c in doc["categories"]]
        roles = {c["name"]: c["roles"] for c in doc["categories"]}
        view = SetupView(interaction.user, self, guild_id)
        self.sessions[guild_id] = {
            "action": "modify",
            "categories": cats,
            "roles": roles,
            "view": view,
            "panel_ch": doc["channel_id"],
            "panel_msg": doc["message_id"],
        }

        embed = discord.Embed(
            title="♻️ Modification du panneau",
            description="Ajustez catégories et rôles ci-dessous",
            color=discord.Color.orange()
        ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    async def delete_panel(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        sess = self.sessions.get(guild_id)
        if not sess or sess["action"] != "modify":
            return await interaction.response.send_message(
                MESSAGES["NOT_FOUND_PANEL"], ephemeral=True
            )

        # Désépingler le message public
        ch = self.bot.get_channel(sess["panel_ch"])  # type: ignore
        if ch:
            try:
                msg = await ch.fetch_message(sess["panel_msg"])  # type: ignore
                await msg.unpin()
            except:
                pass

        await role_panel_collection.delete_one({"guild_id": guild_id})

        # Désactiver la view privée
        for c in sess["view"].children:
            c.disabled = True
        if sess["view"].message:
            await sess["view"].message.edit(
                content="🗑️ Panneau supprimé.", view=sess["view"]
            )

        self.sessions.pop(guild_id)
        await interaction.response.send_message("🗑️ Configuration supprimée.", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        data = interaction.data or {}
        if data.get("component_type") == 2 and data.get("custom_id", "").startswith("toggle_"):
            cat = data["custom_id"].removeprefix("toggle_")
            doc = await role_panel_collection.find_one({
                "guild_id": interaction.guild_id,
                "message_id": interaction.message.id  # type: ignore
            })
            if not doc:
                return
            roles = next((c["roles"] for c in doc["categories"] if c["name"] == cat), [])
            for rid in roles:
                role = interaction.guild.get_role(rid)
                if role:
                    if role in interaction.user.roles:
                        await interaction.user.remove_roles(role)
                    else:
                        await interaction.user.add_roles(role)
            await interaction.response.defer()


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))
