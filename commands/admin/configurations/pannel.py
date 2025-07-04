import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput, ChannelSelect, RoleSelect

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import db

# Essayer d'importer la lib de transcripts
try:
    from py_discord_html_transcripts import generate_transcript
    TRANSCRIPTS_AVAILABLE = True
except ImportError:
    TRANSCRIPTS_AVAILABLE = False

ticket_collection = db["ticket"]


class EmbedModal(Modal, title="Configuration Embed"):
    title_input = TextInput(label="Titre", placeholder="Titre du panneau", max_length=100)
    desc_input = TextInput(label="Description", style=discord.TextStyle.paragraph)
    img_input = TextInput(label="Image URL", required=False)
    foot_input = TextInput(label="Footer", required=False)

    def __init__(self, parent_view: 'ConfigView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.embed_data['title'] = self.title_input.value.strip()
        self.parent_view.embed_data['description'] = self.desc_input.value.strip()
        self.parent_view.embed_data['image'] = self.img_input.value.strip()
        self.parent_view.embed_data['footer'] = self.foot_input.value.strip()
        await interaction.response.edit_message(
            embed=self.parent_view.build_panel_embed(),
            view=self.parent_view
        )


class CategoryModal(Modal, title="Nouvelle Catégorie"):
    name = TextInput(label="Nom de la catégorie", placeholder="Ex: Support", max_length=50)
    description = TextInput(
        label="Description du ticket",
        placeholder="Décrivez ce qu'on attend…",
        style=discord.TextStyle.paragraph
    )

    def __init__(self, parent_view: 'ConfigView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        cat_name = self.name.value.strip()
        desc = self.description.value.strip()
        self.parent_view.temp_categories[cat_name] = {
            'description': desc,
            'roles': [],
            'discord_category': None
        }
        await interaction.response.edit_message(
            embed=self.parent_view.build_panel_embed(),
            view=self.parent_view
        )


class ConfigView(View):
    def __init__(self, author: discord.Member, guild_id: int):
        super().__init__(timeout=300)
        self.author = author
        self.guild_id = guild_id
        self.embed_data: dict[str, str] = {}
        self.temp_categories: dict[str, dict] = {}
        self.log_channel: int | None = None
        self.transcript_channel: int | None = None
        self.message: discord.Message | None = None

    def build_panel_embed(self) -> discord.Embed:
        lines = [
            f"**Titre:** `{self.embed_data.get('title','❌')}`",
            f"**Description:** `{self.embed_data.get('description','❌')}`",
            f"**Image:** `{self.embed_data.get('image','❌')}`",
            f"**Footer:** `{self.embed_data.get('footer','❌')}`",
            f"**Types de tickets:** {len(self.temp_categories)}/5"
        ]
        for name, data in self.temp_categories.items():
            dc = f"<#{data['discord_category']}>" if data['discord_category'] else '❌'
            roles = len(data['roles'])
            lines.append(f"- **{name}** (roles: {roles}, Catégorie Discord: {dc})")

        lines += [
            f"**Salon Logs:** {f'<#{self.log_channel}>' if self.log_channel else '❌'}",
            f"**Salon Transcripts:** {f'<#{self.transcript_channel}>' if self.transcript_channel else '❌'}"
        ]

        embed = discord.Embed(
            title=self.embed_data.get('title','🏷️ Config Ticket'),
            description="\n".join(lines),
            color=EMBED_COLOR
        )
        # Affiche l'image si fournie
        if img := self.embed_data.get('image'):
            embed.set_image(url=img)
        # Footer
        footer = self.embed_data.get('footer')
        embed.set_footer(
            text=footer if footer else EMBED_FOOTER_TEXT,
            icon_url=EMBED_FOOTER_ICON_URL
        )
        return embed

    async def show_panel(self, interaction: discord.Interaction):
        embed = self.build_panel_embed()
        if not self.message:
            await interaction.response.send_message(embed=embed, view=self)
            self.message = await interaction.original_response()
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Définir Embed", style=discord.ButtonStyle.primary, custom_id="set_embed")
    async def _set_embed(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        await interaction.response.send_modal(EmbedModal(self))

    @discord.ui.button(label="Ajouter Catégorie", style=discord.ButtonStyle.primary, custom_id="add_category")
    async def _add_category(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        await interaction.response.send_modal(CategoryModal(self))

    @discord.ui.button(label="Associer Catégorie", style=discord.ButtonStyle.secondary, custom_id="set_cat_channel")
    async def _set_cat_channel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        if not self.temp_categories:
            return await interaction.response.send_message("Aucune catégorie configurée.", ephemeral=True)

        options = [discord.SelectOption(label=n) for n in self.temp_categories]
        select = Select(placeholder="Choisissez un type…", options=options, min_values=1, max_values=1)

        async def cb(resp: discord.Interaction):
            chosen = select.values[0]
            chan_sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.category])

            async def cc(cresp: discord.Interaction):
                self.temp_categories[chosen]['discord_category'] = chan_sel.values[0].id
                await cresp.response.edit_message(embed=self.build_panel_embed(), view=self)

            chan_sel.callback = cc
            view2 = View()
            view2.add_item(chan_sel)
            await resp.response.edit_message(
                content=f"Sélectionnez la catégorie Discord pour **{chosen}** :",
                view=view2
            )

        select.callback = cb
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Choisissez le type de ticket :", view=view, ephemeral=True)

    @discord.ui.button(label="Assigner Rôles", style=discord.ButtonStyle.secondary, custom_id="set_roles")
    async def _set_roles(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)

        options = [discord.SelectOption(label=n) for n in self.temp_categories]
        select = Select(placeholder="Choisissez un type…", options=options, min_values=1, max_values=1)

        async def cb(resp: discord.Interaction):
            chosen = select.values[0]
            role_sel = RoleSelect(min_values=1, max_values=5)

            async def rc(rresp: discord.Interaction):
                self.temp_categories[chosen]['roles'] = [r.id for r in role_sel.values]
                await rresp.response.edit_message(embed=self.build_panel_embed(), view=self)

            role_sel.callback = rc
            view2 = View()
            view2.add_item(role_sel)
            await resp.response.edit_message(
                content=f"Sélectionnez les rôles staff pour **{chosen}** :",
                view=view2
            )

        select.callback = cb
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Choisissez le type de ticket :", view=view, ephemeral=True)

    @discord.ui.button(label="Salon Logs", style=discord.ButtonStyle.primary, custom_id="set_logs")
    async def _set_logs(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)

        sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.text])

        async def cb(resp: discord.Interaction):
            self.log_channel = sel.values[0].id
            await resp.response.edit_message(embed=self.build_panel_embed(), view=self)

        sel.callback = cb
        view = View()
        view.add_item(sel)
        await interaction.response.send_message("Sélectionnez le salon de logs :", view=view, ephemeral=True)

    @discord.ui.button(label="Salon Transcripts", style=discord.ButtonStyle.primary, custom_id="set_transcripts")
    async def _set_transcripts(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)

        sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.text])

        async def cb(resp: discord.Interaction):
            self.transcript_channel = sel.values[0].id
            await resp.response.edit_message(embed=self.build_panel_embed(), view=self)

        sel.callback = cb
        view = View()
        view.add_item(sel)
        await interaction.response.send_message("Sélectionnez le salon de transcripts :", view=view, ephemeral=True)

    @discord.ui.button(label="Valider Config", style=discord.ButtonStyle.success, custom_id="finish")
    async def _finish(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)

        data = {
            'guild_id': str(self.guild_id),
            'panel_embed': self.embed_data,
            'categories': self.temp_categories,
            'log_channel': str(self.log_channel),
            'transcript_channel': str(self.transcript_channel),
            'ticket_count': 0
        }
        await ticket_collection.update_one(
            {'guild_id': str(self.guild_id)},
            {'$set': data},
            upsert=True
        )
        await interaction.response.edit_message(content="Configuration enregistrée !", embed=None, view=None)


