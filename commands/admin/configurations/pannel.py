import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput, ChannelSelect

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import db

# Mongo collection for tickets config
ticket_collection = db["ticket"]

# Modal for embed configuration
class EmbedModal(Modal, title="Configuration Embed"):
    title_input = TextInput(label="Titre", placeholder="Titre du panneau", max_length=100)
    desc_input = TextInput(label="Description", style=discord.TextStyle.paragraph)
    img_input = TextInput(label="Image URL", required=False)
    foot_input = TextInput(label="Footer", required=False)

    def __init__(self, parent_view: 'ConfigView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.parent_view.embed_data['title'] = self.title_input.value.strip()
        self.parent_view.embed_data['description'] = self.desc_input.value.strip()
        self.parent_view.embed_data['image'] = self.img_input.value.strip()
        self.parent_view.embed_data['footer'] = self.foot_input.value.strip()
        embed = self.parent_view.build_panel_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

# Modal for adding a new ticket category
class CategoryModal(Modal, title="Nouvelle Catégorie"):
    name = TextInput(label="Nom de la catégorie", placeholder="Ex: Support", max_length=50)
    description = TextInput(label="Description du ticket", placeholder="Décrivez ce qu'on attend...", style=discord.TextStyle.paragraph)

    def __init__(self, parent_view: 'ConfigView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cat_name = self.name.value.strip()
        desc = self.description.value.strip()
        # initialize with no discord category selected yet
        self.parent_view.temp_categories[cat_name] = {
            'description': desc,
            'roles': [r.id for r in self.parent_view.temp_roles],
            'discord_category': None
        }
        embed = self.parent_view.build_panel_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class ConfigView(View):
    def __init__(self, author: discord.Member, guild_id: int):
        super().__init__(timeout=300)
        self.author = author
        self.guild_id = guild_id
        self.embed_data: dict[str, str] = {}
        # Each ticket type: {description, roles, discord_category}
        self.temp_categories: dict[str, dict] = {}
        self.temp_roles: list[discord.Role] = []
        self.log_channel: int | None = None
        self.transcript_channel: int | None = None
        self.message: discord.Message | None = None

    def build_panel_embed(self) -> discord.Embed:
        lines: list[str] = []
        lines.append(f"**Titre:** `{self.embed_data.get('title', '❌')}`")
        lines.append(f"**Description:** `{self.embed_data.get('description', '❌')}`")
        lines.append(f"**Image:** `{self.embed_data.get('image', '❌')}`")
        lines.append(f"**Footer:** {self.embed_data.get('footer', '❌')}")
        lines.append(f"**Types de tickets:** {len(self.temp_categories)}/5")
        # For each category, show roles count and assigned Discord category
        for name, data in self.temp_categories.items():
            dc = f"<#{data['discord_category']}>" if data['discord_category'] else '❌'
            lines.append(f"- **{name}** (roles: {len(data['roles'])}, Catégorie Discord: {dc})")
        lines.append(f"**Salon Logs:** {f'<#{self.log_channel}>' if self.log_channel else '❌'}")
        lines.append(f"**Salon Transcripts:** {f'<#{self.transcript_channel}>' if self.transcript_channel else '❌'}")

        embed = discord.Embed(
            title=self.embed_data.get('title', '🏷️ Configuration Ticket'),
            description="\n".join(lines),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        return embed

    async def show_panel(self, interaction: discord.Interaction) -> None:
        embed = self.build_panel_embed()
        if not self.message:
            await interaction.response.send_message(embed=embed, view=self)
            self.message = await interaction.original_response()
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Définir Embed", style=discord.ButtonStyle.primary, custom_id="set_embed")
    async def _set_embed(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        await interaction.response.send_modal(EmbedModal(self))

    @discord.ui.button(label="Ajouter Catégorie", style=discord.ButtonStyle.primary, custom_id="add_category")
    async def _add_category(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        await interaction.response.send_modal(CategoryModal(self))

    @discord.ui.button(label="Attribuer Channel Cat", style=discord.ButtonStyle.secondary, custom_id="set_cat_channel")
    async def _set_cat_channel(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        if not self.temp_categories:
            return await interaction.response.send_message("Aucune catégorie configurée.", ephemeral=True)
        options = [discord.SelectOption(label=n) for n in self.temp_categories.keys()]
        select = Select(placeholder="Choisissez un type...", options=options, min_values=1, max_values=1)
        async def cb(resp: discord.Interaction):
            chosen = select.values[0]
            chan_sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.category])
            async def cc(cresp: discord.Interaction):
                self.temp_categories[chosen]['discord_category'] = chan_sel.values[0].id  # type: ignore
                embed = self.build_panel_embed()
                await cresp.response.edit_message(embed=embed, view=self)
            chan_sel.callback = cc
            view2 = View()
            view2.add_item(chan_sel)
            await resp.response.edit_message(content=f"Sélectionnez la catégorie Discord pour **{chosen}**:", view=view2)
        select.callback = cb
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Choisissez le type de ticket:", view=view, ephemeral=True)

    @discord.ui.button(label="Salon Logs", style=discord.ButtonStyle.primary, custom_id="set_logs")
    async def _set_logs(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.text])
        async def cb(resp: discord.Interaction):
            self.log_channel = sel.values[0].id  # type: ignore
            embed = self.build_panel_embed()
            await resp.response.edit_message(embed=embed, view=self)
        sel.callback = cb
        view = View()
        view.add_item(sel)
        await interaction.response.send_message("Sélectionnez le salon de logs :", view=view, ephemeral=True)

    @discord.ui.button(label="Salon Transcripts", style=discord.ButtonStyle.primary, custom_id="set_transcripts")
    async def _set_transcripts(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.text])
        async def cb(resp: discord.Interaction):
            self.transcript_channel = sel.values[0].id  # type: ignore
            embed = self.build_panel_embed()
            await resp.response.edit_message(embed=embed, view=self)
        sel.callback = cb
        view = View()
        view.add_item(sel)
        await interaction.response.send_message("Sélectionnez le salon de transcripts :", view=view, ephemeral=True)

    @discord.ui.button(label="Valider Configuration", style=discord.ButtonStyle.success, custom_id="finish")
    async def _finish(self, interaction: discord.Interaction, button: Button) -> None:
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
        await ticket_collection.update_one({'guild_id': str(self.guild_id)}, {'$set': data}, upsert=True)
        await interaction.response.edit_message(content="Configuration enregistrée !", embed=None, view=None)

class TicketPanelView(View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg
        options = [discord.SelectOption(label=k, description=v['description']) for k, v in cfg['categories'].items()]
        self.select = Select(placeholder="Choisissez une catégorie...", options=options, custom_id="ticket_select")
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction) -> None:
        sel = interaction.data['values'][0]
        cat_data = self.cfg['categories'][sel]
        # Determine channel category for this ticket
        cat_id = cat_data.get('discord_category')
        if not cat_id:
            return await interaction.response.send_message(
                embed=discord.Embed(description="Erreur: pas de catégorie Discord configurée pour ce ticket.", color=EMBED_COLOR),
                ephemeral=True
            )
        user_id = interaction.user.id
        guild_id = str(interaction.guild_id)
        existing = discord.utils.get(
            interaction.guild.text_channels,
            topic=f"ticket:{guild_id}:{user_id}"
        )
        if existing:
            return await interaction.response.send_message(
                embed=discord.Embed(description=MESSAGES['TICKET_EXISTS'], color=EMBED_COLOR), ephemeral=True
            )
        result = await ticket_collection.find_one_and_update(
            {'guild_id': guild_id}, {'$inc': {'ticket_count': 1}}, return_document=True
        )
        count = result['ticket_count']
        channel_name = f"{count}-{interaction.user.name}"
        # Create in specific category
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=interaction.guild.get_channel(int(cat_id)),
            topic=f"ticket:{guild_id}:{user_id}"
        )
        # Set permissions
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        for role_id in cat_data['roles']:
            role = interaction.guild.get_role(int(role_id))
            if role:
                await channel.set_permissions(role, view_channel=True, send_messages=True)
        # Send initial embed + buttons
        embed = discord.Embed(
            title=self.cfg['panel_embed']['title'],
            description=cat_data['description'],
            color=EMBED_COLOR
        )
        btn_view = View()
        btn_view.add_item(Button(label="📥 Claim", custom_id="claim", style=discord.ButtonStyle.secondary))
        btn_view.add_item(Button(label="🔒 Close", custom_id="close", style=discord.ButtonStyle.danger))
        btn_view.add_item(Button(label="♻️ Reopen", custom_id="reopen", style=discord.ButtonStyle.success, disabled=True))
        btn_view.add_item(Button(label="🗑️ Delete", custom_id="delete", style=discord.ButtonStyle.secondary))
        msg = await channel.send(embed=embed, view=btn_view)
        await msg.pin()
        # Log creation
        log_ch = interaction.guild.get_channel(int(self.cfg['log_channel']))
        if log_ch:
            await log_ch.send(embed=discord.Embed(
                title="Ticket créé",
                description=f"Ticket #{count} créé par {interaction.user.mention}",
                color=EMBED_COLOR
            ))
        # Notify user
        text = MESSAGES.get('TICKET_CREATED', "Ticket créé : {channel}").format(channel=channel.mention)
        await interaction.response.send_message(embed=discord.Embed(description=text, color=EMBED_COLOR), ephemeral=True)

class Tickets(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Commandes de tickets")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_listener(self.on_interaction)
        bot.add_listener(self.on_member_remove)

    @ticket.command(name="config", description="Configure le système de tickets.")
    @app_commands.default_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction) -> None:
        view = ConfigView(interaction.user, interaction.guild_id)
        await view.show_panel(interaction)

    @ticket.command(name="panel", description="Affiche le panneau de création de ticket.")
    @app_commands.describe(channel="Salon où envoyer le panneau")
    async def panel(self, interaction: discord.Interaction, channel: discord.TextChannel=None) -> None:
        cfg = await ticket_collection.find_one({'guild_id': str(interaction.guild_id)})
        if not cfg:
            return await interaction.response.send_message(embed=discord.Embed(
                title=MESSAGES['MISSING_ARGUMENT'],
                description="Le panneau n'est pas configuré.",
                color=EMBED_COLOR
            ), ephemeral=True)
        embed = discord.Embed(
            title=cfg['panel_embed']['title'],
            description=cfg['panel_embed']['description'],
            color=EMBED_COLOR
        )
        view = TicketPanelView(cfg)
        dest = channel or interaction.channel
        await dest.send(embed=embed, view=view)
        await interaction.response.send_message(f"Panneau envoyé dans {dest.mention}", ephemeral=True)

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        cid = interaction.data.get('custom_id')
        channel = interaction.channel
        guild_id = str(interaction.guild_id)
        cfg = await ticket_collection.find_one({'guild_id': guild_id})
        if not cfg:
            return
        topic = getattr(channel, 'topic', '') or ''
        if not topic.startswith(f"ticket:{guild_id}:"):
            return
        if cid == 'claim':
            await channel.set_permissions(interaction.user, send_messages=True)
            await interaction.response.send_message(f"{interaction.user.mention} a claim ce ticket.")
        elif cid == 'close':
            await channel.edit(name=f"ferme-{channel.name}")
            await channel.set_permissions(interaction.guild.default_role, view_channel=False)
            await interaction.response.send_message("Ticket fermé.")
            log_ch = interaction.guild.get_channel(int(cfg['log_channel']))
            if log_ch:
                await log_ch.send(embed=discord.Embed(
                    title="Ticket fermé",
                    description=f"{channel.name} fermé par {interaction.user.mention}",
                    color=EMBED_COLOR
                ))
        elif cid == 'reopen':
            await channel.edit(name=channel.name.replace('ferme-', ''))
            await interaction.response.send_message("Ticket rouvert.")
            log_ch = interaction.guild.get_channel(int(cfg['log_channel']))
            if log_ch:
                await log_ch.send(embed=discord.Embed(
                    title="Ticket rouvert",
                    description=f"{channel.name} rouvert par {interaction.user.mention}",
                    color=EMBED_COLOR
                ))
        elif cid == 'delete':
            await interaction.response.send_message("Suppression du ticket...", ephemeral=True)
            if cfg.get('transcript_channel'):
                # transcript logic here
                pass
            log_ch = interaction.guild.get_channel(int(cfg['log_channel']))
            if log_ch:
                await log_ch.send(embed=discord.Embed(
                    title="Ticket supprimé",
                    description=f"{channel.name} supprimé par {interaction.user.mention}",
                    color=EMBED_COLOR
                ))
            await channel.delete()

    async def on_member_remove(self, member: discord.Member) -> None:
        guild_id = str(member.guild.id)
        for channel in member.guild.text_channels:
            if channel.topic == f"ticket:{guild_id}:{member.id}":
                await channel.send(
                    embed=discord.Embed(
                        description=f"{member.name} a quitté le serveur. Cliquez pour fermer le ticket.",
                        color=EMBED_COLOR
                    ),
                    view=CloseConfirmView(channel)
                )


class CloseConfirmView(View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.channel = channel
        # Bouton de confirmation de fermeture
        self.add_item(Button(label="Oui, fermer", style=discord.ButtonStyle.danger, custom_id="confirm_close"))

    @discord.ui.button(label="Oui, fermer", style=discord.ButtonStyle.danger, custom_id="confirm_close")
    async def confirm(self, interaction: discord.Interaction, button: Button) -> None:
        # Renomme et verrouille le salon
        await self.channel.edit(name=f"ferme-{self.channel.name}")
        await self.channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message("Ticket fermé suite au départ du membre.")

# Ajout de la fonction setup pour charger le cog
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
