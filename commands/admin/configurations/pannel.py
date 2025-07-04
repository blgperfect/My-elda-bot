# commands/admin/configurations/pannel.py

import discord
import io
import asyncio
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, ChannelSelect, RoleSelect
from pymongo import ReturnDocument

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
)
from config.mongo import db

ticket_collection = db["ticket"]
MAX_CATEGORIES = 5


def build_embed(data: dict, categories: list[dict], current_question: str = "") -> discord.Embed:
    """Construit l'embed dynamique affichant l'état de la config et la question en cours."""
    embed = discord.Embed(title="📋 Configuration des tickets", color=EMBED_COLOR)
    if current_question:
        embed.add_field(name="❓ Question", value=current_question, inline=False)

    embed.add_field(name="🎫 Titre", value=data.get("title", "❌ Non défini"), inline=False)
    embed.add_field(name="📝 Description", value=data.get("description", "❌ Non défini"), inline=False)
    embed.add_field(name="🔖 Footer", value=data.get("footer", "❌ Non défini"), inline=False)

    transcripts = data.get("transcript_channel")
    embed.add_field(
        name="📂 Salon transcripts",
        value=f"<#{transcripts}>" if transcripts else "❌ Non défini",
        inline=False
    )

    if categories:
        lines = []
        for c in categories:
            roles_mention = " ".join(f"<@&{r}>" for r in c["roles"])
            cat_mention = f"<#{c['discord_category']}>"
            lines.append(f"**{c['name']}** — Rôles : {roles_mention} — Parent : {cat_mention}")
        embed.add_field(
            name=f"📚 Catégories ({len(categories)}/{MAX_CATEGORIES})",
            value="\n".join(lines),
            inline=False
        )
    else:
        embed.add_field(
            name=f"📚 Catégories (0/{MAX_CATEGORIES})",
            value="Aucune pour l'instant",
            inline=False
        )

    embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
    return embed


class HelpView(View):
    """Vue pour le bouton d'aide."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📖 Aide", style=discord.ButtonStyle.secondary, custom_id="help_button")
    async def help(self, interaction: discord.Interaction, button: Button):
        guide = (
            "**Guide Configuration Tickets**\n"
            f"• Répondez dans l'embed mis à jour.\n"
            f"• Max {MAX_CATEGORIES} catégories.\n"
            "• Saisissez chaque nom de catégorie l'un après l'autre.\n"
            "• Tapez `fin` pour terminer l'ajout.\n"
            "• Les salons et rôles seront mentionnés dynamiquement.\n"
        )
        await interaction.response.send_message(guide, ephemeral=True)


class ConfirmRemoveConfigView(View):
    """Confirmation avant suppression de la configuration."""
    def __init__(self, guild_id: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Oui, supprimer", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await ticket_collection.delete_one({"guild_id": self.guild_id})
        await interaction.response.edit_message(
            content="✅ Configuration des tickets supprimée avec succès.",
            view=None
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content="❌ Suppression annulée.",
            view=None
        )


class StartConfigView(View):
    """Vue initiale du panneau de configuration."""
    def __init__(self, channel: discord.TextChannel, disable_start: bool = False):
        super().__init__(timeout=None)
        self.channel = channel
        # bouton Aide
        self.add_item(HelpView().children[0])
        # désactiver le bouton "Commencer" si une config existe déjà
        for child in self.children:
            if isinstance(child, Button) and child.label == "🚀 Commencer la config":
                child.disabled = disable_start

    @discord.ui.button(label="🚀 Commencer la config", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await start_configuration(interaction.client, self.channel, interaction.user)

    @discord.ui.button(label="🗑️ Supprimer config", style=discord.ButtonStyle.danger, custom_id="delete_config")
    async def delete_config(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "⚠️ Voulez-vous vraiment supprimer **toute** la configuration des tickets ?",
            view=ConfirmRemoveConfigView(str(interaction.guild.id)),
            ephemeral=True
        )


class Tickets(commands.Cog):
    """Cog principal pour les commandes tickets."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="config_tickets", description="Démarre la configuration du panneau de tickets")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config_tickets(self, interaction: discord.Interaction):
        existing = await ticket_collection.find_one({"guild_id": str(interaction.guild_id)})
        view = StartConfigView(interaction.channel, disable_start=bool(existing))

        if existing:
            embed = discord.Embed(
                title="⚠️ Configuration existante",
                description="Un panneau de tickets existe déjà. Vous pouvez le supprimer ou le modifier.",
                color=EMBED_COLOR
            )
        else:
            embed = build_embed({}, [], "Cliquez sur 🚀 pour démarrer.")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="panel_tickets", description="Envoie le panneau de tickets dans le salon spécifié")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Salon où poster le panneau de tickets")
    async def panel_tickets(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cfg = await ticket_collection.find_one({"guild_id": str(interaction.guild_id)})
        if not cfg:
            return await interaction.response.send_message("⚠️ Tickets non configurés.", ephemeral=True)

        view = TicketPanelView(cfg)
        embed = discord.Embed(
            title=cfg["panel_embed"]["title"],
            description=cfg["panel_embed"]["description"],
            color=EMBED_COLOR
        )
        if img := cfg["panel_embed"].get("image"):
            embed.set_image(url=img)
        footer = cfg["panel_embed"].get("footer") or EMBED_FOOTER_TEXT
        embed.set_footer(text=footer, icon_url=EMBED_FOOTER_ICON_URL)

        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"Panneau envoyé dans {channel.mention}.", ephemeral=True)


