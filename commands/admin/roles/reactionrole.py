import re
import traceback

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

def _color_to_int(col):
    # Retourne la valeur hexadécimale sous forme d'int, que col soit discord.Color ou int
    return col.value if isinstance(col, discord.Color) else col

# --- Modals pour édition de champs ---
class TitleModal(Modal, title="Modifier le titre du panneau"):
    input_title = TextInput(label="Titre du panneau", max_length=256)

    def __init__(self, parent_view: "ConfigView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        if self.input_title.value.strip():
            sess["panel_title"] = self.input_title.value.strip()
        await self.parent_view.update_embed(interaction)

class DescModal(Modal, title="Modifier la description du panneau"):
    input_desc = TextInput(
        label="Description du panneau",
        style=discord.TextStyle.paragraph,
        max_length=2048
    )

    def __init__(self, parent_view: "ConfigView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        if self.input_desc.value.strip():
            sess["panel_desc"] = self.input_desc.value.strip()
        await self.parent_view.update_embed(interaction)

class ImageModal(Modal, title="Ajouter/Modifier une image (URL)"):
    input_url = TextInput(label="URL de l'image (optionnel)", max_length=2048, required=False)

    def __init__(self, parent_view: "ConfigView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        url = self.input_url.value.strip()
        if url and not re.match(r"^https?://", url):
            return await interaction.response.send_message("URL invalide.", ephemeral=True)
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        sess["panel_image_url"] = url or None
        await self.parent_view.update_embed(interaction)

class ColorModal(Modal, title="Modifier la couleur du panneau"):
    input_color = TextInput(label="Couleur hex (sans #)", max_length=6)

    def __init__(self, parent_view: "ConfigView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.input_color.value.strip()
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
            return await interaction.response.send_message("Couleur invalide.", ephemeral=True)
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        sess["panel_color"] = int(raw, 16)
        await self.parent_view.update_embed(interaction)

class CategoryModal(Modal, title="Ajouter jusqu’à 5 catégories"):
    cat1 = TextInput(label="Catégorie #1", max_length=50, required=False)
    cat2 = TextInput(label="Catégorie #2", max_length=50, required=False)
    cat3 = TextInput(label="Catégorie #3", max_length=50, required=False)
    cat4 = TextInput(label="Catégorie #4", max_length=50, required=False)
    cat5 = TextInput(label="Catégorie #5", max_length=50, required=False)

    def __init__(self, parent_view: "ConfigView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        for val in (
            self.cat1.value.strip(),
            self.cat2.value.strip(),
            self.cat3.value.strip(),
            self.cat4.value.strip(),
            self.cat5.value.strip(),
        ):
            if val and val not in sess["categories"] and len(sess["categories"]) < 5:
                sess["categories"].append(val)
                sess["roles"][val] = []
        await self.parent_view.update_embed(interaction)

# --- Selects pour suppression ---
class CategoryRemoveSelect(Select):
    def __init__(self, parent_view: "ConfigView"):
        sess = parent_view.cog.sessions[parent_view.guild_id]
        options = [discord.SelectOption(label=c, value=c) for c in sess["categories"]]
        super().__init__(
            placeholder="Supprimer catégories…",
            min_values=1, max_values=len(options),
            options=options,
            custom_id="remove_cat_sel"
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        for c in self.values:
            sess["categories"].remove(c)
            sess["roles"].pop(c, None)
        await self.parent_view.update_embed(interaction)
        await interaction.delete_original_response()

class RolesRemoveSelect(Select):
    def __init__(self, parent_view: "ConfigView", category: str):
        sess = parent_view.cog.sessions[parent_view.guild_id]
        options = [
            discord.SelectOption(label=str(r), value=str(r))
            for r in sess["roles"].get(category, [])
        ]
        super().__init__(
            placeholder=f"Supprimer rôles de {category}…",
            min_values=1, max_values=len(options),
            options=options,
            custom_id="remove_role_sel"
        )
        self.parent_view = parent_view
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        sess = self.parent_view.cog.sessions[self.parent_view.guild_id]
        sess["roles"][self.category] = [
            r for r in sess["roles"][self.category]
            if str(r) not in self.values
        ]
        await self.parent_view.update_embed(interaction)
        await interaction.delete_original_response()

# --- Vue de configuration principale ---
class ConfigView(View):
    def __init__(self, author: discord.Member, cog: commands.Cog, guild_id: int):
        super().__init__(timeout=None)
        self.author = author
        self.cog = cog
        self.guild_id = guild_id
        self.message: discord.Message | None = None

    @discord.ui.select(
        placeholder="Actions…",
        min_values=1, max_values=1,
        custom_id="cfg_menu",
        options=[
            discord.SelectOption(label="Modifier titre", value="title"),
            discord.SelectOption(label="Modifier description", value="desc"),
            discord.SelectOption(label="Modifier image", value="image"),
            discord.SelectOption(label="Modifier couleur", value="color"),
            discord.SelectOption(label="Ajouter catégories", value="addcat"),
            discord.SelectOption(label="Ajouter rôles", value="addroles"),
            discord.SelectOption(label="Supprimer catégories", value="removecat"),
            discord.SelectOption(label="Supprimer rôles", value="removeroles"),
        ]
    )
    async def cfg_menu(self, interaction: discord.Interaction, select: Select):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        action = select.values[0]
        if action == "title":
            await interaction.response.send_modal(TitleModal(self))
        elif action == "desc":
            await interaction.response.send_modal(DescModal(self))
        elif action == "image":
            await interaction.response.send_modal(ImageModal(self))
        elif action == "color":
            await interaction.response.send_modal(ColorModal(self))
        elif action == "addcat":
            await interaction.response.send_modal(CategoryModal(self))
        elif action == "addroles":
            await self.open_role_select(interaction)
        elif action == "removecat":
            await self.open_remove_cat(interaction)
        elif action == "removeroles":
            await self.open_remove_roles(interaction)

    @discord.ui.button(
        label="✅ Envoyer/Mise à jour",
        style=discord.ButtonStyle.success,
        custom_id="cfg_finish"
    )
    async def finish(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await self.cog.finalize_panel(self.guild_id, interaction)

    async def open_role_select(self, interaction: discord.Interaction):
        sess = self.cog.sessions[self.guild_id]
        options = [discord.SelectOption(label=c, value=c) for c in sess["categories"]]

        class CatSel(Select):
            def __init__(sel):
                super().__init__(
                    placeholder="Catégorie…",
                    min_values=1, max_values=1,
                    options=options,
                    custom_id="add_role_cat"
                )

            async def callback(sel, inner: discord.Interaction):
                cat = sel.values[0]
                role_selector = RoleSelect(placeholder=f"Rôles pour {cat}", min_values=1, max_values=10)
                async def role_callback(resp: discord.Interaction):
                    ss = self.cog.sessions[self.guild_id]
                    ss["roles"][cat] = [r.id for r in role_selector.values]
                    await self.update_embed(resp)
                    await resp.delete_original_response()
                role_selector.callback = role_callback
                v2 = View(timeout=None)
                v2.add_item(role_selector)
                await inner.response.send_message(f"Choisissez jusqu’à 10 rôles pour **{cat}**", view=v2, ephemeral=True)

        v = View(timeout=None)
        v.add_item(CatSel())
        await interaction.response.send_message("Sélectionnez catégorie :", view=v, ephemeral=True)

    async def open_remove_cat(self, interaction: discord.Interaction):
        select = CategoryRemoveSelect(self)
        v = View(timeout=None)
        v.add_item(select)
        await interaction.response.send_message("Sélectionnez catégories à retirer :", view=v, ephemeral=True)

    async def open_remove_roles(self, interaction: discord.Interaction):
        sess = self.cog.sessions[self.guild_id]
        opts = [discord.SelectOption(label=c, value=c) for c in sess["categories"]]

        class CSel(Select):
            def __init__(sel):
                super().__init__(placeholder="Catégorie…", min_values=1, max_values=1, options=opts, custom_id="rem_role_cat")

            async def callback(sel, inner: discord.Interaction):
                category = sel.values[0]
                rsel = RolesRemoveSelect(self, category)
                v2 = View(timeout=None)
                v2.add_item(rsel)
                await inner.response.send_message(f"Rôles à retirer de **{category}** :", view=v2, ephemeral=True)

        v = View(timeout=None)
        v.add_item(CSel())
        await interaction.response.send_message("Sélectionnez catégorie :", view=v, ephemeral=True)

    async def update_embed(self, interaction: discord.Interaction):
        sess = self.cog.sessions[self.guild_id]
        color_int = sess["panel_color"] if isinstance(sess["panel_color"], int) else sess["panel_color"].value
        embed = discord.Embed(
            title=sess["panel_title"],
            description=sess["panel_desc"],
            color=discord.Color(color_int)
        )
        if sess.get("panel_image_url"):
            embed.set_image(url=sess["panel_image_url"])
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.clear_fields()
        for cat in sess["categories"]:
            vals = sess["roles"].get(cat, [])
            embed.add_field(name=cat, value=(" ".join(f"<@&{r}>" for r in vals) or "_(vide)_"), inline=False)

        if self.message:
            await self.message.edit(embed=embed, view=self)
            await interaction.response.defer()
        else:
            await interaction.response.defer()

# --- Boutons publics pour le panneau final ---
class CategoryButton(Button):
    def __init__(self, category: str):
        super().__init__(label=category, style=discord.ButtonStyle.primary, custom_id=f"category_{category}")

    async def callback(self, interaction: discord.Interaction):
        doc = await role_panel_collection.find_one({
            "guild_id": interaction.guild_id,
            "message_id": interaction.message.id
        })
        if not doc:
            return await interaction.response.defer()
        roles = next((c["roles"] for c in doc["categories"] if c["name"] == self.label), [])
        v = View(timeout=None)
        for rid in roles:
            role = interaction.guild.get_role(rid)
            if role:
                v.add_item(RoleButton(rid, role.name))
        await interaction.response.send_message(f"**{self.label}** : choisissez un rôle", view=v, ephemeral=True)

class RoleButton(Button):
    def __init__(self, role_id: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id=f"role_{role_id}")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.defer()
        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
            else:
                await interaction.user.add_roles(role)
        except Exception:
            pass
        await interaction.response.defer()

# --- Menu principal /rolesetup ---
class MainView(View):
    def __init__(self, author: discord.Member, cog: commands.Cog, has_panel: bool):
        super().__init__(timeout=None)
        self.author = author
        self.cog = cog
        # Activer/désactiver selon existence
        self.children[0].disabled = has_panel    # Créer
        self.children[1].disabled = not has_panel  # Modifier
        self.children[2].disabled = not has_panel  # Supprimer

    @discord.ui.button(label="🆕 Créer panneau", style=discord.ButtonStyle.primary, custom_id="main_create")
    async def main_create(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        guild = interaction.guild_id
        self.cog.sessions[guild] = {
            "categories": [],
            "roles": {},
            "panel_title": "📜 Panneau de rôles",
            "panel_desc": "Veuillez sélectionner vos rôles en appuyant sur les boutons.",
            "panel_image_url": None,
            "panel_color": _color_to_int(EMBED_COLOR),
            "action": "create"
        }
        view = ConfigView(self.author, self.cog, guild)
        embed = discord.Embed(
            title="⚙️ Configuration du panneau",
            description="Aucune catégorie définie pour l’instant",
            color=EMBED_COLOR
        ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @discord.ui.button(label="✏️ Modifier panneau", style=discord.ButtonStyle.secondary, custom_id="main_modify")
    async def main_modify(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        guild = interaction.guild_id
        doc = await role_panel_collection.find_one({"guild_id": guild})
        default_hex = f"{_color_to_int(EMBED_COLOR):06x}"
        sess = {
            "categories": [c["name"] for c in doc["categories"]],
            "roles": {c["name"]: c["roles"] for c in doc["categories"]},
            "panel_title": doc.get("title", "📜 Panneau de rôles"),
            "panel_desc": doc.get("description", "Veuillez sélectionner vos rôles en appuyant sur les boutons."),
            "panel_image_url": doc.get("image_url"),
            "panel_color": int(doc.get("color", default_hex), 16),
            "action": "modify"
        }
        self.cog.sessions[guild] = sess

        view = ConfigView(self.author, self.cog, guild)
        embed = discord.Embed(
            title=sess["panel_title"],
            description=sess["panel_desc"],
            color=discord.Color(sess["panel_color"])
        )
        if sess.get("panel_image_url"):
            embed.set_image(url=sess["panel_image_url"])
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        for cat in sess["categories"]:
            vals = sess["roles"][cat]
            embed.add_field(name=cat, value=(" ".join(f"<@&{r}>" for r in vals) or "_(vide)_"), inline=False)

        await interaction.response.edit_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @discord.ui.button(label="🗑️ Supprimer panneau", style=discord.ButtonStyle.danger, custom_id="main_delete")
    async def main_delete(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await self.cog.delete_panel(interaction)

# --- Le Cog principal ---
class ReactionRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, dict] = {}

    @app_commands.command(
        name="rolesetup",
        description="Créer ou modifier un panneau de rôles interactif"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rolesetup(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild_id
            doc = await role_panel_collection.find_one({"guild_id": guild})
            has_panel = bool(doc)
            view = MainView(interaction.user, self, has_panel)
            desc = (f"Vous avez déjà un panneau dans <#{doc['channel_id']}>:{doc['message_id']}"
                    if has_panel else "Créez un nouveau panneau.")
            embed = discord.Embed(
                title="Configuration panneau de rôles",
                description=desc,
                color=EMBED_COLOR
            ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(MESSAGES["INTERNAL_ERROR"], ephemeral=True)

    @rolesetup.error
    async def rolesetup_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        else:
            traceback.print_exc()
            await interaction.response.send_message(MESSAGES["INTERNAL_ERROR"], ephemeral=True)

    async def finalize_panel(self, guild_id: int, interaction: discord.Interaction):
        sess = self.sessions[guild_id]
        embed_pub = discord.Embed(
            title=sess["panel_title"],
            description=sess["panel_desc"],
            color=discord.Color(sess["panel_color"])
        )
        if sess.get("panel_image_url"):
            embed_pub.set_image(url=sess["panel_image_url"])
        embed_pub.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        public_view = View(timeout=None)
        for cat in sess["categories"]:
            public_view.add_item(CategoryButton(cat))

        msg = await interaction.channel.send(embed=embed_pub, view=public_view)

        data = {
            "guild_id": guild_id,
            "channel_id": interaction.channel.id,
            "message_id": msg.id,
            "title": sess["panel_title"],
            "description": sess["panel_desc"],
            "image_url": sess.get("panel_image_url"),
            "color": f"{sess['panel_color']:06x}",
            "categories": [{"name": c, "roles": sess["roles"][c]} for c in sess["categories"]],
        }

        if sess["action"] == "create":
            await role_panel_collection.insert_one(data)
            await interaction.response.send_message("✅ Panneau envoyé.", ephemeral=True)
        else:
            await role_panel_collection.update_one({"guild_id": guild_id}, {"$set": data})
            await interaction.response.send_message("✅ Panneau mis à jour.", ephemeral=True)

    async def delete_panel(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        doc = await role_panel_collection.find_one({"guild_id": guild_id})
        if not doc:
            return await interaction.response.send_message(MESSAGES["NOT_FOUND_PANEL"], ephemeral=True)
        channel = interaction.guild.get_channel(doc["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(doc["message_id"])
                await msg.unpin()
                await msg.delete()
            except:
                pass
        await role_panel_collection.delete_one({"guild_id": guild_id})
        await interaction.response.send_message("🗑️ Panneau supprimé.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))
