# commands/admin/configurations/confess.py

import re
import datetime
import logging

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

from config.mongo import confession_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES

log = logging.getLogger("elda.confession")


def parse_label_and_emoji(raw: str):
    """
    Extrait du raw un emoji custom de forme <:name:id> ou <a:name:id>,
    retourne (label, PartialEmoji|None).
    """
    m = re.search(r'<(a?):(\w+):(\d+)>', raw)
    if not m:
        return raw, None
    animated, name, id_str = m.groups()
    pe = discord.PartialEmoji(name=name, id=int(id_str), animated=bool(animated))
    clean = re.sub(r'<a?:\w+:\d+>', '', raw).strip()
    return clean or None, pe


class ConfessionModal(Modal, title="🕯️ Confession Anonyme"):
    confession = TextInput(
        label="Ta confession",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        placeholder="Écris ta confession ici…"
    )

    def __init__(self, guild_id: int, member: discord.Member):
        super().__init__()
        self.guild_id = guild_id
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        # 1️⃣ On defer pour garder le token valide
        await interaction.response.defer(ephemeral=True)

        # 2️⃣ Charger la config
        cfg = await confession_collection.find_one({
            "kind": "config",
            "guild_id": self.guild_id
        })
        if not cfg:
            log.error(f"[Modal] Pas de config pour guild {self.guild_id}")
            return await interaction.followup.send(
                "⚠️ Configuration introuvable. Reconfigurez avec `/set_confess`.",
                ephemeral=True
            )

        # 3️⃣ Vérifier le blocage
        blocked = await confession_collection.find_one({
            "kind": "block",
            "guild_id": self.guild_id,
            "user_id": self.member.id
        })
        if blocked:
            return await interaction.followup.send(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        # 4️⃣ Incrémenter le compteur
        res = await confession_collection.find_one_and_update(
            {"kind": "config", "guild_id": self.guild_id},
            {"$inc": {"count": 1}},
            return_document=True
        )
        num = res.get("count", 1)

        # 5️⃣ Poster l’embed de la confession
        channel = interaction.guild.get_channel(cfg["channel_id"])
        if not channel:
            log.error(f"[Modal] Salon {cfg['channel_id']} introuvable en guild {self.guild_id}")
            return await interaction.followup.send(
                MESSAGES["CHANNEL_NOT_FOUND"], ephemeral=True
            )

        embed = discord.Embed(
            title=f"Confession #{num}",
            description=self.confession.value,
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        try:
            await channel.send(embed=embed)
        except Exception:
            log.exception("Erreur envoi embed confession")
            return await interaction.followup.send(
                MESSAGES["INTERNAL_ERROR"], ephemeral=True
            )

        # 6️⃣ Mettre à jour le panneau : suppression + ré-envoi
        try:
            if old_id := cfg.get("message_id"):
                old = await channel.fetch_message(old_id)
                await old.delete()
        except discord.NotFound:
            pass
        except Exception:
            log.exception("Erreur suppression ancien panneau")

        view = PanelView(self.guild_id, cfg["button_label"])
        panel = discord.Embed(
            title="Confession Anonyme !",
            description=f"Clique sur « {cfg['button_label']} » pour soumettre ta confession !",
            color=EMBED_COLOR
        )
        panel.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        sent = await channel.send(embed=panel, view=view)
        await confession_collection.update_one(
            {"kind": "config", "guild_id": self.guild_id},
            {"$set": {"message_id": sent.id}}
        )

        # 7️⃣ Ack à l’utilisateur
        await interaction.followup.send(
            MESSAGES["ACTION_SUCCESS"], ephemeral=True
        )


class PanelView(View):
    def __init__(self, guild_id: int, raw_label: str):
        super().__init__(timeout=None)
        label, emoji = parse_label_and_emoji(raw_label)
        custom_id = f"confess_button:{guild_id}"
        btn = Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=custom_id)
        btn.callback = self.on_confess_button
        self.add_item(btn)

    async def on_confess_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ConfessionModal(interaction.guild.id, interaction.user)
        )


class ConfessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="set_confess",
        description="Configure le salon et le bouton de confession."
    )
    @app_commands.describe(
        channel="Salon où poster le panneau de confession",
        button_label="Texte du bouton (emoji custom pris en charge)"
    )
    async def set_confess(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        button_label: str
    ):
        # Permission admin
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        # Upsert config (initialise count à 0 si nouvelle)
        await confession_collection.update_one(
            {"kind": "config", "guild_id": interaction.guild.id},
            {
                "$set": {
                    "channel_id":   channel.id,
                    "button_label": button_label
                },
                "$setOnInsert": {"count": 0}
            },
            upsert=True
        )

        # Envoi du panneau initial
        view = PanelView(interaction.guild.id, button_label)
        embed = discord.Embed(
            title="Confession Anonyme !",
            description=f"Clique sur « {button_label} » pour soumettre ta confession !",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        msg = await channel.send(embed=embed, view=view)

        # Sauvegarde du message_id
        await confession_collection.update_one(
            {"kind": "config", "guild_id": interaction.guild.id},
            {"$set": {"message_id": msg.id}}
        )

        await interaction.response.send_message(
            MESSAGES["MESSAGE_SENT"], ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionCog(bot))