async def start_configuration(bot: commands.Bot, channel: discord.TextChannel, author: discord.Member):
    def check(m: discord.Message):
        return m.author == author and m.channel == channel

    data = {"title": None, "description": None, "footer": None, "transcript_channel": None}
    categories: list[dict] = []

    # Étapes textuelles
    text_steps = [
        ("title", "Entrez le **titre** du panneau"),
        ("description", "Entrez la **description**"),
        ("footer", "Entrez le **footer** (ou tapez `aucun`)")
    ]
    embed_msg = await channel.send(embed=build_embed(data, categories, text_steps[0][1]))

    for key, question in text_steps:
        await embed_msg.edit(embed=build_embed(data, categories, question))
        try:
            msg = await bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            return await embed_msg.edit(
                embed=discord.Embed(description="⏰ Temps écoulé, relancez `/config_tickets`.", color=0xFF0000)
            )
        content = msg.content.strip()
        data[key] = None if (key == "footer" and content.lower() == "aucun") else content
        await msg.delete()

    # Sélection du salon transcripts
    await embed_msg.edit(embed=build_embed(data, categories, "Sélectionnez le salon de transcripts"))
    sel_view = View(timeout=None)
    sel = ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="Salon transcripts")
    result = {}

    async def sel_cb(i: discord.Interaction):
        result["transcript"] = sel.values[0].id
        await i.response.defer()
    sel.callback = sel_cb
    sel_view.add_item(sel)
    await channel.send(view=sel_view)
    while "transcript" not in result:
        await asyncio.sleep(0.5)
    data["transcript_channel"] = result["transcript"]

    # Ajout de catégories
    while len(categories) < MAX_CATEGORIES:
        await embed_msg.edit(embed=build_embed(data, categories, "Entrez nom de catégorie ou tapez `fin`"))
        try:
            msg = await bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            return await embed_msg.edit(
                embed=discord.Embed(description="⏰ Temps écoulé, relancez `/config_tickets`.", color=0xFF0000)
            )
        name = msg.content.strip()
        await msg.delete()
        if name.lower() == "fin":
            break

        # Description catégorie
        await embed_msg.edit(embed=build_embed(data, categories, f"Description pour `{name}`"))
        desc_msg = await bot.wait_for("message", check=check, timeout=120)
        desc = desc_msg.content.strip()
        await desc_msg.delete()

        # Sélection des rôles
        await embed_msg.edit(embed=build_embed(data, categories, f"Sélectionnez les rôles pour `{name}`"))
        sel_roles = RoleSelect(min_values=1, max_values=5, placeholder="Rôles staff")
        rr, view_r = {}, View(timeout=None)

        async def rcb(i: discord.Interaction):
            rr["roles"] = [r.id for r in sel_roles.values]
            await i.response.defer()
        sel_roles.callback = rcb
        view_r.add_item(sel_roles)
        await channel.send(view=view_r)
        while "roles" not in rr:
            await asyncio.sleep(0.5)

        # Sélection catégorie parent
        await embed_msg.edit(embed=build_embed(data, categories, f"Sélectionnez la catégorie parent pour `{name}`"))
        sel_cat = ChannelSelect(channel_types=[discord.ChannelType.category], placeholder="Catégorie parent")
        rc, view_c = {}, View(timeout=None)

        async def ccb(i: discord.Interaction):
            rc["cat"] = sel_cat.values[0].id
            await i.response.defer()
        sel_cat.callback = ccb
        view_c.add_item(sel_cat)
        await channel.send(view=view_c)
        while "cat" not in rc:
            await asyncio.sleep(0.5)

        categories.append({
            "name": name,
            "description": desc,
            "roles": rr["roles"],
            "discord_category": rc["cat"]
        })
        await embed_msg.edit(embed=build_embed(data, categories, f"Catégorie `{name}` ajoutée"))

    if not categories:
        return await embed_msg.edit(
            embed=discord.Embed(description="❌ Au moins une catégorie requise. Appuyez de nouveau sur Commencer.", color=0xFF0000)
        )

    # Enregistrement en base
    await ticket_collection.update_one(
        {"guild_id": str(channel.guild.id)},
        {"$set": {
            "guild_id": str(channel.guild.id),
            "panel_embed": {
                "title": data["title"],
                "description": data["description"],
                "footer": data.get("footer")
            },
            "transcript_channel": str(data["transcript_channel"]),
            "categories": {
                c["name"]: {
                    "description": c["description"],
                    "roles": [str(r) for r in c["roles"]],
                    "discord_category": str(c["discord_category"])
                } for c in categories
            },
            "ticket_count": 0
        }},
        upsert=True
    )

    # Confirmation finale
    final = discord.Embed(
        title="Et voilà c'est configuré !",
        description="Faites la commande **/panel_tickets** pour afficher votre panneau !",
        color=EMBED_COLOR
    )
    if data.get("footer"):
        final.set_footer(text=data["footer"], icon_url=EMBED_FOOTER_ICON_URL)
    await embed_msg.edit(embed=final)


