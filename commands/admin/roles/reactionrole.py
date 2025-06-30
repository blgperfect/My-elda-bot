import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, RoleSelect
from typing import List
from datetime import datetime
from bson import ObjectId

from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES
from config.mongo import role_panels

# ===== MODALS =====
class CategoryModal(Modal, title="Nouvelle catégorie"):
    name = TextInput(label="Nom de la catégorie", placeholder="ex: personnalité", max_length=32)

    def __init__(self, guild_id: int, menu_msg_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.menu_msg_id = menu_msg_id

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        # Limite de 5 catégories
        count = await role_panels.count_documents({"guild_id": self.guild_id})
        if count >= 5:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Limite atteinte", description="5 catégories max.", color=EMBED_COLOR
                ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL), ephemeral=True
            )
        # Catégorie existante ?
        if await role_panels.find_one({"guild_id": self.guild_id, "category": name}):
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Existe déjà", description=f"**{name}** existe.", color=EMBED_COLOR
                ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL), ephemeral=True
            )
        # Ajouter
        await role_panels.insert_one({"guild_id": self.guild_id, "category": name, "roles": []})
        # Mettre à jour menu
        Cog = interaction.client.get_cog("PanelReaction")
        await Cog.update_menu_embed(interaction, self.menu_msg_id)
        await interaction.response.edit_message(content=f"✅ Catégorie **{name}** ajoutée.", view=None)

class RoleModal(Modal, title="Gestion des rôles"):
    def __init__(self, guild_id: int, cat_id: ObjectId, menu_msg_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.cat_id = cat_id
        self.menu_msg_id = menu_msg_id
        self.add_item(RoleSelect(
            placeholder="Sélectionnez jusqu'à 10 rôles",
            min_values=0,
            max_values=10,
            custom_id="role_select"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        selected: List[discord.Role] = self.children[0].values  # type: ignore
        role_ids = [r.id for r in selected]
        # Mise à jour
        await role_panels.update_one(
            {"_id": self.cat_id}, {"$set": {"roles": role_ids}}
        )
        # Update menu
        Cog = interaction.client.get_cog("PanelReaction")
        await Cog.update_menu_embed(interaction, self.menu_msg_id)
        await interaction.response.edit_message(content="✅ Rôles mis à jour.", view=None)

# ===== VIEWS =====
class ConfigView(View):
    def __init__(self, guild_id: int, menu_msg_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.menu_msg_id = menu_msg_id
        self.refresh()

    def refresh(self):
        self.clear_items()
        # Bouton ajouter catégorie
        self.add_item(Button(label="➕ Ajouter catégorie", style=discord.ButtonStyle.success, custom_id="add_cat"))
        # Boutons catégories existantes (max 5)
        # On va ajouter dynamiquement via callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator

    @discord.ui.button(label="➕ Ajouter catégorie", style=discord.ButtonStyle.success, custom_id="add_cat")
    async def add_category(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(CategoryModal(self.guild_id, self.menu_msg_id))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class PanelReaction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="panelreaction", description="Configurez votre panneau de rôles.")
    @app_commands.checks.has_permissions(administrator=True)
    async def panelreaction(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = await self.build_menu_embed(guild.id)
        view = ConfigView(guild.id, None)
        msg = await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        # récupérer message_id
        sent = await interaction.original_response()
        view.menu_msg_id = sent.id

    async def build_menu_embed(self, guild_id: int) -> discord.Embed:
        panels = await role_panels.find({"guild_id": guild_id}).to_list(length=5)
        desc = ""
        for p in panels:
            guild = self.bot.get_guild(p["guild_id"])
            roles = [guild.get_role(r) for r in p.get("roles", [])]
            names = ', '.join(r.name for r in roles if r)
            desc += f"**{p['category']}**: {names or '_aucun_'}\n"
        embed = discord.Embed(
            title="Panneau de catégories",
            description=desc or "_Aucune catégorie_",
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        return embed

    async def update_menu_embed(self, interaction: discord.Interaction, msg_id: int):
        guild = interaction.guild
        embed = await self.build_menu_embed(guild.id)
        chan = interaction.channel
        msg = await chan.fetch_message(msg_id)
        # Reconstruire la view
        view = ConfigView(guild.id, msg_id)
        # Ajouter boutons catégories
        panels = await role_panels.find({"guild_id": guild.id}).to_list(length=5)
        for p in panels:
            view.add_item(Button(label=p['category'], style=discord.ButtonStyle.primary,
                                 custom_id=f"cat_{p['_id']}", row=1))
        # Bouton gérer rôles (sera accolé)
        # On gère callback via une commande de l'interaction
        await msg.edit(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data.get('custom_id', '')
        if custom_id.startswith('cat_'):
            # Gérer rôles pour cette catégorie
            cat_id = ObjectId(custom_id.split('_',1)[1])
            await interaction.response.send_modal(RoleModal(interaction.guild.id, cat_id, interaction.message.id))

async def setup(bot: commands.Bot):
    await bot.add_cog(PanelReaction(bot))
