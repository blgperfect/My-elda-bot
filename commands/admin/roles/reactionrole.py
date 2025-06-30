import discord
from discord import app_commands, SelectOption
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select, RoleSelect
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL
from config.mongo import role_panels

# === Modal pour créer une catégorie ===
class CategoryModal(Modal, title="Nouvelle catégorie"):
    name = TextInput(
        label="Nom de la catégorie",
        placeholder="ex: personnalité",
        max_length=32
    )

    def __init__(self, guild_id: int, cog: "PanelReaction"):
        super().__init__()
        self.guild_id = guild_id
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        count = await role_panels.count_documents({"guild_id": self.guild_id})
        if count >= 5:
            return await interaction.response.send_message(
                "❌ Limite de 5 catégories atteinte.", ephemeral=True
            )
        if await role_panels.find_one({"guild_id": self.guild_id, "category": name}):
            return await interaction.response.send_message(
                f"❌ La catégorie **{name}** existe déjà.", ephemeral=True
            )
        await role_panels.insert_one({"guild_id": self.guild_id, "category": name, "roles": []})
        # rafraîchir l'embed principal
        await self.cog.refresh_main_embed(self.guild_id)
        await interaction.response.send_message(
            f"✅ Catégorie **{name}** créée.", ephemeral=True
        )

# === View pour ajouter des rôles via sélections ===
class AddRoleView(View):
    def __init__(self, guild_id: int, cog: "PanelReaction"):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.cog = cog
        self.category_id: Optional[str] = None
        # sélection de catégorie
        sel = Select(
            placeholder="Choisissez une catégorie...",
            min_values=1,
            max_values=1,
            options=[],
            custom_id="addrole_cat"
        )
        sel.callback = self.on_category  # type: ignore
        self.add_item(sel)

    async def on_category(self, interaction: discord.Interaction):
        cat_sel: Select = self.children[0]  # type: ignore
        # remplir options si vide
        if not cat_sel.options:
            panels = await role_panels.find({"guild_id": self.guild_id}).to_list(length=5)
            cat_sel.options = [SelectOption(label=p['category'], value=str(p['_id'])) for p in panels]
            if not cat_sel.options:
                cat_sel.options = [SelectOption(label="Aucune catégorie", value="none")]
            await interaction.response.edit_message(view=self)
            return
        # récupérer id
        if cat_sel.values[0] == "none":
            return await interaction.response.send_message("Aucune catégorie disponible.", ephemeral=True)
        self.category_id = cat_sel.values[0]
        # passer à la sélection de rôles
        self.clear_items()
        rol = RoleSelect(
            placeholder="Sélectionnez jusqu'à 10 rôles",
            min_values=1,
            max_values=10,
            custom_id="addrole_roles"
        )
        rol.callback = self.on_roles  # type: ignore
        self.add_item(rol)
        await interaction.response.edit_message(
            content="Choisissez les rôles à ajouter :", view=self
        )

    async def on_roles(self, interaction: discord.Interaction):
        rol_sel: RoleSelect = self.children[0]  # type: ignore
        selected: List[discord.Role] = rol_sel.values  # type: ignore
        # mise à jour DB
        panel = await role_panels.find_one({"_id": ObjectId(self.category_id)})
        existing = [r['role_id'] for r in panel.get('roles', [])]
        to_add = []
        for r in selected:
            if r.id not in existing:
                to_add.append(r)
        if not to_add:
            return await interaction.response.send_message(
                "Aucun nouveau rôle à ajouter.", ephemeral=True
            )
        await role_panels.update_one(
            {"_id": ObjectId(self.category_id)},
            {"$push": {"roles": {"$each": [{"emoji": "🔸", "role_id": r.id} for r in to_add]}}}
        )
        await interaction.response.send_message(
            f"✅ Ajouté: {', '.join(r.name for r in to_add)}.", ephemeral=True
        )
        # rafraîchir embed
        await self.cog.refresh_main_embed(self.guild_id)

# === Vue principale de configuration ===
class PanelConfigView(View):
    def __init__(self, guild_id: int, cog: "PanelReaction"):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.cog = cog
        btn_cat = Button(
            label="➕ Ajouter catégorie",
            style=discord.ButtonStyle.success,
            custom_id="cfg_add_cat"
        )
        btn_cat.callback = self.add_category  # type: ignore
        self.add_item(btn_cat)
        btn_roles = Button(
            label="➕ Ajouter des rôles",
            style=discord.ButtonStyle.primary,
            custom_id="cfg_add_roles"
        )
        btn_roles.callback = self.add_roles  # type: ignore
        self.add_item(btn_roles)

    async def add_category(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CategoryModal(self.guild_id, self.cog))

    async def add_roles(self, interaction: discord.Interaction):
        view = AddRoleView(self.guild_id, self.cog)
        await interaction.response.send_message(
            "Sélectionnez la catégorie puis les rôles :", view=view, ephemeral=True
        )

# === Cog principal ===
class PanelReaction(commands.Cog):
    """Gestion interactive des panneaux de rôles multi-serveurs."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.menu_msg = {}  # guild_id -> message_id

    @app_commands.command(name="panelreaction", description="Configurez votre panneau de rôles.")
    @app_commands.checks.has_permissions(administrator=True)
    async def panelreaction(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Panneau de catégories",
            description="", color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await self.build_main_embed(interaction.guild.id, embed)
        view = PanelConfigView(interaction.guild.id, self)
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        self.menu_msg[interaction.guild.id] = msg.id

    async def build_main_embed(self, guild_id: int, embed: discord.Embed):
        panels = await role_panels.find({"guild_id": guild_id}).to_list(length=5)
        desc = ""
        guild = self.bot.get_guild(guild_id)
        for p in panels:
            names = []
            for r in p.get("roles", []):
                role = guild.get_role(r["role_id"])
                if role:
                    names.append(f"{r['emoji']} <@&{r['role_id']}>")
            desc += f"**{p['category']}**: {', '.join(names) or '_aucun_'}\n"
        embed.description = desc or "_Aucune catégorie_"

    async def refresh_main_embed(self, guild_id: int):
        if guild_id not in self.menu_msg:
            return
        channel = None
        for ch in self.bot.get_all_channels():
            try:
                msg = await ch.fetch_message(self.menu_msg[guild_id])
                channel = ch
                break
            except:
                continue
        if not channel:
            return
        embed = discord.Embed(
            title="Panneau de catégories",
            description="",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await self.build_main_embed(guild_id, embed)
        await channel.get_partial_message(self.menu_msg[guild_id]).edit(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(PanelReaction(bot))
