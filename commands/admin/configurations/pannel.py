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

class CategoryModal(Modal, title="Nouvelle Catégorie"):
    name = TextInput(label="Nom de la catégorie", placeholder="Ex: Support", max_length=50)
    description = TextInput(label="Description du ticket", placeholder="Décrivez ce qu'on attend...", style=discord.TextStyle.paragraph)

    def __init__(self, parent_view: 'ConfigView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cat_name = self.name.value.strip()
        desc = self.description.value.strip()
        self.parent_view.temp_categories[cat_name] = {
            'description': desc,
            'roles': [r.id for r in self.parent_view.temp_roles]
        }
        await self.parent_view.show_panel(interaction)

class ConfigView(View):
    def __init__(self, author: discord.Member, guild_id: int):
        super().__init__(timeout=300)
        self.author = author
        self.guild_id = guild_id
        self.embed_data = {}
        self.temp_categories: dict[str, dict] = {}
        self.temp_roles: list[discord.Role] = []
        self.log_channel: int | None = None
        self.ticket_category: int | None = None
        self.message: discord.Message | None = None

    async def show_panel(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=self.embed_data.get('title', '🏷️ Configuration Ticket'),
            description=(
                f"**Titre Embed:** `{self.embed_data.get('title', '❌')}`\n"
                f"**Description Embed:** `{self.embed_data.get('description', '❌')}`\n"
                f"**Image Embed:** `{self.embed_data.get('image', '❌')}`\n"
                f"**Footer Embed:** `{self.embed_data.get('footer', '❌')}`\n"
                f"**Catégories:** {len(self.temp_categories)}/5\n"
                f"**Salon Logs:** {f'<#{self.log_channel}>' if self.log_channel else '❌'}\n"
                f"**Catégorie Discord:** {f'<#{self.ticket_category}>' if self.ticket_category else '❌'}"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        self.clear_items()
        self.add_item(Button(label="Définir Embed", style=discord.ButtonStyle.primary, custom_id="set_embed"))
        self.add_item(Button(label="Ajouter Catégorie", style=discord.ButtonStyle.primary, custom_id="add_category", disabled=len(self.temp_categories)>=5))
        self.add_item(Button(label="Salon Logs", style=discord.ButtonStyle.primary, custom_id="set_logs"))
        self.add_item(Button(label="Catégorie Discord", style=discord.ButtonStyle.primary, custom_id="set_channel_cat"))
        finish = Button(
            label="Valider Configuration",
            style=discord.ButtonStyle.success,
            custom_id="finish",
            disabled=not all([
                self.embed_data.get('title'),
                self.embed_data.get('description'),
                self.log_channel,
                self.ticket_category
            ])
        )
        self.add_item(finish)

        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.message:
            await self.message.edit(embed=embed, view=self)
        else:
            msg = await interaction.followup.send(embed=embed, view=self, ephemeral=True)
            self.message = msg

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(content="⌛ Configuration expirée.", view=self)

    @discord.ui.button(label="Définir Embed", style=discord.ButtonStyle.primary, custom_id="set_embed")
    async def _set_embed(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        modal = Modal(title="Configuration Embed")
        title_in = TextInput(label="Titre", placeholder="Titre du panneau", max_length=100)
        desc_in = TextInput(label="Description", style=discord.TextStyle.paragraph)
        img_in = TextInput(label="Image URL", required=False)
        foot_in = TextInput(label="Footer", required=False)
        modal.add_item(title_in)
        modal.add_item(desc_in)
        modal.add_item(img_in)
        modal.add_item(foot_in)

        async def modal_submit(modal_inter: discord.Interaction):
            self.embed_data['title'] = title_in.value.strip()
            self.embed_data['description'] = desc_in.value.strip()
            self.embed_data['image'] = img_in.value.strip()
            self.embed_data['footer'] = foot_in.value.strip()
            await self.show_panel(modal_inter)
        modal.on_submit = modal_submit  # type: ignore
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Ajouter Catégorie", style=discord.ButtonStyle.primary, custom_id="add_category")
    async def _add_category(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        modal = CategoryModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Salon Logs", style=discord.ButtonStyle.primary, custom_id="set_logs")
    async def _set_logs(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        view = View()
        sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.text])
        async def cb(resp: discord.Interaction):
            self.log_channel = sel.values[0].id  # type: ignore
            await self.show_panel(resp)
            await resp.delete_original_response()
        sel.callback = cb
        view.add_item(sel)
        await interaction.response.send_message("Sélectionnez le salon de logs :", view=view, ephemeral=True)

    @discord.ui.button(label="Catégorie Discord", style=discord.ButtonStyle.primary, custom_id="set_channel_cat")
    async def _set_channel_cat(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        view = View()
        sel = ChannelSelect(min_values=1, max_values=1, channel_types=[discord.ChannelType.category])
        async def cb(resp: discord.Interaction):
            self.ticket_category = sel.values[0].id  # type: ignore
            await self.show_panel(resp)
            await resp.delete_original_response()
        sel.callback = cb
        view.add_item(sel)
        await interaction.response.send_message("Sélectionnez la catégorie Discord :", view=view, ephemeral=True)

    @discord.ui.button(label="Valider Configuration", style=discord.ButtonStyle.success, custom_id="finish")
    async def _finish(self, interaction: discord.Interaction, button: Button) -> None:
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        data = {
            'guild_id': str(self.guild_id),
            'panel_embed': self.embed_data,
            'categories': self.temp_categories,
            'log_channel': str(self.log_channel),
            'ticket_category': str(self.ticket_category),
            'ticket_count': 0
        }
        await ticket_collection.update_one(
            {'guild_id': str(self.guild_id)},
            {'$set': data},
            upsert=True
        )
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
        user_id = interaction.user.id
        guild_id = str(interaction.guild_id)
        existing = discord.utils.get(interaction.guild.text_channels, topic=f"ticket:{guild_id}:{user_id}")
        if existing:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=MESSAGES['TICKET_EXISTS'],
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )
        # increment count
        result = await ticket_collection.find_one_and_update(
            {'guild_id': guild_id},
            {'$inc': {'ticket_count': 1}},
            return_document=True
        )
        count = result['ticket_count']
        label = f"{count}-{interaction.user.name}"
        channel = await interaction.guild.create_text_channel(
            name=label,
            category=interaction.guild.get_channel(int(self.cfg['ticket_category'])),
            topic=f"ticket:{guild_id}:{user_id}"
        )
        # permissions
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        for role_id in self.cfg['categories'][interaction.data['values'][0]]['roles']:
            role = interaction.guild.get_role(int(role_id))
            if role:
                await channel.set_permissions(role, view_channel=True, send_messages=True)
        # send initial embed
        desc = self.cfg['categories'][interaction.data['values'][0]]['description']
        embed = discord.Embed(
            title=self.cfg['panel_embed']['title'],
            description=desc,
            color=EMBED_COLOR
        )
        btn_view = View()
        btn_view.add_item(Button(label="📥 Claim", custom_id="claim", style=discord.ButtonStyle.secondary))
        btn_view.add_item(Button(label="🔒 Close", custom_id="close", style=discord.ButtonStyle.danger))
        btn_view.add_item(Button(label="♻️ Reopen", custom_id="reopen", style=discord.ButtonStyle.success, disabled=True))
        btn_view.add_item(Button(label="🗑️ Delete", custom_id="delete", style=discord.ButtonStyle.secondary))
        msg = await channel.send(embed=embed, view=btn_view)
        await msg.pin()
        # log
        log_ch = interaction.guild.get_channel(int(self.cfg['log_channel']))
        if log_ch:
            await log_ch.send(embed=discord.Embed(
                title="Ticket créé",
                description=f"Ticket #{count} créé par {interaction.user.mention}",
                color=EMBED_COLOR
            ))
        await interaction.response.send_message(
            embed=discord.Embed(
                description=MESSAGES['TICKET_CREATED'].format(channel=channel.mention),
                color=EMBED_COLOR
            ),
            ephemeral=True
        )

class Tickets(commands.Cog):
    """Cog pour le système de tickets ultra configurable."""

    ticket = app_commands.Group(name="ticket", description="Commandes de tickets")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_listener(self.on_button_click, 'on_interaction')
        bot.add_listener(self.on_member_remove)

    @ticket.command(name="config", description="Configure le système de tickets.")
    @app_commands.default_permissions(administrator=True)
    async def ticket_config(self, interaction: discord.Interaction) -> None:
        view = ConfigView(interaction.user, interaction.guild_id)
        await view.show_panel(interaction)

    @ticket.command(name="panel", description="Affiche le panneau de création de ticket.")
    async def ticket_panel(self, interaction: discord.Interaction) -> None:
        cfg = await ticket_collection.find_one({'guild_id': str(interaction.guild_id)})
        if not cfg:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title=MESSAGES['MISSING_ARGUMENT'],
                    description="Le panneau n'est pas configuré.",
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )
        embed = discord.Embed(
            title=cfg['panel_embed']['title'],
            description=cfg['panel_embed']['description'],
            color=EMBED_COLOR
        )
        select_view = TicketPanelView(cfg)
        await interaction.response.send_message(embed=embed, view=select_view)

    async def on_button_click(self, interaction: discord.Interaction) -> None:
        if not interaction.data or 'custom_id' not in interaction.data:
            return
        cid = interaction.data['custom_id']
        channel = interaction.channel
        guild_id = str(interaction.guild_id)
        # retrieve config
        cfg = await ticket_collection.find_one({'guild_id': guild_id})
        if not cfg:
            return
        # load ticket topic
        topic = getattr(channel, 'topic', '') or ''
        if not topic.startswith(f"ticket:{guild_id}:"):
            return
        user_id = int(topic.split(':')[2])
        # buttons
        if cid == 'claim':
            await channel.set_permissions(interaction.user, send_messages=True)
            await interaction.response.send_message(f"{interaction.user.mention} a claim ce ticket.", ephemeral=False)
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
            topic = channel.topic or ''
            if topic == f"ticket:{guild_id}:{member.id}":
                await channel.send(
                    embed=discord.Embed(
                        description=f"{member.name} a quitté le serveur. Cliquer pour fermer le ticket.",
                        color=EMBED_COLOR
                    ),
                    view=CloseConfirmView(channel)
                )

class CloseConfirmView(View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.channel = channel
        self.add_item(Button(label="Oui, fermer", style=discord.ButtonStyle.danger, custom_id="confirm_close"))

    @discord.ui.button(label="Oui, fermer", style=discord.ButtonStyle.danger, custom_id="confirm_close")
    async def confirm(self, interaction: discord.Interaction, button: Button) -> None:
        await self.channel.edit(name=f"ferme-{self.channel.name}")
        await self.channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message("Ticket fermé suite au départ du membre.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
