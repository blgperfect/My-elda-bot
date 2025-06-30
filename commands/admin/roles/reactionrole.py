# commands/admin/roles/reactionrole.py

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL
from config.mongo import role_panels
from datetime import datetime

# === Contraintes ===
MAX_CATEGORIES = 10
MAX_ROLES_PER_CATEGORY = 25
MAX_LABEL_LENGTH = 100

# --- Modals ---

class AddCategoryModal(Modal):
    label = TextInput(label="Nom de la catégorie", max_length=MAX_LABEL_LENGTH)
    ctype = TextInput(label="Type (exclusive/multi)", placeholder="exclusive ou multi", max_length=10)

    def __init__(self, author: discord.Member):
        super().__init__(title="➕ Ajouter une catégorie")
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)
        label = self.label.value.strip()
        ctype = self.ctype.value.strip().lower()
        if ctype not in ("exclusive", "multi"):
            return await interaction.response.send_message("❌ Type invalide.", ephemeral=True)

        doc = await role_panels.find_one({"guild_id": interaction.guild.id})
        cats = doc["categories"] if doc else []
        if len(cats) >= MAX_CATEGORIES:
            return await interaction.response.send_message(f"❌ Max {MAX_CATEGORIES} catégories.", ephemeral=True)

        new_id = max((c["id"] for c in cats), default=0) + 1
        new_cat = {"id": new_id, "label": label, "type": ctype, "roles": []}
        if doc:
            await role_panels.update_one({"_id": doc["_id"]}, {"$push": {"categories": new_cat}})
        else:
            await role_panels.insert_one({"guild_id": interaction.guild.id, "categories": [new_cat]})

        await interaction.response.send_message(f"✅ Catégorie **{label}** (ID `{new_id}`) créée.", ephemeral=True)

class AddRoleModal(Modal):
    cat_id = TextInput(label="ID de la catégorie", placeholder="Ex: 1")
    role = TextInput(label="Rôle (mention ou ID)", placeholder="<@&123...>")
    label = TextInput(label="Libellé du bouton", max_length=MAX_LABEL_LENGTH)

    def __init__(self, author: discord.Member):
        super().__init__(title="➕ Ajouter un rôle")
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)

        try:
            cat_id = int(self.cat_id.value.strip())
        except:
            return await interaction.response.send_message("❌ Catégorie invalide.", ephemeral=True)

        # récupère le rôle
        raw = self.role.value.strip()
        if raw.isdigit():
            rid = int(raw)
        elif raw.startswith("<@&") and raw.endswith(">"):
            rid = int(raw[3:-1])
        else:
            return await interaction.response.send_message("❌ Format de rôle invalide.", ephemeral=True)

        role_obj = interaction.guild.get_role(rid)
        if not role_obj:
            return await interaction.response.send_message("❌ Rôle introuvable.", ephemeral=True)

        lbl = self.label.value.strip()
        doc = await role_panels.find_one({"guild_id": interaction.guild.id})
        cat = next((c for c in doc["categories"] if c["id"] == cat_id), None)
        if not cat:
            return await interaction.response.send_message("❌ Catégorie introuvable.", ephemeral=True)
        if len(cat["roles"]) >= MAX_ROLES_PER_CATEGORY:
            return await interaction.response.send_message(f"❌ Max {MAX_ROLES_PER_CATEGORY} rôles.", ephemeral=True)
        if any(r["role_id"] == rid for r in cat["roles"]):
            return await interaction.response.send_message("❌ Rôle déjà présent.", ephemeral=True)

        await role_panels.update_one(
            {"_id": doc["_id"], "categories.id": cat_id},
            {"$push": {"categories.$.roles": {"role_id": rid, "label": lbl}}}
        )
        await interaction.response.send_message(f"✅ Rôle **{lbl}** ajouté à cat `{cat_id}`.", ephemeral=True)

class RemoveRoleModal(Modal):
    cat_id = TextInput(label="ID de la catégorie", placeholder="Ex: 1")
    role_index = TextInput(label="Index du rôle (0-based)", placeholder="Ex: 0")

    def __init__(self, author: discord.Member):
        super().__init__(title="➖ Retirer un rôle")
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)

        try:
            cat_id = int(self.cat_id.value.strip())
            idx = int(self.role_index.value.strip())
        except:
            return await interaction.response.send_message("❌ Entrée invalide.", ephemeral=True)

        doc = await role_panels.find_one({"guild_id": interaction.guild.id})
        cat = next((c for c in doc["categories"] if c["id"] == cat_id), None)
        if not cat or idx<0 or idx>=len(cat["roles"]):
            return await interaction.response.send_message("❌ Catégorie ou index invalide.", ephemeral=True)

        await role_panels.update_one(
            {"_id": doc["_id"], "categories.id": cat_id},
            {"$unset": {f"categories.$.roles.{idx}": 1}}
        )
        await role_panels.update_one(
            {"_id": doc["_id"]},
            {"$pull": {"categories.$.roles": None}}
        )
        await interaction.response.send_message(f"✅ Rôle à l’index `{idx}` retiré.", ephemeral=True)