class ConfirmDeleteView(View):
    """View de confirmation pour suppression de ticket et envoi du transcript."""
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg

    @discord.ui.button(label="Oui, supprimer", style=discord.ButtonStyle.danger)
    async def confirm_yes(self, interaction: discord.Interaction, button: Button):
        chan = interaction.channel
        member_id = chan.topic.split(":")[-1]
        embed = discord.Embed(
            title="✅ Voici le transcript !",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Membre concerné", value=f"<@{member_id}>", inline=False)
        embed.add_field(name="Claimé par", value=interaction.user.mention, inline=False)

        if self.cfg.get("transcript_channel"):
            tgt = interaction.guild.get_channel(int(self.cfg["transcript_channel"]))
            if tgt:
                try:
                    import chat_exporter
                    html = await chat_exporter.export(
                        chan, limit=None, tz_info="UTC", military_time=False
                    )
                    buf = io.BytesIO(html.encode()); buf.seek(0)
                    file = discord.File(buf, filename="transcript.html")
                    await tgt.send(embed=embed, file=file)
                except Exception as e:
                    error_embed = discord.Embed(
                        title="⚠️ Erreur lors de l’envoi du transcript",
                        description=str(e),
                        color=0xFF0000,
                        timestamp=discord.utils.utcnow()
                    )
                    await tgt.send(embed=error_embed)

        await chan.delete()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def confirm_no(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ Suppression annulée.", view=None)


class TicketControlsView(View):
    """Contrôles (claim, close, reopen, delete) sur chaque ticket créé."""
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg

    @discord.ui.button(label="📥 Claim", style=discord.ButtonStyle.secondary)
    async def claim(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.set_permissions(
            interaction.user,
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )
        await interaction.response.send_message(f"{interaction.user.mention} a claim.", ephemeral=True)

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: Button):
        ch = interaction.channel
        if ch.name.startswith("ferme-"):
            return await interaction.response.send_message("⚠️ Déjà fermé.", ephemeral=True)

        await ch.edit(name=f"ferme-{ch.name}")
        # désactiver @everyone
        await ch.set_permissions(
            interaction.guild.default_role,
            view_channel=False,
            send_messages=False
        )
        # retirer accès opener
        try:
            opener_id = int(ch.topic.split(":")[-1])
            opener = interaction.guild.get_member(opener_id)
            if opener:
                await ch.set_permissions(
                    opener,
                    view_channel=False,
                    send_messages=False,
                    read_message_history=False
                )
        except Exception:
            pass

        button.disabled = True
        for c in self.children:
            if c.label == "♻️ Reopen":
                c.disabled = False

        await interaction.response.edit_message(content="Ticket fermé.", view=self)
        await ch.send(f"Fermé par {interaction.user.mention}")

    @discord.ui.button(label="♻️ Reopen", style=discord.ButtonStyle.success, disabled=True)
    async def reopen(self, interaction: discord.Interaction, button: Button):
        ch = interaction.channel
        if not ch.name.startswith("ferme-"):
            return await interaction.response.send_message("⚠️ Déjà ouvert.", ephemeral=True)
        await ch.edit(name=ch.name.removeprefix("ferme-"))

        try:
            opener_id = int(ch.topic.split(":")[-1])
            opener = interaction.guild.get_member(opener_id)
            if opener:
                await ch.set_permissions(
                    opener,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
        except Exception:
            pass

        button.disabled = True
        for c in self.children:
            if c.label == "🔒 Close":
                c.disabled = False

        await interaction.response.edit_message(content="Ticket rouvert.", view=self)
        await ch.send(f"Rouvert par {interaction.user.mention}")

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.secondary)
    async def delete(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🔔 Confirm?", view=ConfirmDeleteView(self.cfg), ephemeral=True)


class TicketPanelView(View):
    """Vue du panneau de sélection de catégorie pour création de ticket."""
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg
        options = [discord.SelectOption(label=k) for k in cfg["categories"]]
        sel = discord.ui.Select(placeholder="Choisissez…", options=options)
        sel.callback = self.on_select
        self.add_item(sel)

    async def on_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cat = self.cfg["categories"][interaction.data["values"][0]]
        if not cat.get("discord_category"):
            return await interaction.followup.send("⚠️ Pas de salon parent.", ephemeral=True)

        gid = str(interaction.guild_id)
        topic = f"ticket:{gid}:{interaction.user.id}"
        if discord.utils.get(interaction.guild.text_channels, topic=topic):
            return await interaction.followup.send(MESSAGES["TICKET_EXISTS"], ephemeral=True)

        doc = await ticket_collection.find_one_and_update(
            {"guild_id": gid}, {"$inc": {"ticket_count": 1}}, return_document=ReturnDocument.AFTER
        )
        name = f"{doc['ticket_count']}-{interaction.user.name}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False),
            interaction.user:           discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for rid in cat["roles"]:
            role = interaction.guild.get_role(int(rid))
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        ch = await interaction.guild.create_text_channel(
            name=name,
            category=interaction.guild.get_channel(int(cat["discord_category"])),
            topic=topic,
            overwrites=overwrites
        )

        mentions = [r.mention for r in overwrites if isinstance(r, discord.Role)]
        emb = discord.Embed(
            title=self.cfg["panel_embed"]["title"],
            description=cat["description"],
            color=EMBED_COLOR
        )
        await ch.send(content=" ".join(mentions) or None, embed=emb, view=TicketControlsView(self.cfg))
        await interaction.followup.send(f"Ticket créé : {ch.mention}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
