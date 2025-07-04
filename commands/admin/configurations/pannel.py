"""Ticket panel : UX 100 % boutons + formulaires (v2.0)
========================================================

⚡️ **NOUVEAUTÉS MAJEURES**
-------------------------
1. **Plus aucun message à taper** :
   * Modal `BasicsModal` recueille titre/description/footer en une fois.
   * Bouton "➕ Ajouter une catégorie" → Modal `CategoryModal` (nom + desc)
     puis vue `CatRoleParentView` avec deux Select (rôles + catégorie‑parente).
2. Vue `ConfigView` affiche en permanence les boutons :
   * 📂 Choisir transcript
   * ➕ Ajouter une catégorie
   * ✅ Terminer la config
3. Tous les helpers & fix @everyone sont conservés.
4. API slash‑commandes inchangée.

Drop‑in : remplace ton ancien `panel.py`.
"""
from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Sequence

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import (
    Button,
    ChannelSelect,
    Modal,
    RoleSelect,
    Select,
    TextInput,
    View,
)
from pymongo import ReturnDocument

from config.mongo import db
from config.params import EMBED_COLOR, EMBED_FOOTER_ICON_URL, EMBED_FOOTER_TEXT, MESSAGES

log = logging.getLogger(__name__)

MAX_CATEGORIES = 5
TICKET_COLLECTION = db["ticket"]

# ---------------------------------------------------------------------------
# Dataclasses & helpers
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CategoryCfg:
    name: str
    description: str
    roles: List[int]
    discord_category: int

    @property
    def pretty(self) -> str:
        roles = " ".join(f"<@&{r}>" for r in self.roles)
        return f"**{self.name}** — {roles} — Parent : <#{self.discord_category}>"


def build_embed(data: Dict[str, Any], cats: Sequence[CategoryCfg]) -> discord.Embed:
    e = discord.Embed(title="📋 Configuration des tickets", color=EMBED_COLOR)
    e.add_field(name="🎫 Titre", value=data.get("title") or "❌ Non défini", inline=False)
    e.add_field(name="📝 Description", value=data.get("description") or "❌ Non défini", inline=False)
    e.add_field(name="🔖 Footer", value=data.get("footer") or "❌ Non défini", inline=False)
    tc = data.get("transcript_channel")
    e.add_field(name="📂 Salon transcripts", value=f"<#{tc}>" if tc else "❌ Non défini", inline=False)
    if cats:
        e.add_field(name=f"📚 Catégories ({len(cats)}/{MAX_CATEGORIES})", value="\n".join(c.pretty for c in cats), inline=False)
    else:
        e.add_field(name=f"📚 Catégories (0/{MAX_CATEGORIES})", value="Aucune", inline=False)
    e.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
    return e


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------

class BasicsModal(Modal, title="Infos principales du panneau"):
    titre: TextInput = TextInput(label="Titre", max_length=80)
    description: TextInput = TextInput(label="Description", style=discord.TextStyle.long, max_length=400)
    footer: TextInput = TextInput(label="Footer (laisser vide pour aucun)", required=False, max_length=100)

    def __init__(self, cfg_view: "ConfigView") -> None:
        super().__init__()
        self.cfg_view = cfg_view

    async def on_submit(self, interaction: discord.Interaction):  # noqa: D401,E501
        self.cfg_view.data.update(
            title=self.titre.value,
            description=self.description.value,
            footer=self.footer.value or None,
        )
        await self.cfg_view.refresh_embed(interaction)
        await interaction.response.send_message("✅ Infos enregistrées.", ephemeral=True)