class PublishModal(Modal):
    channel = TextInput(label="Salon (mention ou ID)", placeholder="#général ou 123...")

    def __init__(self, author: discord.Member):
        super().__init__(title="📤 Publier le menu")
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)

        raw = self.channel.value.strip()
        if raw.isdigit():
            ch = interaction.guild.get_channel(int(raw))
        elif raw.startswith("<#") and raw.endswith(">"):
            ch = interaction.guild.get_channel(int(raw[2:-1]))
        else:
            return await interaction.response.send_message("❌ Format invalide.", ephemeral=True)
        if not ch:
            return await interaction.response.send_message("❌ Salon introuvable.", ephemeral=True)

        doc = await role_panels.find_one({"guild_id": interaction.guild.id})
        cats = doc["categories"] if doc else []
        embed = discord.Embed(
            title="𓈒𖥔˚｡˖ 𝐑𝐎𝐋𝐄𝐒 𝐈𝐍𝐓𝐄𝐑𝐀𝐂𝐓𝐈𝐅𝐒 ˖ ࣪⭑",
            description="**Cliquez sur les boutons pour gérer vos rôles.**",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = View(timeout=None)
        for c in cats:
            all_ids = [r["role_id"] for r in c["roles"]]
            for r in c["roles"]:
                lbl = r["label"][:MAX_LABEL_LENGTH]
                if c["type"] == "exclusive":
                    btn = Button(label=lbl, style=discord.ButtonStyle.secondary, custom_id=f"excl:{r['role_id']}:{','.join(map(str,all_ids))}")
                else:
                    btn = Button(label=lbl, style=discord.ButtonStyle.secondary, custom_id=f"multi:{r['role_id']}")
                view.add_item(btn)
        msg = await ch.send(embed=embed, view=view)
        # remplacer custom_id pour inclure message_id => gestion dans listener
        # stocker mapping emoji-less dans base
        await role_panels.update_one(
            {"_id": doc["_id"]},
            {"$set": {"message_id": msg.id}}
        )
        await interaction.response.send_message(f"✅ Menu publié dans {ch.mention}", ephemeral=True)


# --- Cog unique ---

class ReactionPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rolesetup", description="Menu unique pour configurer et publier votre panneau")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rolesetup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ Configuration du panneau de rôles",
            description=(
                "Sélectionnez une action :\n"
                "• ➕ Add category\n"
                "• ➖ Remove category\n"
                "• 📋 List categories\n"
                "• ➕ Add role\n"
                "• ➖ Remove role\n"
                "• 📤 Publish menu"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = View(timeout=None)
        view.add_item(Select(
            placeholder="→ Choisissez une action…",
            custom_id="main_menu",
            options=[
                discord.SelectOption(label="➕ Ajouter catégorie", value="add_cat"),
                discord.SelectOption(label="➖ Supprimer catégorie", value="remove_cat"),
                discord.SelectOption(label="📋 Lister catégories", value="list_cat"),
                discord.SelectOption(label="➕ Ajouter rôle", value="add_role"),
                discord.SelectOption(label="➖ Retirer rôle", value="remove_role"),
                discord.SelectOption(label="📤 Publier le menu", value="publish"),
            ]
        ))
        async def menu_callback(select, inter: discord.Interaction):
            if inter.user != interaction.user:
                return await inter.response.send_message("❌ Non autorisé.", ephemeral=True)
            v = select.values[0]
            if v == "add_cat":
                return await inter.response.send_modal(AddCategoryModal(inter.user))
            if v == "remove_cat":
                return await CategorySelectView(inter.user, "remove_category").setup(inter)
            if v == "list_cat":
                doc = await role_panels.find_one({"guild_id": inter.guild.id})
                cats = doc["categories"] if doc else []
                if not cats:
                    return await inter.response.send_message("❌ Aucune catégorie.", ephemeral=True)
                e = discord.Embed(title="📂 Catégories", color=EMBED_COLOR)
                for c in cats:
                    e.add_field(name=f"{c['id']} – {c['label']}", value=f"type `{c['type']}`, rôles `{len(c['roles'])}`", inline=False)
                e.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
                return await inter.response.send_message(embed=e, ephemeral=True)
            if v == "add_role":
                return await AddRoleModal(inter.user).send(inter)
            if v == "remove_role":
                return await RemoveRoleModal(inter.user).send(inter)
            if v == "publish":
                return await PublishModal(inter.user).send(inter)

        view.children[0].callback = menu_callback
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # gestion des boutons exclusifs/multi
        if not interaction.data or interaction.data.get("component_type") != 2:
            return
        cid = interaction.data.get("custom_id","")
        if ":" not in cid:
            return
        mode, rid, *rest = cid.split(":")
        role_id = int(rid)
        member = interaction.user
        role = interaction.guild.get_role(role_id)
        if mode == "excl":
            all_ids = list(map(int, rest[0].split(","))) if rest else []
            for ar in all_ids:
                r = interaction.guild.get_role(ar)
                if r in member.roles and ar != role_id:
                    await member.remove_roles(r)
        if role in member.roles:
            await member.remove_roles(role)
            msg = f"❌ {role.name} retiré."
        else:
            await member.add_roles(role)
            msg = f"✅ {role.name} attribué."
        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionPanel(bot))
