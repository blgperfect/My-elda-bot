# commands/admin/soutien.py

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, RoleSelect, ChannelSelect
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES, EMOJIS
from config.mongo import soutien_collection


class PhraseModal(Modal, title="Définir la phrase de soutien"):
    phrase = TextInput(
        label="Phrase à mettre dans le statut personnalisé",
        placeholder="Entrez le texte exact",
        max_length=100,
    )

    def __init__(self, parent_view: "SoutienView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.phrase = self.phrase.value.strip()
        await self.parent_view.update_embed(interaction)


class SoutienView(View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=180)
        self.author          = author
        self.phrase          : str | None = None
        self.role_id         : int | None = None
        self.announce_ch_id  : int | None = None
        self.log_enabled     : bool        = False
        self.log_ch_id       : int | None = None
        self.message         : discord.Message | None = None

    async def update_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ Configuration Soutien",
            color=EMBED_COLOR,
            description=(
                f"**Phrase :** `{self.phrase or '❌ non définie'}`\n"
                f"**Rôle :** {f'<@&{self.role_id}>' if self.role_id else '❌ non défini'}\n"
                f"**Salon annonce :** {f'<#{self.announce_ch_id}>' if self.announce_ch_id else '❌ non défini'}\n"
                f"**Salon logs :** {f'<#{self.log_ch_id}>' if self.log_enabled and self.log_ch_id else '❌ désactivé'}\n\n"
                "Quand tout est prêt, cliquez sur **Terminer**."
            )
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # bouton Terminer
        finish = next(b for b in self.children if b.custom_id == "finish")  # type: ignore
        finish.disabled = not all((self.phrase, self.role_id, self.announce_ch_id))

        # bouton toggle logs
        toggle = next(b for b in self.children if b.custom_id == "toggle_logs")  # type: ignore
        log_btn = next(b for b in self.children if b.custom_id == "log_channel")   # type: ignore

        if self.log_enabled:
            toggle.label = "Désactiver logs"
            toggle.style = discord.ButtonStyle.danger
            log_btn.disabled = False
        else:
            toggle.label = "Activer logs"
            toggle.style = discord.ButtonStyle.secondary
            log_btn.disabled = True
            self.log_ch_id = None

        if self.message:
            await self.message.edit(embed=embed, view=self)

        if not interaction.response.is_done():
            await interaction.response.defer()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(
                content="⏱️ Menu expiré. Relancez `/soutien`.",
                view=self
            )

    @discord.ui.button(label="Modifier phrase", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("PENCIL","🖋️"), custom_id="phrase")
    async def _phrase(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        await interaction.response.send_modal(PhraseModal(self))

    @discord.ui.button(label="Sélectionner rôle", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("STAR","⭐"), custom_id="role")
    async def _role(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        temp = View(timeout=60)
        sel  = RoleSelect(placeholder="🔍 Sélectionnez un rôle…", min_values=1, max_values=1)
        async def cb(resp: discord.Interaction):
            self.role_id = sel.values[0].id
            await self.update_embed(resp)
            await resp.delete_original_response()
        sel.callback = cb
        temp.add_item(sel)
        await interaction.response.send_message("Choisissez le rôle :", view=temp, ephemeral=True)

    @discord.ui.button(label="Sélectionner salon annonce", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("BELL","🔔"), custom_id="channel")
    async def _channel(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        temp = View(timeout=60)
        sel  = ChannelSelect(placeholder="🔍 Salon d’annonce…", min_values=1, max_values=1,
                             channel_types=[discord.ChannelType.text])
        async def cb(resp: discord.Interaction):
            self.announce_ch_id = sel.values[0].id
            await self.update_embed(resp)
            await resp.delete_original_response()
        sel.callback = cb
        temp.add_item(sel)
        await interaction.response.send_message("Choisissez le salon d’annonce :", view=temp, ephemeral=True)

    @discord.ui.button(label="Activer logs", style=discord.ButtonStyle.secondary,
                       emoji=EMOJIS.get("LOG","📝"), custom_id="toggle_logs")
    async def _toggle_logs(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        self.log_enabled = not self.log_enabled
        await self.update_embed(interaction)

    @discord.ui.button(label="Sélectionner salon logs", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("BELL","🔔"), custom_id="log_channel", disabled=True)
    async def _log_channel(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        temp = View(timeout=60)
        sel  = ChannelSelect(placeholder="🔍 Salon de logs…", min_values=1, max_values=1,
                             channel_types=[discord.ChannelType.text])
        async def cb(resp: discord.Interaction):
            self.log_ch_id = sel.values[0].id
            await self.update_embed(resp)
            await resp.delete_original_response()
        sel.callback = cb
        temp.add_item(sel)
        await interaction.response.send_message("Choisissez le salon de logs :", view=temp, ephemeral=True)

    @discord.ui.button(label="✅ Terminer", style=discord.ButtonStyle.success,
                       custom_id="finish", disabled=True)
    async def _finish(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)

        # Sauvegarde en base
        await soutien_collection.update_one(
            {"_id": interaction.guild_id},
            {"$set": {
                "phrase": self.phrase,
                "role_id": self.role_id,
                "announce_ch_id": self.announce_ch_id,
                "log_enabled": self.log_enabled,
                "log_ch_id": self.log_ch_id if self.log_enabled else None
            }},
            upsert=True
        )

        # **Embed de confirmation** → toujours dans announce_ch_id
        chan = interaction.guild.get_channel(self.announce_ch_id)
        if chan:
            emb = discord.Embed(
                title="🔔 Soutien activé",
                color=EMBED_COLOR,
                description=(
                    f"Pour recevoir le rôle <@&{self.role_id}>, définissez ce texte dans votre statut personnalisé :\n\n"
                    f"**{self.phrase}**"
                )
            )
            emb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await chan.send(embed=emb)

        # Disable de tous les boutons
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(content="✅ Configuration enregistrée.", view=self)


class Soutien(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="soutien", description="Configure la fonctionnalité de soutien.")
    async def soutien(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            err = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                description="Vous devez être administrateur pour configurer.",
                color=EMBED_COLOR
            )
            err.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=err, ephemeral=True)

        view  = SoutienView(interaction.user)
        embed = discord.Embed(
            title="⚙️ Configuration Soutien",
            description=(
                "1️⃣ Définissez la phrase (pour le statut personnalisé).\n"
                "2️⃣ Choisissez le rôle.\n"
                "3️⃣ Sélectionnez le salon d’annonce.\n"
                "4️⃣ (Optionnel) Activez et choisissez un salon de logs (pour les messages d’activation/désactivation).\n\n"
                "Vous avez 3 minutes."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Soutien(bot))
