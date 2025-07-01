# cogs/suggestion.py

import re
import datetime
import discord
from discord.ext import commands
from discord import app_commands, PartialEmoji
from discord.ui import View, Button, Modal, TextInput

from config.mongo import suggestions_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

def _now_utc():
    return datetime.datetime.utcnow()

def parse_label(label: str):
    """Parse label for custom emoji syntax <:name:id>."""
    m = re.fullmatch(r"<:(?P<name>\w+):(?P<id>\d+)>", label)
    if m:
        return None, PartialEmoji(name=m.group('name'), id=int(m.group('id')))
    return label, None

class SuggestionButton(Button):
    def __init__(self, guild_id: int, label: str):
        lbl, emoji = parse_label(label)
        super().__init__(label=lbl, emoji=emoji, style=discord.ButtonStyle.primary, custom_id=f"suggest_button:{guild_id}")
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("Mauvais serveur.", ephemeral=True)
            return
        await interaction.response.send_modal(SuggestionModal(self.guild_id))

class SuggestionConfigView(View):
    def __init__(self, bot: commands.Bot, guild_id: int, channel_id: int, button_label: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.add_item(SuggestionButton(guild_id, button_label))

class SuggestionModal(Modal, title="Votre suggestion"):
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.add_item(TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            placeholder="Merci de soumettre votre suggestion!",
            custom_id="suggestion_input",
            required=True,
            max_length=2000
        ))

    async def on_submit(self, interaction: discord.Interaction):
        config = await suggestions_collection.find_one({"kind": "config", "guild_id": self.guild_id})
        if not config:
            await interaction.response.send_message("Le panneau n'est pas configuré.", ephemeral=True)
            return

        new_count = config.get("count", 0) + 1
        await suggestions_collection.update_one({"_id": config["_id"]}, {"$set": {"count": new_count}})

        description = self.children[0].value
        author = interaction.user
        created_at = _now_utc()

        embed = discord.Embed(
            title=f"Suggestion #{new_count}",
            description=description,
            color=EMBED_COLOR
        )
        embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
        embed.set_footer(
            text=f"{created_at.strftime('%Y-%m-%d %H:%M UTC')} • {EMBED_FOOTER_TEXT}",
            icon_url=EMBED_FOOTER_ICON_URL
        )

        view = ApproveRejectView(self.guild_id, new_count)
        channel = interaction.client.get_channel(config["channel_id"])
        suggestion_msg = await channel.send(embed=embed, view=view)

        await suggestions_collection.insert_one({
            "kind": "suggestion",
            "guild_id": self.guild_id,
            "suggestion_id": new_count,
            "channel_id": config["channel_id"],
            "author_id": str(author.id),
            "author_name": author.display_name,
            "description": description,
            "created_at": created_at,
            "message_id": str(suggestion_msg.id)
        })

        try:
            old = await channel.fetch_message(int(config.get("message_id", 0)))
            await old.delete()
        except Exception:
            pass

        panel_embed = discord.Embed(
            title="Soumettez votre suggestion",
            description="Merci de soumettre votre suggestion!",
            color=EMBED_COLOR
        )
        panel_embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        panel_msg = await channel.send(
            embed=panel_embed,
            view=SuggestionConfigView(
                interaction.client,
                self.guild_id,
                config["channel_id"],
                config["button_label"]
            )
        )
        await suggestions_collection.update_one(
            {"kind": "config", "guild_id": self.guild_id},
            {"$set": {"message_id": str(panel_msg.id)}}
        )

        await interaction.response.send_message("✅ Votre suggestion a été envoyée !", ephemeral=True)

class ApproveButton(Button):
    def __init__(self, guild_id: int, suggestion_id: int):
        super().__init__(label="Approuver", style=discord.ButtonStyle.success,
                         custom_id=f"approve_button:{guild_id}:{suggestion_id}")
        self.guild_id = guild_id
        self.suggestion_id = suggestion_id

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Permission refusée.", ephemeral=True)
            return

        msg = interaction.message
        embed = msg.embeds[0]
        decision_time = _now_utc().strftime('%Y-%m-%d %H:%M UTC')
        embed.color = discord.Color.green()
        embed.add_field(
            name="Statut",
            value=f"Approuvé par {interaction.user.display_name} le {decision_time}",
            inline=False
        )

        await suggestions_collection.delete_one({
            "kind": "suggestion",
            "guild_id": self.guild_id,
            "suggestion_id": self.suggestion_id
        })

        await msg.edit(embed=embed, view=None)
        await interaction.response.send_message("Suggestion approuvée.", ephemeral=True)

