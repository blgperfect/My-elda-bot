# commands/giveaway.py

import asyncio
import re
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Select, Button

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
)
from config.mongo import giveaways_collection

_EMOJI_RE = re.compile(r'<:(\w+):(\d+)>')

def parse_duration(text: str) -> timedelta:
    unit = text[-1].lower()
    val  = int(text[:-1])
    return {
        "m": timedelta(minutes=val),
        "h": timedelta(hours=val),
        "d": timedelta(days=val),
        "w": timedelta(weeks=val),
    }.get(unit, timedelta(minutes=val))

def make_participate_button(label_raw: str) -> Button:
    m = _EMOJI_RE.search(label_raw)
    if m:
        name, eid = m.groups()
        emoji = discord.PartialEmoji(name=name, id=int(eid))
        text = _EMOJI_RE.sub('', label_raw).strip() or None
        return Button(label=text, emoji=emoji, style=discord.ButtonStyle.primary, custom_id="giveaway_participate")
    return Button(label=label_raw, style=discord.ButtonStyle.primary, custom_id="giveaway_participate")


class GiveawayModal(Modal, title="📢 Lancer un Giveaway"):
    titre   = TextInput(label="Titre du giveaway", required=True)
    reward  = TextInput(label="Récompense", required=True)
    winners = TextInput(label="Nombre de gagnants", required=True, placeholder="ex: 1")
    duree   = TextInput(label="Durée (m,h,d,w)", required=True, placeholder="ex: 10m")

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            "title":       self.titre.value,
            "reward":      self.reward.value,
            "winners":     int(self.winners.value),
            "duration":    self.duree.value,
            "created_at":  datetime.now(timezone.utc),
            "participants": []
        }

        await interaction.response.send_message(
            f"{interaction.user.mention}, écris le label pour le bouton (ou `skip` pour « Participer »)."
        )
        prompt = await interaction.original_response()

        def check_label(m: discord.Message):
            return (
                m.author.id == interaction.user.id
                and m.channel.id == interaction.channel.id
                and not m.author.bot
            )

        try:
            label_msg = await interaction.client.wait_for(
                "message", check=check_label, timeout=60
            )
        except asyncio.TimeoutError:
            await prompt.delete()
            return await interaction.channel.send(
                "⏱️ Temps écoulé.", delete_after=10
            )

        raw = label_msg.content.strip()
        data["button_label"] = "Participer" if raw.lower() == "skip" else raw
        await prompt.delete()
        await label_msg.delete()

        # === Sélecteur de salon ===
        class ChannelSelect(Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=ch.name, value=str(ch.id))
                    for ch in interaction.guild.text_channels
                ]
                super().__init__(
                    placeholder="Choisissez un salon…",
                    min_values=1, max_values=1,
                    options=options,
                    custom_id="giveaway_channel"
                )

            async def callback(self, select_intr: discord.Interaction):
                chan = select_intr.guild.get_channel(int(self.values[0]))
                data["channel_id"] = chan.id

                # Calcul de la fin du giveaway
                end = data["created_at"] + parse_duration(data["duration"])
                ts = int(end.timestamp())

                embed = discord.Embed(
                    title=data["title"],
                    description=(
                        f"Récompense : **{data['reward']}**\n"
                        f"Gagnants : **{data['winners']}**\n"
                        f"Fin dans : <t:{ts}:R>"
                    ),
                    color=EMBED_COLOR,
                    timestamp=end
                )
                embed.set_footer(
                    text=EMBED_FOOTER_TEXT,
                    icon_url=EMBED_FOOTER_ICON_URL
                )

                # Création de la View finale
                final_view = GiveawayView(data)
                msg = await chan.send(embed=embed, view=final_view)

                # Sauvegarde en base MongoDB
                doc = data.copy()
                doc["_id"] = msg.id
                await giveaways_collection.insert_one(doc)

                await select_intr.response.edit_message(
                    content=f"✅ Giveaway créé dans {chan.mention} !",
                    view=None
                )

        sel_view = View(timeout=None)
        sel_view.add_item(ChannelSelect())
        await interaction.channel.send(
            f"{interaction.user.mention}, dans quel salon envoyer le giveaway ?",
            view=sel_view
        )


class GiveawayView(View):
    def __init__(self, data: dict):
        super().__init__(timeout=None)
        self.data = data

        # Bouton Participer (manuellement)
        self.add_item(make_participate_button(data["button_label"]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        # restreindre les mod actions
        if cid in ("giveaway_cancel", "giveaway_reroll", "giveaway_draw"):
            if not interaction.user.guild_permissions.ban_members:
                await interaction.response.send_message(
                    "❌ Vous n'avez pas la permission.", ephemeral=True
                )
                return False
        return True

    @discord.ui.button(
        label="Annuler",
        style=discord.ButtonStyle.danger,
        custom_id="giveaway_cancel"
    )
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.message.delete()
        await giveaways_collection.delete_one({"_id": self.data["_id"]})
        await interaction.response.send_message("🚫 Giveaway annulé.", ephemeral=True)

    @discord.ui.button(
        label="Reroll",
        style=discord.ButtonStyle.secondary,
        custom_id="giveaway_reroll"
    )
    async def reroll(self, interaction: discord.Interaction, button: Button):
        doc = await giveaways_collection.find_one({"_id": self.data["_id"]})
        parts = doc.get("participants", [])
        if not parts:
            return await interaction.response.send_message(
                "⚠️ Pas de participants.", ephemeral=True
            )
        winner = random.choice(parts)
        await interaction.response.send_message(
            f"🎉 Nouveau gagnant : <@{winner}>", ephemeral=False
        )

    @discord.ui.button(
        label="Tirer Maintenant",
        style=discord.ButtonStyle.success,
        custom_id="giveaway_draw"
    )
    async def draw_now(self, interaction: discord.Interaction, button: Button):
        doc = await giveaways_collection.find_one({"_id": self.data["_id"]})
        parts = doc.get("participants", [])
        if len(parts) < self.data["winners"]:
            return await interaction.response.send_message(
                "⚠️ Pas assez de participants.", ephemeral=True
            )
        winners = random.sample(parts, self.data["winners"])
        embed = interaction.message.embeds[0]
        embed.add_field(
            name="🎊 Gagnants",
            value=", ".join(f"<@{w}>" for w in winners),
            inline=False
        )
        await interaction.message.edit(embed=embed, view=None)
        await giveaways_collection.update_one(
            {"_id": self.data["_id"]},
            {"$set": {"winners_list": winners}}
        )
        await interaction.response.send_message("✅ Tirage effectué !", ephemeral=True)


class GiveawayCog(commands.Cog):
    """Gestion des giveaways avec modération."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="giveaway",
        description="Créer un nouveau giveaway"
    )
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def giveaway(self, interaction: discord.Interaction):
        """Lance le modal de création (visible seulement aux ban_members)."""
        await interaction.response.send_modal(GiveawayModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))
