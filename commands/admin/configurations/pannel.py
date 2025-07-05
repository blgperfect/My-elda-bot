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
import io

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
        guild_id = interaction.guild.id

        # Extraction et validation des rôles mentionnés
        role_ids = []
        for mention in support_roles.split():
            try:
                rid = int(mention.strip('<@&>'))
                if interaction.guild.get_role(rid):
                    role_ids.append(rid)
            except ValueError:
                continue
        if not role_ids:
            return await interaction.response.send_message(
                "⚠️ Veuillez mentionner au moins un rôle valide.", ephemeral=True
            )

        # Upsert config sans écraser les autres champs
        update = {
            '$set': {
                'panel_channel_id': panel.id,
                'transcript_channel_id': transcript.id,
                'category_id': category.id
            },
            '$addToSet': {'support_roles': {'$each': role_ids}},
            '$setOnInsert': {'ticket_counter': 0}
        }
        config = await soutien_collection.find_one_and_update(
            {'guild_id': guild_id},
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        # Suppression ancien panneau si existant
        if config.get('panel_message_id'):
            try:
                old = await panel.fetch_message(config['panel_message_id'])
                await old.delete()
            except:
                pass

        # Envoi nouveau panneau
        embed = discord.Embed(
            title="🎫 Créer un ticket",
            description=(
                "Pour créer un ticket et contacter l'administration, cliquez ci-dessous "
                f"<:ticket:1390855520533090355>"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = TicketPanelView(self.bot)
        msg = await panel.send(embed=embed, view=view)
        await soutien_collection.update_one(
            {'guild_id': guild_id},
            {'$set': {'panel_message_id': msg.id}}
        )

        await interaction.response.send_message(
            "✅ Configuration enregistrée et panneau mis à jour.", ephemeral=True
        )


class TicketPanelView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @button(emoji=EMOJIS.get('TICKET', '<:ticket:1390855520533090355>'),
            style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild.id
        config = await soutien_collection.find_one_and_update(
            {'guild_id': guild_id},
            {'$inc': {'ticket_counter': 1}},
            return_document=ReturnDocument.AFTER
        )
        count = config['ticket_counter']
        name = f"{count:03d}-{interaction.user.name}"
        category = discord.utils.get(interaction.guild.categories, id=config['category_id'])
        # Permissions
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, read_messages=True,
                send_messages=True, read_message_history=True
            )
        }
        for rid in config['support_roles']:
            role = interaction.guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, read_messages=True,
                    send_messages=True, read_message_history=True
                )

        channel = await interaction.guild.create_text_channel(
            name=name, category=category,
            overwrites=overwrites,
            topic=f"Ticket {name} créé par {interaction.user.id}"
        )

        # Embed d'accueil et pin
        embed = discord.Embed(
            title="🎫 Ticket Ouvert",
            description=(
                "**Merci d'avoir contacté le staff.**\n"
                "Pour tout problème, mentionnez les utilisateurs concernés avec preuves.\n"
                "Pour un partenariat, vérifiez nos conditions.\n"
                "Pour postuler, indiquez le poste."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        mentions = ' '.join(f'<@&{r}>' for r in config['support_roles'])
        view = TicketActionView(config)
        welcome = await channel.send(mentions, embed=embed, view=view)
        await welcome.pin()

        await interaction.response.send_message(
            f"✅ Ticket créé : {channel.mention}", ephemeral=True
        )


class TicketActionView(View):
    def __init__(self, config: dict):
        super().__init__(timeout=None)
        self.config = config

    @button(label="Claim", style=discord.ButtonStyle.secondary, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: Button):
        if not any(r.id in self.config['support_roles'] for r in interaction.user.roles) \
           and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                MESSAGES['PERMISSION_ERROR'], ephemeral=True
            )
        await interaction.channel.send(f"{interaction.user.mention} a claim ce ticket.")
        await interaction.response.defer()

    @button(label="Close", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: Button):
        opener_id = int(interaction.channel.topic.split()[-1])
        opener = interaction.guild.get_member(opener_id)
        if opener:
            await interaction.channel.set_permissions(opener, view_channel=False)
        await interaction.channel.send("🔒 Ticket fermé. Seuls les supports peuvent continuer.")
        await interaction.response.defer()

    @button(label="Reopen", style=discord.ButtonStyle.success, custom_id="reopen_ticket")
    async def reopen(self, interaction: discord.Interaction, button: Button):
        opener_id = int(interaction.channel.topic.split()[-1])
        opener = interaction.guild.get_member(opener_id)
        if opener:
            await interaction.channel.set_permissions(opener, view_channel=True)
        await interaction.channel.send("🔓 Ticket rouvert. Accès rétabli.")
        await interaction.response.defer()

    @button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_ticket")
    async def delete(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "⚠️ Confirmez la suppression ?", view=DeleteConfirmView(self.config), ephemeral=True
        )


class DeleteConfirmView(View):
    def __init__(self, config: dict):
        super().__init__(timeout=None)
        self.config = config

    @button(label="Confirmer", style=discord.ButtonStyle.danger, custom_id="confirm_delete")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        channel = interaction.channel
        transcript_ch = interaction.guild.get_channel(self.config['transcript_channel_id'])
        # Génération du transcript
        buffer = io.StringIO()
        async for msg in channel.history(limit=None, oldest_first=True):
            buffer.write(f"[{msg.created_at.isoformat()}] {msg.author}: {msg.content}\n")
        buffer.seek(0)
        file = discord.File(fp=buffer, filename=f"{channel.name}_transcript.txt")
        embed = discord.Embed(
            title="📝 Transcription de ticket",
            description=(
                f"Ouvreur : <@{channel.topic.split()[-1]}>\n"
                f"Channel : {channel.name}\n"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        if transcript_ch:
            await transcript_ch.send(embed=embed, file=file)
        await channel.delete()
        await interaction.followup.send("Le ticket a été supprimé.", ephemeral=True)

    @button(label="Annuler", style=discord.ButtonStyle.secondary, custom_id="cancel_delete")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Suppression annulée.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketConfigCog(bot))
