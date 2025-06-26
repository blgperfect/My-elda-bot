# commands/admin/soutien.py

import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, RoleSelect, ChannelSelect, Modal, TextInput
from discord.http import Route

from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES, EMOJIS
from config.mongo import soutien_collection


class PhraseModal(Modal, title="Définir la phrase de soutien"):
    phrase = TextInput(
        label="Phrase à mettre dans la bio",
        placeholder="Entrez le texte exact",
        max_length=100,
    )

    def __init__(self, parent_view: "SoutienView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        # stocke la phrase et rafraîchit l’embed principal
        self.parent_view.phrase = self.phrase.value.strip()
        await self.parent_view.update_embed(interaction)
        

class SoutienView(View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=180)
        self.author     = author
        self.phrase     : str | None = None
        self.role_id    : int | None = None
        self.channel_id : int | None = None
        self.message    : discord.Message | None = None

    async def update_embed(self, interaction: discord.Interaction):
        """Reconstruit et édite l’embed principal."""
        embed = discord.Embed(
            title="Configuration Soutien",
            color=EMBED_COLOR,
            description=(
                f"**Phrase :** `{self.phrase or '❌ non définie'}`\n"
                f"**Rôle :** {f'<@&{self.role_id}>' if self.role_id else '❌ non défini'}\n"
                f"**Salon :** {f'<#{self.channel_id}>' if self.channel_id else '❌ non défini'}\n\n"
                "Quand tout est prêt, cliquez sur **Terminer**."
            )
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # active/désactive le bouton Terminer
        finish_btn: Button = next(b for b in self.children if b.custom_id == "finish")  # type: ignore
        finish_btn.disabled = not all((self.phrase, self.role_id, self.channel_id))

        if self.message:
            await self.message.edit(embed=embed, view=self)

        # répond à l’interaction (pour éviter timeouts)
        if interaction.response.is_done() is False:
            await interaction.response.defer()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(
                content="⏱️ Menu expiré. Relancez `/soutien` pour reconfigurer.",
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

        temp_view = View(timeout=60)
        select = RoleSelect(
            placeholder="🔍 Recherchez et sélectionnez un rôle…",
            min_values=1,
            max_values=1
        )

        async def callback_role(resp: discord.Interaction):
            self.role_id = select.values[0].id
            await self.update_embed(resp)
            await resp.delete_original_response()

        select.callback = callback_role
        temp_view.add_item(select)
        await interaction.response.send_message("Sélectionnez un rôle :", view=temp_view, ephemeral=True)

    @discord.ui.button(label="Sélectionner salon", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("BELL","🔔"), custom_id="channel")
    async def _channel(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)

        temp_view = View(timeout=60)
        select = ChannelSelect(
            placeholder="🔍 Recherchez et sélectionnez un salon…",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text]
        )

        async def callback_chan(resp: discord.Interaction):
            self.channel_id = select.values[0].id
            await self.update_embed(resp)
            await resp.delete_original_response()

        select.callback = callback_chan
        temp_view.add_item(select)
        await interaction.response.send_message("Sélectionnez un salon textuel :", view=temp_view, ephemeral=True)

    @discord.ui.button(label="✅ Terminer", style=discord.ButtonStyle.success,
                       custom_id="finish", disabled=True)
    async def _finish(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)

        # enregistre la config
        await soutien_collection.update_one(
            {"_id": interaction.guild_id},
            {"$set": {
                "phrase": self.phrase,
                "role_id": self.role_id,
                "channel_id": self.channel_id
            }},
            upsert=True
        )

        # annonce officielle
        chan = interaction.guild.get_channel(self.channel_id)
        if chan:
            emb = discord.Embed(
                title="🔔 Fonction Soutien activée",
                color=EMBED_COLOR,
                description=(
                    f"Bonjour à tous !\n"
                    f"Pour obtenir le rôle <@&{self.role_id}>, ajoutez dans votre bio :\n\n"
                    f"**{self.phrase}**"
                )
            )
            emb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await chan.send(embed=emb)

        # désactive le menu
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ Configuration enregistrée.", view=self)


class Soutien(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def fetch_bio(self, user: discord.User) -> str:
        route = Route("GET", "/users/{user_id}/profile", user_id=user.id)
        data = await self.bot.http.request(route)
        return data.get("bio", "") or ""

    @app_commands.command(name="soutien", description="Configure la fonctionnalité de soutien.")
    async def soutien(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            err = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                description=MESSAGES["NOT_OWNER"],
                color=EMBED_COLOR
            )
            err.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=err, ephemeral=True)

        view = SoutienView(interaction.user)
        embed = discord.Embed(
            title="⚙️ Configuration Soutien",
            color=EMBED_COLOR,
            description=(
                "1️⃣ Définissez la phrase à mettre dans la bio.\n"
                "2️⃣ Choisissez le rôle à attribuer.\n"
                "3️⃣ Sélectionnez le salon de notifications.\n\n"
                "Cliquez sur les boutons ci-dessous pour débuter.\n"
                "Vous avez 3 minutes."
            )
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if not member:
                continue

            cfg = await soutien_collection.find_one({"_id": guild.id})
            if not cfg:
                continue

            phrase  = cfg["phrase"]
            role    = guild.get_role(cfg["role_id"])
            chan    = guild.get_channel(cfg["channel_id"])
            if not role or not chan:
                continue

            before_bio = await self.fetch_bio(before)
            after_bio  = await self.fetch_bio(after)
            had = phrase in before_bio
            has = phrase in after_bio

            if not had and has:
                await member.add_roles(role, reason="Soutien activé")
                await chan.send(f"{EMOJIS.get('PARTY','🎉')} {member.mention} a activé le soutien ! Rôle attribué.")
            elif had and not has:
                await member.remove_roles(role, reason="Soutien désactivé")
                await chan.send(f"{EMOJIS.get('CROSS','✖️')} {member.mention} a désactivé le soutien ! Rôle retiré.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Soutien(bot))