class CategoryModal(Modal, title="Nouvelle catégorie"):
    name: TextInput = TextInput(label="Nom", max_length=30)
    description: TextInput = TextInput(label="Description", style=discord.TextStyle.long, max_length=200)

    def __init__(self, cfg_view: "ConfigView") -> None:
        super().__init__()
        self.cfg_view = cfg_view

    async def on_submit(self, interaction: discord.Interaction):  # noqa: D401,E501
        # après le Modal on enchaîne avec Selects pour rôles + parent
        await interaction.response.defer(ephemeral=True)
        await self.cfg_view.start_role_parent_select(interaction, self.name.value, self.description.value)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class CatRoleParentView(View):
    """Selects affichés après CategoryModal."""

    def __init__(self, cfg_view: "ConfigView", name: str, desc: str):
        super().__init__(timeout=180)
        self.cfg_view = cfg_view
        self.name = name
        self.desc = desc
        self.role_select = RoleSelect(min_values=1, max_values=5, placeholder="Rôles staff")
        self.cat_select = ChannelSelect(channel_types=[discord.ChannelType.category], placeholder="Catégorie parente")
        self.add_item(self.role_select)
        self.add_item(self.cat_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # noqa: D401,E501
        return interaction.user == self.cfg_view.author

    @discord.ui.button(label="✅ Valider", style=discord.ButtonStyle.success)
    async def validate(self, interaction: discord.Interaction, _btn: Button):
        roles = [r.id for r in self.role_select.values]  # type: ignore[attr-defined]
        parent = self.cat_select.values[0].id  # type: ignore[attr-defined]
        self.cfg_view.categories.append(CategoryCfg(self.name, self.desc, roles, parent))
        await self.cfg_view.refresh_embed(interaction)
        await interaction.response.edit_message(content="Catégorie ajoutée ✔️", view=None)


class ConfigView(View):
    """Vue principale utilisée tout au long de la configuration."""

    def __init__(self, bot: commands.Bot, author: discord.Member, embed_msg: discord.Message):
        super().__init__(timeout=None)
        self.bot = bot
        self.author = author
        self.embed_msg = embed_msg
        self.data: Dict[str, Any] = {}
        self.categories: List[CategoryCfg] = []

    # ---- Helpers --------------------------------------------------------

    async def refresh_embed(self, interaction: discord.Interaction | None = None):
        await self.embed_msg.edit(embed=build_embed(self.data, self.categories), view=self)
        if interaction and interaction.response.is_done():
            return

    # ---- Buttons --------------------------------------------------------

    @discord.ui.button(label="🛠️ Infos panneau", style=discord.ButtonStyle.primary)
    async def basics(self, interaction: discord.Interaction, _btn: Button):
        await interaction.response.send_modal(BasicsModal(self))

    @discord.ui.button(label="📂 Choisir transcript", style=discord.ButtonStyle.secondary)
    async def transcript(self, interaction: discord.Interaction, _btn: Button):
        view = View(timeout=180)
        sel = ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="Salon transcripts")
        view.add_item(sel)

        async def _callback(i: discord.Interaction):  # noqa: D401,E501
            self.data["transcript_channel"] = sel.values[0].id  # type: ignore[attr-defined]
            await self.refresh_embed(i)
            await i.response.edit_message(content="Salon transcripts défini ✔️", view=None)

        sel.callback = _callback  # type: ignore[assignment]
        await interaction.response.send_message("Choisissez…", view=view, ephemeral=True)

    @discord.ui.button(label="➕ Ajouter une catégorie", style=discord.ButtonStyle.success)
    async def add_category(self, interaction: discord.Interaction, _btn: Button):
        if len(self.categories) >= MAX_CATEGORIES:
            return await interaction.response.send_message("Limite atteinte.", ephemeral=True)
        await interaction.response.send_modal(CategoryModal(self))

    @discord.ui.button(label="✅ Terminer", style=discord.ButtonStyle.danger)
    async def finish(self, interaction: discord.Interaction, _btn: Button):
        if not (self.data.get("title") and self.data.get("description") and self.categories):
            return await interaction.response.send_message("Veuillez remplir infos + au moins 1 catégorie.", ephemeral=True)
        await self.save_to_db(interaction.guild)
        await self.embed_msg.edit(embed=discord.Embed(title="🎉 Configuration terminée !", color=EMBED_COLOR), view=None)
        await interaction.response.send_message("Configuration enregistrée.", ephemeral=True)

    # ---- Extra steps ----------------------------------------------------

    async def start_role_parent_select(self, interaction: discord.Interaction, name: str, desc: str):
        view = CatRoleParentView(self, name, desc)
        await interaction.followup.send("Choisissez rôles & parent :", view=view, ephemeral=True)

    async def save_to_db(self, guild: discord.Guild):
        await TICKET_COLLECTION.update_one(
            {"guild_id": str(guild.id)},
            {"$set": {
                "guild_id": str(guild.id),
                "panel_embed": {
                    "title": self.data["title"],
                    "description": self.data["description"],
                    "footer": self.data.get("footer"),
                },
                "transcript_channel": str(self.data.get("transcript_channel")),
                "categories": {c.name: asdict(c) for c in self.categories},
                "ticket_count": 0,
            }},
            upsert=True,
        )


