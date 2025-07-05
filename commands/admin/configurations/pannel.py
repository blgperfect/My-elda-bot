import io
import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from discord.ui import View, button, Button
from dataclasses import dataclass
from typing import List, Optional
from config.mongo import ticket_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL
from pymongo import ReturnDocument

# -------- Data Model --------
@dataclass
class PanelConfig:
    panel_channel_id: int
    category_id: int
    transcript_channel_id: int
    role_ids: List[int]

# -------- Mongo Helpers (async) --------
async def get_config(guild_id: int) -> Optional[PanelConfig]:
    doc = await ticket_collection.find_one({'_id': guild_id})
    if not doc:
        return None
    return PanelConfig(
        panel_channel_id=doc['panel_channel_id'],
        category_id=doc['category_id'],
        transcript_channel_id=doc['transcript_channel_id'],
        role_ids=doc.get('role_ids', [])
    )

async def upsert_config(guild_id: int, cfg: PanelConfig):
    await ticket_collection.update_one(
        {'_id': guild_id},
        {'$set': {
            'panel_channel_id': cfg.panel_channel_id,
            'category_id': cfg.category_id,
            'transcript_channel_id': cfg.transcript_channel_id,
            'role_ids': cfg.role_ids
        },
         '$setOnInsert': {'count': 0}
        },
        upsert=True
    )

async def reset_config(guild_id: int):
    await ticket_collection.delete_one({'_id': guild_id})

async def next_ticket_number(guild_id: int) -> int:
    updated = await ticket_collection.find_one_and_update(
        {'_id': guild_id},
        {'$inc': {'count': 1}},
        projection={'count': True},
        return_document=ReturnDocument.AFTER,
        upsert=True
    )
    return updated.get('count', 1)

