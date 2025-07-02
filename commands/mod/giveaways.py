import asyncio
import re
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput, View, ChannelSelect, Button

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
)
from config.mongo import giveaways_collection

# Regex pour custom emoji Discord <:name:id> ou <a:name:id>
_EMOJI_RE = re.compile(r'<(a?):(\w+):(\d+)>')

def parse_label_and_emoji(raw: str):
    m = _EMOJI_RE.search(raw)
    if not m:
        return raw, None
    animated, name, id_str = m.groups()
    pe = discord.PartialEmoji(name=name, id=int(id_str), animated=bool(animated))
    clean = _EMOJI_RE.sub("", raw).strip()
    return (clean or None), pe


def parse_duration(text: str) -> timedelta:
    unit = text[-1].lower()
    if unit not in ("m", "h", "d", "w"):
        raise ValueError("Unité invalide")
    val = int(text[:-1])
    return {
        "m": timedelta(minutes=val),
        "h": timedelta(hours=val),
        "d": timedelta(days=val),
        "w": timedelta(weeks=val),
    }[unit]


class GiveawayModal(Modal, title="📢 Lancer un Giveaway"):
    titre   = TextInput(label="Titre du giveaway", required=True)
    reward  = TextInput(label="Récompense", required=True)
    winners = TextInput(label="Nombre de gagnants", required=True, placeholder="ex: 1")
    duree   = TextInput(label="Durée (m,h,d,w)", required=True, placeholder="ex: 10m")

    async def on_submit(self, interaction: discord.Interaction):
        # Validation des inputs
        try:
            winners_count = int(self.winners.value)
            if winners_count < 1:
                raise ValueError()
        except ValueError:
            return await interaction.response.send_message(
                "❌ Le nombre de gagnants doit être un entier positif.", ephemeral=True
            )
        try:
            duration_delta = parse_duration(self.duree.value)
        except Exception:
            return await interaction.response.send_message(
                "❌ Durée invalide (ex: 10m, 2h, 1d, 1w).", ephemeral=True
            )

        data = {
            "title": self.titre.value,
            "reward": self.reward.value,
            "winners": winners_count,
            "duration": self.duree.value,
            "created_at": datetime.now(timezone.utc),
            "participants": []
        }

        # Demande du label
        await interaction.response.send_message(
            f"{interaction.user.mention}, écris le label pour le bouton (ou `skip` pour \"Participer\")."
        )
        prompt = await interaction.original_response()

        def check_label(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and not m.author.bot

        try:
            label_msg = await interaction.client.wait_for("message", check=check_label, timeout=60)
        except asyncio.TimeoutError:
            await prompt.delete()
            return await interaction.channel.send("⏱️ Temps écoulé.", delete_after=10)

        raw = label_msg.content.strip()
        data["button_label"] = "Participer" if raw.lower() == "skip" else raw
        await prompt.delete()
        await label_msg.delete()

        # Sélecteur de salon
        class ChannelSelectView(ChannelSelect):
            def __init__(self):
                super().__init__(
                    placeholder="Salon de publication…",
                    custom_id="giveaway_channel",
                    channel_types=[discord.ChannelType.text],
                    min_values=1, max_values=1
                )

            async def callback(self, select_inter: discord.Interaction):
                chan = select_inter.guild.get_channel(self.values[0].id)
                data["channel_id"] = chan.id

                end_time = data["created_at"] + duration_delta
                ts = int(end_time.timestamp())
                # Embed initial
                embed = discord.Embed(
                    title=data["title"],
                    description=(
                        f"Récompense : **{data['reward']}**\n"
                        f"Gagnants : **{data['winners']}**\n"
                        f"Participants : **0**\n"
                        f"Fin dans : <t:{ts}:R>"
                    ),
                    color=EMBED_COLOR,
                    timestamp=end_time
                )
                embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

                # Création de la view
                view = GiveawayView(data, end_time)
                msg = await chan.send(embed=embed, view=view)
                data["_id"] = msg.id
                await giveaways_collection.insert_one(data)
                await select_inter.response.edit_message(content=f"✅ Giveaway créé dans {chan.mention}!", view=None)

                # Auto-finish du giveaway
                async def finish_giveaway():
                    await asyncio.sleep(duration_delta.total_seconds())
                    parts = data["participants"]
                    if len(parts) < data["winners"]:
                        await chan.send("⚠️ Giveaway terminé, pas assez de participants.")
                        try:
                            await msg.edit(view=view.make_reroll_only())
                        except discord.NotFound:
                            pass
                        return
                    winners = random.sample(parts, data["winners"])
                    mentions = " ".join(f"<@{w}>" for w in winners)
                    await chan.send(f"🎊 {mentions}, félicitations !")
                    embed_fin = msg.embeds[0]
                    embed_fin.add_field(name="🎊 Gagnants", value=mentions, inline=False)
                    try:
                        await msg.edit(embed=embed_fin, view=view.make_reroll_only())
                    except discord.NotFound:
                        pass
                    await giveaways_collection.update_one(
                        {"_id": data["_id"]},
                        {"$set": {"winners_list": winners}}
                    )

                asyncio.create_task(finish_giveaway())

        # Envoi du select
        select_view = View(timeout=None)
        select_view.add_item(ChannelSelectView())
        await interaction.channel.send(f"{interaction.user.mention}, choisis le salon :", view=select_view)


class GiveawayView(View):
    def __init__(self, data: dict, end_time: datetime):
        super().__init__(timeout=None)
        self.data = data
        self.end_time = end_time
        # Bouton Participer
        raw = data.get("button_label", "Participer")
        label, emoji = parse_label_and_emoji(raw)
        part_btn = Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary, custom_id="giveaway_participate")
        part_btn.callback = self.participate
        self.add_item(part_btn)
        # Annuler
        cancel_btn = Button(label="Annuler", style=discord.ButtonStyle.danger, custom_id="giveaway_cancel")
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)
        # Reroll
        reroll_btn = Button(label="Reroll", style=discord.ButtonStyle.secondary, custom_id="giveaway_reroll")
        reroll_btn.callback = self.reroll
        self.add_item(reroll_btn)
        # Tirage immédiat
        draw_btn = Button(label="Tirer Maintenant", style=discord.ButtonStyle.success, custom_id="giveaway_draw")
        draw_btn.callback = self.draw_now
        self.add_item(draw_btn)

    def make_reroll_only(self) -> View:
        # On reprend GiveawayView pour conserver interaction_check
        view = GiveawayView(self.data, self.end_time)
        # Désactive tous les boutons sauf le reroll
        for item in view.children:
            item.disabled = (item.custom_id != "giveaway_reroll")
        return view

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        # Pour cancel, reroll et draw, il faut la permission ban_members
        if cid in ("giveaway_cancel", "giveaway_reroll", "giveaway_draw") and not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return False
        return True

    async def participate(self, interaction: discord.Interaction):
        uid = interaction.user.id
        parts = self.data["participants"]
        if uid in parts:
            parts.remove(uid)
            await interaction.response.send_message("❌ Participation retirée.", ephemeral=True)
        else:
            parts.append(uid)
            await interaction.response.send_message("✅ Participation ajoutée.", ephemeral=True)
        await giveaways_collection.update_one({"_id": self.data["_id"]}, {"$set": {"participants": parts}})
        # Mise à jour embed participants
        msg = interaction.message
        ts = int(self.end_time.timestamp())
        embed = msg.embeds[0]
        embed.description = (
            f"Récompense : **{self.data['reward']}**\n"
            f"Gagnants : **{self.data['winners']}**\n"
            f"Participants : **{len(parts)}**\n"
            f"Fin dans : <t:{ts}:R>"
        )
        await msg.edit(embed=embed)

    async def cancel(self, interaction: discord.Interaction):
        await interaction.message.delete()
        await giveaways_collection.delete_one({"_id": self.data["_id"]})
        await interaction.response.send_message("🚫 Giveaway annulé.", ephemeral=True)

    async def reroll(self, interaction: discord.Interaction):
        parts = self.data.get("participants", [])
        if not parts:
            return await interaction.response.send_message("⚠️ Aucun participant.", ephemeral=True)
        # Tirage
        winner = random.choice(parts)
        await interaction.response.send_message(f"🎉 <@{winner}>, tu as gagné !", ephemeral=False)
        # Enregistrer le reroll
        await giveaways_collection.update_one(
            {"_id": self.data["_id"]},
            {"$set": {
                "last_reroll": datetime.now(timezone.utc),
                "reroll_winner": winner
            }}
        )
        # Désactiver le bouton pour éviter le spam
        view = self.make_reroll_only()
        for btn in view.children:
            if btn.custom_id == "giveaway_reroll":
                btn.disabled = True
        await interaction.message.edit(view=view)

    async def draw_now(self, interaction: discord.Interaction):
        parts = self.data.get("participants", [])
        if len(parts) < self.data["winners"]:
            return await interaction.response.send_message("⚠️ Pas assez de participants.", ephemeral=True)
        winners = random.sample(parts, self.data["winners"])
        mentions = " ".join(f"<@{w}>" for w in winners)
        await interaction.channel.send(f"🎊 {mentions}, félicitations !")
        msg = interaction.message
        embed = msg.embeds[0]
        embed.add_field(name="🎊 Gagnants", value=mentions, inline=False)
        await msg.edit(embed=embed, view=self.make_reroll_only())
        await giveaways_collection.update_one({"_id": self.data["_id"]}, {"$set": {"winners_list": winners}})
        await interaction.response.send_message("✅ Tirage effectué.", ephemeral=True)


class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_expired.start()

    @tasks.loop(seconds=60)
    async def cleanup_expired(self):
        now = datetime.now(timezone.utc)
        async for gw in giveaways_collection.find({}):
            created = gw.get("created_at")
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            try:
                end = created + parse_duration(gw["duration"])
            except Exception:
                continue
            if end < now:
                await giveaways_collection.delete_one({"_id": gw["_id"]})

    @cleanup_expired.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="giveaway", description="Créer un nouveau giveaway")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def giveaway(self, interaction: discord.Interaction):
        await interaction.response.send_modal(GiveawayModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))