# ---------------------------------------------------------------------------
# Ticket panel view (ping fix kept)
# ---------------------------------------------------------------------------

class TicketPanelView(View):
    def __init__(self, cfg: Dict[str, Any]):
        super().__init__(timeout=None)
        self.cfg = cfg
        sel = Select(placeholder="Choisissez…", options=[discord.SelectOption(label=k) for k in cfg["categories"]])
        sel.callback = self.on_select  # type: ignore[assignment]
        self.add_item(sel)

    async def on_select(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        choice = inter.data["values"][0]  # type: ignore[index]
        cat = self.cfg["categories"][choice]
        gid = str(inter.guild_id)
        topic = f"ticket:{gid}:{inter.user.id}"
        if discord.utils.get(inter.guild.text_channels, topic=topic):
            return await inter.followup.send(MESSAGES.get("TICKET_EXISTS", "Vous avez déjà un ticket."), ephemeral=True)
        doc = await TICKET_COLLECTION.find_one_and_update({"guild_id": gid}, {"$inc": {"ticket_count": 1}}, return_document=ReturnDocument.AFTER)
        name = f"{doc['ticket_count']}-{inter.user.name}"
        overwrites: Dict[Any, discord.PermissionOverwrite] = {
            inter.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            inter.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for rid in cat["roles"]:
            if (role := inter.guild.get_role(int(rid))):
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        parent = inter.guild.get_channel(int(cat["discord_category"]))
        chan = await inter.guild.create_text_channel(name=name, category=parent, topic=topic, overwrites=overwrites)
        mentions = [r.mention for r in overwrites if isinstance(r, discord.Role) and r != inter.guild.default_role]
        emb = discord.Embed(title=self.cfg["panel_embed"]["title"], description=cat["description"], color=EMBED_COLOR)
        await chan.send(content=" ".join(mentions) or None, embed=emb)
        await inter.followup.send(f"Ticket créé : {chan.mention}", ephemeral=True)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="config_tickets", description="Configurer le panneau de tickets")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config_tickets(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        msg = await inter.channel.send(embed=discord.Embed(description="⏳ Préparation…", color=EMBED_COLOR))
        view = ConfigView(self.bot, inter.user, msg)
        await view.refresh_embed(None)

    @app_commands.command(name="panel_tickets", description="Publie le panneau de tickets")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_tickets(self, inter: discord.Interaction, channel: discord.TextChannel):
        cfg = await TICKET_COLLECTION.find_one({"guild_id": str(inter.guild_id)})
        if not cfg:
            return await inter.response.send_message("Configuré nulle part.", ephemeral=True)
        view = TicketPanelView(cfg)
        emb = discord.Embed(title=cfg["panel_embed"]["title"], description=cfg["panel_embed"]["description"], color=EMBED_COLOR)
        if (img := cfg["panel_embed"].get("image")):
            emb.set_image(url=img)
        emb.set_footer(text=cfg["panel_embed"].get("footer", EMBED_FOOTER_TEXT), icon_url=EMBED_FOOTER_ICON_URL)
        await channel.send(embed=emb, view=view)
        await inter.response.send_message(f"Panneau publié dans {channel.mention} ✅", ephemeral=True)


# ---------------------------------------------------------------------------
# Setup for the bot
# ---------------------------------------------------------------------------

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