class RejectButton(Button):
    def __init__(self, guild_id: int, suggestion_id: int):
        super().__init__(label="Rejeter", style=discord.ButtonStyle.danger,
                         custom_id=f"reject_button:{guild_id}:{suggestion_id}")
        self.guild_id = guild_id
        self.suggestion_id = suggestion_id

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Permission refusée.", ephemeral=True)
            return

        msg = interaction.message
        embed = msg.embeds[0]
        decision_time = _now_utc().strftime('%Y-%m-%d %H:%M UTC')
        embed.color = discord.Color.red()
        embed.add_field(
            name="Statut",
            value=f"Rejeté par {interaction.user.display_name} le {decision_time}",
            inline=False
        )

        await suggestions_collection.delete_one({
            "kind": "suggestion",
            "guild_id": self.guild_id,
            "suggestion_id": self.suggestion_id
        })

        await msg.edit(embed=embed, view=None)
        await interaction.response.send_message("Suggestion rejetée.", ephemeral=True)

class ApproveRejectView(View):
    def __init__(self, guild_id: int, suggestion_id: int):
        super().__init__(timeout=None)
        self.add_item(ApproveButton(guild_id, suggestion_id))
        self.add_item(RejectButton(guild_id, suggestion_id))

class SuggestionCog(commands.Cog):
    """Cog pour gérer le système de suggestions"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Recharge les vues persistantes au démarrage
        async for config in suggestions_collection.find({"kind": "config"}):
            view = SuggestionConfigView(self.bot,
                                        config["guild_id"],
                                        config["channel_id"],
                                        config["button_label"])
            try:
                chan = self.bot.get_channel(config["channel_id"])
                msg = await chan.fetch_message(int(config["message_id"]))
                self.bot.add_view(view, message_id=msg.id)
            except:
                pass
        async for sugg in suggestions_collection.find({"kind": "suggestion"}):
            view = ApproveRejectView(sugg["guild_id"], sugg["suggestion_id"])
            try:
                chan = self.bot.get_channel(sugg["channel_id"])
                msg = await chan.fetch_message(int(sugg["message_id"]))
                self.bot.add_view(view, message_id=msg.id)
            except:
                pass

    @app_commands.command(name="set_suggestion")
    @app_commands.describe(
        channel="Salon pour le panneau de suggestions",
        button_label="Texte du bouton Soumettre"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_suggestion(self, interaction: discord.Interaction,
                             channel: discord.TextChannel,
                             button_label: str = "📝 Suggérer"):
        now = _now_utc()
        config = await suggestions_collection.find_one({"kind": "config", "guild_id": interaction.guild_id})
        if config:
            await suggestions_collection.update_one(
                {"_id": config["_id"]},
                {"$set": {"channel_id": channel.id, "button_label": button_label}}
            )
        else:
            config = {
                "kind": "config",
                "guild_id": interaction.guild_id,
                "channel_id": channel.id,
                "button_label": button_label,
                "count": 0,
                "message_id": None,
                "created_at": now
            }
            await suggestions_collection.insert_one(config)

        try:
            if config.get("message_id"):
                old = await channel.fetch_message(int(config["message_id"]))
                await old.delete()
        except:
            pass

        panel_embed = discord.Embed(
            title="Soumettez votre suggestion",
            description="Merci de soumettre votre suggestion!",
            color=EMBED_COLOR
        )
        panel_embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        panel_msg = await channel.send(embed=panel_embed,
                                       view=SuggestionConfigView(self.bot, interaction.guild_id, channel.id, button_label))
        await suggestions_collection.update_one(
            {"kind": "config", "guild_id": interaction.guild_id},
            {"$set": {"message_id": str(panel_msg.id)}}
        )

        await interaction.response.send_message(f"✅ Panneau de suggestions configuré dans {channel.mention}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SuggestionCog(bot))