class ConfirmDeleteView(View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=300)
        self.cfg = cfg

    @discord.ui.button(label="Oui, supprimer", style=discord.ButtonStyle.danger, custom_id="confirm_yes")
    async def confirm_yes(self, interaction: discord.Interaction, button: Button):
        # Répondre avant suppression pour éviter 404
        await interaction.response.send_message("Ticket supprimé ✅", ephemeral=True)

        # Génération automatique de transcript
        if self.cfg.get('transcript_channel'):
            if TRANSCRIPTS_AVAILABLE:
                transcript = await generate_transcript(interaction.channel)
                await interaction.guild.get_channel(int(self.cfg['transcript_channel'])).send(file=transcript)
            else:
                await interaction.guild.get_channel(int(self.cfg['transcript_channel'])).send(
                    "⚠️ Impossible de générer le transcript : librairie manquante.\n"
                    "Installez-la avec : `pip install py-discord-html-transcripts`"
                )

        # Log
        log = interaction.guild.get_channel(int(self.cfg['log_channel']))
        if log:
            await log.send(f"Ticket supprimé : {interaction.channel.name}")

        # Suppression du salon
        await interaction.channel.delete()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="confirm_no")
    async def confirm_no(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Suppression annulée.", ephemeral=True)


class TicketControlsView(View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg

    @discord.ui.button(label="📥 Claim", style=discord.ButtonStyle.secondary, custom_id="claim")
    async def claim(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await interaction.response.send_message(f"{interaction.user.mention} a claim.", ephemeral=True)

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="close")
    async def close(self, interaction: discord.Interaction, button: Button):
        ch = interaction.channel
        await ch.edit(name=f"ferme-{ch.name}")
        await ch.set_permissions(interaction.guild.default_role, view_channel=False)
        button.disabled = True
        for c in self.children:
            if isinstance(c, Button) and c.custom_id == "reopen":
                c.disabled = False
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Ticket fermé.", ephemeral=True)
        log = interaction.guild.get_channel(int(self.cfg['log_channel']))
        if log:
            await log.send(f"Ticket fermé : {ch.name}")

    @discord.ui.button(label="♻️ Reopen", style=discord.ButtonStyle.success,
                       custom_id="reopen", disabled=True)
    async def reopen(self, interaction: discord.Interaction, button: Button):
        ch = interaction.channel
        new_name = ch.name.removeprefix("ferme-")
        await ch.edit(name=new_name)
        button.disabled = True
        for c in self.children:
            if isinstance(c, Button) and c.custom_id == "close":
                c.disabled = False
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Ticket rouvert.", ephemeral=True)
        log = interaction.guild.get_channel(int(self.cfg['log_channel']))
        if log:
            await log.send(f"Ticket rouvert : {new_name}")

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.secondary, custom_id="delete")
    async def delete(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "🔔 **Confirmer la suppression ?**",
            view=ConfirmDeleteView(self.cfg),
            ephemeral=True
        )


class TicketPanelView(View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg
        options = [discord.SelectOption(label=k) for k in cfg['categories']]
        self.select = Select(
            placeholder="Choisissez une catégorie…",
            options=options,
            custom_id="ticket_select"
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sel = interaction.data['values'][0]
        cat = self.cfg['categories'][sel]
        # Vérifier configuration catégorie Discord
        if not cat.get('discord_category'):
            return await interaction.followup.send(
                "⚠️ Pas de catégorie Discord configurée.",
                ephemeral=True
            )
        # Vérifier ticket existant
        gid = str(interaction.guild_id)
        topic = f"ticket:{gid}:{interaction.user.id}"
        if discord.utils.get(interaction.guild.text_channels, topic=topic):
            msg = MESSAGES.get('TICKET_EXISTS', "Vous avez déjà un ticket ouvert.")
            return await interaction.followup.send(msg, ephemeral=True)
        # Créer le salon
        doc = await ticket_collection.find_one_and_update(
            {'guild_id': gid},
            {'$inc': {'ticket_count': 1}},
            return_document=True
        )
        number = doc['ticket_count']
        name = f"{number}-{interaction.user.name}"
        channel = await interaction.guild.create_text_channel(
            name=name,
            category=interaction.guild.get_channel(int(cat['discord_category'])),
            topic=topic
        )
        # Permissions
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        for rid in cat['roles']:
            role = interaction.guild.get_role(int(rid))
            if role:
                await channel.set_permissions(role, view_channel=True, send_messages=True)
        # Mention roles hors embed
        mentions = " ".join(
            r.mention for r in (interaction.guild.get_role(int(rid)) for rid in cat['roles']) if r
        ) or None
        # Embed du ticket
        embed = discord.Embed(
            title=self.cfg['panel_embed']['title'],
            description=cat['description'],
            color=EMBED_COLOR
        )
        if img := self.cfg['panel_embed'].get('image'):
            embed.set_image(url=img)
        # Envoi
        await channel.send(content=mentions, embed=embed, view=TicketControlsView(self.cfg))
        await interaction.followup.send(f"Ticket créé : {channel.mention}", ephemeral=True)


class CloseConfirmView(View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.channel = channel

    @discord.ui.button(label="Oui, fermer", style=discord.ButtonStyle.danger, custom_id="confirm_close")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        ch = self.channel
        await ch.edit(name=f"ferme-{ch.name}")
        await ch.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message("Ticket fermé suite au départ.", ephemeral=True)


class Tickets(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Commandes de tickets")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @ticket.command(name="config", description="Configure le système de tickets")
    @app_commands.default_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        view = ConfigView(interaction.user, interaction.guild_id)
        await view.show_panel(interaction)

    @ticket.command(name="panel", description="Affiche le panneau de tickets")
    @app_commands.describe(channel="Salon où envoyer le panneau")
    async def panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        cfg = await ticket_collection.find_one({'guild_id': str(interaction.guild_id)})
        if not cfg:
            return await interaction.response.send_message("⚠️ Panneau non configuré.", ephemeral=True)

        embed = discord.Embed(
            title=cfg['panel_embed']['title'],
            description=cfg['panel_embed']['description'],
            color=EMBED_COLOR
        )
        if img := cfg['panel_embed'].get('image'):
            embed.set_image(url=img)

        dest = channel or interaction.channel
        await dest.send(embed=embed, view=TicketPanelView(cfg))
        await interaction.response.send_message(f"Panneau envoyé dans {dest.mention}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