# -------- Views --------
class TicketPanelView(View):
    def __init__(self, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.bot = bot

    @button(label="🎟 Ouvrir un ticket", style=discord.ButtonStyle.blurple, custom_id="ticket.open")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        cfg = await get_config(self.guild_id)
        if not cfg:
            return await interaction.followup.send(
                "⚠️ Le système n'est pas configuré. `/ticket config` d'abord.",
                ephemeral=True
            )

        guild = interaction.guild
        category = guild.get_channel(cfg.category_id)
        if not isinstance(category, discord.CategoryChannel):
            return await interaction.followup.send(
                "❌ La catégorie configurée est invalide.",
                ephemeral=True
            )

        num = await next_ticket_number(self.guild_id)
        channel_name = f"{num}-{interaction.user.name}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        mentions = []
        for rid in cfg.role_ids:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                mentions.append(role.mention)

        ticket_ch = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        view = TicketManagementView(self.guild_id, interaction.user.id)
        embed = discord.Embed(
            title=f"Ticket #{num}",
            description=(
                f"Bonjour {interaction.user.mention},\n"
                "Merci d’avoir ouvert un ticket.\n"
                "Notre équipe va vous répondre sous peu."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await ticket_ch.send(embed=embed, view=view)
        if mentions:
            await ticket_ch.send(" ".join(mentions))

        await interaction.followup.send(
            f"✅ Ticket créé : {ticket_ch.mention}",
            ephemeral=True
        )

class TicketManagementView(View):
    def __init__(self, guild_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.claimed = False

    def _has_permission(self, member: discord.Member) -> bool:
        if member.id == self.owner_id:
            return True
        return any(role.id in (asyncio.run(get_config(self.guild_id)).role_ids)
                   for role in member.roles)

    @button(label="✅ Claim", style=discord.ButtonStyle.success, custom_id="ticket.claim")
    async def claim(self, interaction: discord.Interaction, button: Button):
        if not self._has_permission(interaction.user):
            return await interaction.response.send_message(
                "❌ Vous n'avez pas la permission de gérer ce ticket.",
                ephemeral=True
            )
        if self.claimed:
            return await interaction.response.send_message(
                "ℹ️ Ce ticket est déjà pris en charge.",
                ephemeral=True
            )
        self.claimed = True
        await interaction.channel.send(f"✅ Ticket pris en charge par {interaction.user.mention}.")
        await interaction.response.defer()

    @button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="ticket.close")
    async def close(self, interaction: discord.Interaction, button: Button):
        if not self._has_permission(interaction.user):
            return await interaction.response.send_message(
                "❌ Vous n'avez pas la permission de gérer ce ticket.",
                ephemeral=True
            )
        cfg = await get_config(self.guild_id)
        guild = interaction.guild
        overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        overwrites[interaction.user] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
        for rid in cfg.role_ids:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        await interaction.channel.edit(overwrites=overwrites)
        await interaction.channel.send("🔒 Le ticket est désormais fermé.")
        await interaction.response.defer()

    @button(label="🔓 Reopen", style=discord.ButtonStyle.grey, custom_id="ticket.reopen")
    async def reopen(self, interaction: discord.Interaction, button: Button):
        if not self._has_permission(interaction.user):
            return await interaction.response.send_message(
                "❌ Vous n'avez pas la permission de gérer ce ticket.",
                ephemeral=True
            )
        cfg = await get_config(self.guild_id)
        guild = interaction.guild
        overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        overwrites[interaction.user] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        for rid in cfg.role_ids:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        await interaction.channel.edit(overwrites=overwrites, category=interaction.channel.category)
        await interaction.channel.send("🔓 Le ticket a été rouvert.")
        await interaction.response.defer()

    @button(label="🗑 Delete", style=discord.ButtonStyle.red, custom_id="ticket.delete")
    async def delete(self, interaction: discord.Interaction, button: Button):
        if not self._has_permission(interaction.user):
            return await interaction.response.send_message(
                "❌ Vous n'avez pas la permission de gérer ce ticket.",
                ephemeral=True
            )
        cfg = await get_config(self.guild_id)
        if not cfg:
            return await interaction.response.send_message(
                "⚠️ Config introuvable, impossible de sauvegarder la transcription.",
                ephemeral=True
            )

        msgs = [m async for m in interaction.channel.history(oldest_first=True)]
        transcript = "\n".join(
            f"[{m.created_at.isoformat()}] {m.author.display_name}: {m.content}"
            for m in msgs
        )

        buffer = io.StringIO(transcript)
        buffer.seek(0)
        file = discord.File(fp=buffer, filename=f"transcript-{interaction.channel.name}.txt")

        t_ch = interaction.guild.get_channel(cfg.transcript_channel_id)
        if t_ch:
            await t_ch.send(
                content=f"**Transcript du ticket {interaction.channel.name}**",
                file=file
            )

        await interaction.channel.delete()

class ResetView(View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=60)
        self.cog = cog

    @button(label="⚠️ Confirmer Reset", style=discord.ButtonStyle.danger, custom_id="ticket.reset.confirm")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await reset_config(interaction.guild_id)
        await interaction.response.edit_message(content="✅ Configuration remise à zéro.", view=None)

    @button(label="❌ Annuler", style=discord.ButtonStyle.secondary, custom_id="ticket.reset.cancel")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="ℹ️ Réinitialisation annulée.", view=None)

# -------- Cog --------
class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    ticket = app_commands.Group(
        name="ticket",
        description="Gestion du système de tickets"
    )

    @ticket.command(
        name="config",
        description="Configurer le panneau de tickets"
    )
    @app_commands.describe(
        panel_channel="Salon où envoyer le panneau",
        category="Catégorie pour les tickets",
        transcript_channel="Salon pour les transcriptions",
        roles="Rôles autorisés (au moins un, séparés par espace)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_config(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        category: discord.CategoryChannel,
        transcript_channel: discord.TextChannel,
        roles: str
    ):
        role_ids = [int(r.strip("<@&>")) for r in roles.split()]
        if not role_ids:
            return await interaction.response.send_message(
                "❌ Vous devez mentionner au moins un rôle.",
                ephemeral=True
            )

        cfg = PanelConfig(
            panel_channel_id=panel_channel.id,
            category_id=category.id,
            transcript_channel_id=transcript_channel.id,
            role_ids=role_ids
        )
        await upsert_config(interaction.guild.id, cfg)

        content = "🎟 Appuyez sur le bouton ci-dessous pour ouvrir un ticket"
        embed = discord.Embed(
            title="Ouvrir un ticket",
            description="Cliquez sur le bouton pour créer un nouveau ticket.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        view = TicketPanelView(interaction.guild.id, self.bot)
        await panel_channel.send(content=content, embed=embed, view=view)
        await interaction.response.send_message(
            "✅ Panneau de tickets configuré et envoyé en embed.",
            ephemeral=True
        )

    @ticket.command(
        name="reset",
        description="Réinitialiser la configuration des tickets"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_reset(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⚠️ Confirmez la réinitialisation du système de tickets :",
            view=ResetView(self),
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
