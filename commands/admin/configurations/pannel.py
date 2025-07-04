import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, ChannelSelect, RoleSelect
import asyncio
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

    # Question en cours
    if current_question:
        embed.add_field(name="❓ Question", value=current_question, inline=False)

    # Champs configurés
    embed.add_field(name="🎫 Titre", value=data.get("title", "❌ Non défini"), inline=False)
    embed.add_field(name="📝 Description", value=data.get("description", "❌ Non défini"), inline=False)
    embed.add_field(name="🔖 Footer", value=data.get("footer", "❌ Non défini"), inline=False)

    # Salon transcripts
    transcripts = data.get("transcript_channel")
    embed.add_field(
        name="📂 Salon transcripts",
        value=f"<#{transcripts}>" if transcripts else "❌ Non défini",
        inline=False
    )

    # Catégories
    if categories:
        lines = []
        for c in categories:
            roles_mention = " ".join(f"<@&{r}>" for r in c["roles"])
            cat_mention = f"<#{c['discord_category']}>"
            lines.append(f"**{c['name']}** — Rôles: {roles_mention} — Parent: {cat_mention}")
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

    embed.set_footer(text="Besoin d'aide ? Cliquez sur 📖", icon_url=EMBED_FOOTER_ICON_URL)
    return embed


class HelpView(View):
    """Vue pour le bouton d'aide."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📖 Aide", style=discord.ButtonStyle.secondary, custom_id="help_button")
    async def help(self, interaction: discord.Interaction, button: Button):
        text = (
            "**Guide Configuration Tickets**\n"
            f"• Répondez dans l'embed mis à jour.\n"
            f"• Max {MAX_CATEGORIES} catégories.\n"
            "• Saisissez chaque nom de catégorie l'un après l'autre.\n"
            "• Tapez `fin` pour terminer l'ajout.\n"
            "• Les salons et rôles seront mentionnés dynamiquement.\n"
        )
        await interaction.response.send_message(text, ephemeral=True)


class StartConfigView(View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.channel = channel
        self.add_item(HelpView().children[0])  # bouton d'aide

    @discord.ui.button(label="🚀 Commencer la config", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: Button):
        if interaction.user != interaction.guild.owner and not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await interaction.response.defer()
        await start_configuration(interaction.client, self.channel, interaction.user)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="config_tickets", description="Démarre la configuration du panneau de tickets")
    async def config_tickets(self, interaction: discord.Interaction):
        if await ticket_collection.find_one({"guild_id": str(interaction.guild_id)}):
            return await interaction.response.send_message(
                "⚠️ Un panneau de tickets existe déjà pour ce serveur.", ephemeral=True
            )
        view = StartConfigView(interaction.channel)
        embed = build_embed({}, [], "Cliquez sur 🚀 pour démarrer.")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="panel_tickets", description="Envoie le panneau de tickets dans le salon spécifié")
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
        ("footer", "Entrez le **footer** (ou tapez 'aucun')")
    ]
    embed_msg = await channel.send(embed=build_embed(data, categories, text_steps[0][1]))

    for key, question in text_steps:
        await embed_msg.edit(embed=build_embed(data, categories, question))
        try:
            msg = await bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            return await embed_msg.edit(
                embed=discord.Embed(description="⏰ Temps écoulé, relancez /config_tickets.", color=0xFF0000)
            )
        content = msg.content.strip()
        data[key] = None if (key == "footer" and content.lower() == "aucun") else content
        await msg.delete()

    # Salon transcripts
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
        await embed_msg.edit(embed=build_embed(data, categories, "Entrez nom de catégorie ou tapez 'fin'"))
        try:
            msg = await bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            return await embed_msg.edit(
                embed=discord.Embed(description="⏰ Temps écoulé, relancez /config_tickets.", color=0xFF0000)
            )
        name = msg.content.strip()
        await msg.delete()
        if name.lower() == "fin":
            break

        # Description catégorie
        await embed_msg.edit(embed=build_embed(data, categories, f"Description pour '{name}'"))
        desc_msg = await bot.wait_for("message", check=check, timeout=120)
        desc = desc_msg.content.strip()
        await desc_msg.delete()

        # Sélection rôles
        await embed_msg.edit(embed=build_embed(data, categories, f"Sélectionnez les rôles pour '{name}'"))
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
        await embed_msg.edit(embed=build_embed(data, categories, f"Sélectionnez la catégorie parent pour '{name}'"))
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

        await embed_msg.edit(embed=build_embed(data, categories, f"Catégorie '{name}' ajoutée"))

    if not categories:
        return await embed_msg.edit(
            embed=discord.Embed(description="❌ Au moins une catégorie requise.", color=0xFF0000)
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
        title=data["title"],
        description=data["description"],
        color=EMBED_COLOR
    )
    if data.get("footer"):
        final.set_footer(text=data["footer"], icon_url=EMBED_FOOTER_ICON_URL)
    await embed_msg.edit(embed=final)


class TicketControlsView(View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg

    @discord.ui.button(label="📥 Claim", style=discord.ButtonStyle.secondary)
    async def claim(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await interaction.response.send_message(f"{interaction.user.mention} a claim.", ephemeral=True)

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: Button):
        ch = interaction.channel
        if ch.name.startswith("ferme-"):
            return await interaction.response.send_message("⚠️ Déjà fermé.", ephemeral=True)
        await ch.edit(name=f"ferme-{ch.name}")
        await ch.set_permissions(interaction.guild.default_role, view_channel=False)
        button.disabled = True
        for c in self.children:
            if getattr(c, "label", None) == "♻️ Reopen":
                c.disabled = False
        await interaction.response.edit_message(content="Ticket fermé.", view=self)
        await ch.send(f"Fermé par {interaction.user.mention}")

    @discord.ui.button(label="♻️ Reopen", style=discord.ButtonStyle.success, disabled=True)
    async def reopen(self, interaction: discord.Interaction, button: Button):
        ch = interaction.channel
        if not ch.name.startswith("ferme-"):
            return await interaction.response.send_message("⚠️ Déjà ouvert.", ephemeral=True)
        new = ch.name.removeprefix("ferme-")
        await ch.edit(name=new)
        button.disabled = True
        for c in self.children:
            if getattr(c, "label", None) == "🔒 Close":
                c.disabled = False
        await interaction.response.edit_message(content="Ticket rouvert.", view=self)
        await ch.send(f"Rouvert par {interaction.user.mention}")

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.secondary)
    async def delete(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🔔 Confirm?", view=ConfirmDeleteView(self.cfg), ephemeral=True)


class ConfirmDeleteView(View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg

    @discord.ui.button(label="Oui, supprimer", style=discord.ButtonStyle.danger)
    async def confirm_yes(self, interaction: discord.Interaction, button: Button):
        chan = interaction.channel
        await interaction.response.send_message("Supprimé ✅", ephemeral=True)
        log = discord.Embed(color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        if self.cfg.get("transcript_channel"):
            tgt = interaction.guild.get_channel(int(self.cfg["transcript_channel"]))
            if tgt:
                try:
                    import chat_exporter
                    html = await chat_exporter.export(chan, limit=None, tz_info="UTC", military_time=False)
                    buf = io.BytesIO(html.encode()); buf.seek(0)
                    file = discord.File(buf, filename="transcript.html")
                    await tgt.send(file=file)
                    log.description = "✅ Transcript envoyé."
                except Exception as e:
                    log.description = f"⚠️ Erreur: {e}"
                await tgt.send(embed=log)
        await chan.send(f"Supprimé par {interaction.user.mention}")
        await chan.delete()


class TicketPanelView(View):
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
        num = doc["ticket_count"]
        name = f"{num}-{interaction.user.name}"
        ch = await interaction.guild.create_text_channel(
            name=name,
            category=interaction.guild.get_channel(int(cat["discord_category"])),
            topic=topic
        )
        await ch.set_permissions(interaction.guild.default_role, view_channel=False)
        await ch.set_permissions(interaction.user, view_channel=True, send_messages=True)

        mentions = []
        for rid in cat["roles"]:
            role = interaction.guild.get_role(int(rid))
            if role:
                await ch.set_permissions(role, view_channel=True, send_messages=True)
                mentions.append(role.mention)

        emb = discord.Embed(
            title=self.cfg["panel_embed"]["title"],
            description=cat["description"],
            color=EMBED_COLOR
        )
        await ch.send(content=" ".join(mentions) or None, embed=emb, view=TicketControlsView(self.cfg))
        await interaction.followup.send(f"Ticket créé : {ch.mention}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
