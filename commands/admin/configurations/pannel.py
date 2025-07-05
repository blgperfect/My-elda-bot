import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, button
from pymongo import ReturnDocument
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import soutien_collection

class TicketConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket-config")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        panel="Salon où poster le panneau de création de ticket",
        transcript="Salon pour les transcriptions",
        category="Catégorie où créer les tickets",
        support_roles="Rôles à qui donner accès (mentionnés séparés par espace)"
    )
    async def ticket_config(
        self,
        interaction: discord.Interaction,
        panel: discord.TextChannel,
        transcript: discord.TextChannel,
        category: discord.CategoryChannel,
        support_roles: str,
    ):
        """
        Configure les paramètres de ticket : panneau, transcription, catégorie et rôles de support.
        Tous les paramètres sont obligatoires.
        """
        guild_id = interaction.guild.id
        # Extraction des IDs de rôles depuis les mentions
        role_ids = []
        for mention in support_roles.split():
            try:
                role_id = int(mention.strip('<@&>'))
                if interaction.guild.get_role(role_id):
                    role_ids.append(role_id)
            except ValueError:
                continue
        if not role_ids:
            return await interaction.response.send_message(
                "️️️⚠️ Veuillez mentionner au moins un rôle valide pour support_roles.", ephemeral=True
            )

        # Mise à jour MongoDB (ticket_counter initialisé si nécessaire)
        config = await soutien_collection.find_one_and_update(
            {'guild_id': guild_id},
            {
                '$set': {
                    'panel_channel_id': panel.id,
                    'transcript_channel_id': transcript.id,
                    'category_id': category.id
                },
                '$addToSet': {'support_roles': {'$each': role_ids}},
                '$setOnInsert': {'ticket_counter': 0}
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        # Supprimer l'ancien panneau si existant
        if config.get('panel_message_id'):
            try:
                old_msg = await panel.fetch_message(config['panel_message_id'])
                await old_msg.delete()
            except Exception:
                pass

        # Création du nouveau panneau
        embed = discord.Embed(
            title="🎫 Créer un ticket",
            description=(
                "Pour créer un ticket et contacter l'administration, cliquez sur le bouton ci-dessous "
                f"<:ticket:1390855520533090355>"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = TicketPanelView(self.bot)
        msg = await panel.send(embed=embed, view=view)
        await msg.pin()

        await soutien_collection.update_one(
            {'guild_id': guild_id},
            {'$set': {'panel_message_id': msg.id}}
        )

        await interaction.response.send_message(
            "✅ Configuration complète enregistrée et panneau mis à jour.",
            ephemeral=True
        )


class TicketPanelView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @button(
        emoji=EMOJIS.get('TICKET', '<:ticket:1390855520533090355>'),
        style=discord.ButtonStyle.primary,
        custom_id="create_ticket"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild.id
        config = await soutien_collection.find_one_and_update(
            {'guild_id': guild_id},
            {'$inc': {'ticket_counter': 1}},
            return_document=ReturnDocument.AFTER
        )
        counter = config['ticket_counter']
        name = f"{counter:03d}-{interaction.user.name}"
        category = discord.utils.get(interaction.guild.categories, id=config['category_id'])
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, read_messages=True, send_messages=True, read_message_history=True
            ),
        }
        for role_id in config.get('support_roles', []):
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, read_messages=True, send_messages=True, read_message_history=True
                )
        # Les admins gardent l'accès
        overwrites[interaction.guild.roles[0]] = discord.PermissionOverwrite(view_channel=True)

        channel = await interaction.guild.create_text_channel(
            name=name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket {name} créé par {interaction.user.id}"
        )

        embed = discord.Embed(
            title="🎫 Ticket Ouvert",
            description=(
                "**Merci d'avoir contacté le staff.**\n"
                "Pour tout problème, mentionnez les utilisateurs concernés ainsi que les preuves à l'appui.\n"
                "Pour un partenariat, assurez-vous d'avoir lu nos conditions.\n"
                "Pour postuler, mentionnez le poste que vous souhaitez."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        mentions = ' '.join(f'<@&{r}>' for r in config.get('support_roles', []))
        welcome_view = TicketActionView(config)
        await channel.send(mentions, embed=embed, view=welcome_view)
        await interaction.response.send_message(
            f"✅ Ticket créé : {channel.mention}", ephemeral=True
        )


class TicketActionView(View):
    def __init__(self, config: dict):
        super().__init__(timeout=None)
        self.config = config

    @button(label="Claim", style=discord.ButtonStyle.secondary, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: Button):
        if not any(r.id in self.config.get('support_roles', []) for r in interaction.user.roles) and \
           not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(MESSAGES['PERMISSION_ERROR'], ephemeral=True)
        await interaction.channel.send(f"{interaction.user.mention} a claim ce ticket.")
        await interaction.response.defer()

    @button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        opener_id = int(interaction.channel.topic.split()[-1])
        opener = guild.get_member(opener_id)
        if opener:
            await interaction.channel.set_permissions(opener, view_channel=False)
        await interaction.response.defer()

    @button(label="Reopen", style=discord.ButtonStyle.success, custom_id="reopen_ticket")
    async def reopen(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        opener_id = int(interaction.channel.topic.split()[-1])
        opener = guild.get_member(opener_id)
        if opener:
            await interaction.channel.set_permissions(opener, view_channel=True)
        await interaction.response.defer()

    @button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_ticket")
    async def delete(self, interaction: discord.Interaction, button: Button):
        transcript_ch = interaction.guild.get_channel(self.config['transcript_channel_id'])
        embed = discord.Embed(
            title="📝 Transcription de ticket",
            description=(
                f"Ouvreur : <@{interaction.channel.topic.split()[-1]}>\n"
                f"Channel : {interaction.channel.name}\n"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        if transcript_ch:
            await transcript_ch.send(embed=embed)
        await interaction.channel.delete()

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketConfigCog(bot))
