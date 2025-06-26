# commands/soutien.py
import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
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
        self.parent_view.phrase = self.phrase.value.strip()
        await self.parent_view.update_embed(interaction)


class RoleSelect(Select):
    def __init__(self, parent_view: "SoutienView", roles: list[discord.Role]):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in roles
        ]
        super().__init__(
            placeholder="Choisissez un rôle…",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.role_id = int(self.values[0])
        await self.parent_view.update_embed(interaction)


class ChannelSelect(Select):
    def __init__(self, parent_view: "SoutienView", channels: list[discord.TextChannel]):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=ch.name, value=str(ch.id))
            for ch in channels
        ]
        super().__init__(
            placeholder="Choisissez un salon…",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.channel_id = int(self.values[0])
        await self.parent_view.update_embed(interaction)


class SoutienView(View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=180)
        self.author     = author
        self.phrase     : str | None = None
        self.role_id    : int | None = None
        self.channel_id : int | None = None

    async def update_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Configuration Soutien",
            color=EMBED_COLOR,
            description=(
                f"**Phrase :** `{self.phrase or '❌ non définie'}`\n"
                f"**Rôle :** {f'<@&{self.role_id}>' if self.role_id else '❌ non défini'}\n"
                f"**Salon :** {f'<#{self.channel_id}>' if self.channel_id else '❌ non défini'}\n\n"
                "Cliquez sur **Terminer** quand tout est configuré."
            )
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        finish_btn: Button = next(b for b in self.children if b.custom_id == "finish")  # type: ignore
        finish_btn.disabled = not all((self.phrase, self.role_id, self.channel_id))
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(
                content="⏱️ Menu expiré. Relancez `/soutien` pour reconfigurer.",
                view=self
            )
        except:
            pass

    @discord.ui.button(label="Modifier phrase", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("PENCIL","🖋️"), custom_id="phrase")
    async def _phrase(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )
        await interaction.response.send_modal(PhraseModal(self))

    @discord.ui.button(label="Sélectionner rôle", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("STAR","⭐"), custom_id="role")
    async def _role(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )
        # Filtre des rôles valides
        roles = [
            r for r in interaction.guild.roles
            if not r.is_default() and r < interaction.guild.me.top_role
        ]
        if not roles:
            return await interaction.response.send_message(
                f"{EMOJIS.get('WARNING','⚠️')} Aucun rôle disponible à sélectionner.",
                ephemeral=True
            )

        temp_view = View(timeout=60)
        temp_view.add_item(RoleSelect(self, roles))
        await interaction.response.send_message(
            "Sélectionnez un rôle :", view=temp_view, ephemeral=True
        )

    @discord.ui.button(label="Sélectionner salon", style=discord.ButtonStyle.primary,
                       emoji=EMOJIS.get("BELL","🔔"), custom_id="channel")
    async def _channel(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )
        channels = interaction.guild.text_channels
        if not channels:
            return await interaction.response.send_message(
                f"{EMOJIS.get('WARNING','⚠️')} Aucun salon textuel trouvé.",
                ephemeral=True
            )

        temp_view = View(timeout=60)
        temp_view.add_item(ChannelSelect(self, channels))
        await interaction.response.send_message(
            "Sélectionnez un salon :", view=temp_view, ephemeral=True
        )

    @discord.ui.button(label="✅ Terminer", style=discord.ButtonStyle.success,
                       custom_id="finish", disabled=True)
    async def _finish(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )
        # Upsert en base
        await soutien_collection.update_one(
            {"_id": interaction.guild_id},
            {"$set": {
                "phrase": self.phrase,
                "role_id": self.role_id,
                "channel_id": self.channel_id
            }},
            upsert=True
        )
        # Envoi de l’annonce
        chan = interaction.guild.get_channel(self.channel_id)
        if chan:
            ann = discord.Embed(
                title="🔔 Fonction Soutien activée",
                color=EMBED_COLOR,
                description=(
                    f"Bonjour à tous !\n"
                    f"Pour obtenir le rôle <@&{self.role_id}>, ajoutez dans votre bio :\n\n"
                    f"**{self.phrase}**"
                )
            )
            ann.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await chan.send(embed=ann)

        # Ferme et désactive le menu
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content="✅ Configuration enregistrée.", view=self
        )


class Soutien(commands.Cog):
    """Cog pour la gestion de la fonctionnalité Soutien."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def fetch_bio(self, user: discord.User) -> str:
        route = Route("GET", "/users/{user_id}/profile", user_id=user.id)
        data = await self.bot.http.request(route)
        return data.get("bio", "") or ""

    @app_commands.command(
        name="soutien",
        description="Configure la fonctionnalité de soutien des membres."
    )
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
                "Vous avez 3 minutes avant expiration."
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
                await chan.send(f"{EMOJIS.get('PARTY','🎉')} {member.mention} a activé le soutien ! Rôle {role.mention} attribué.")
            elif had and not has:
                await member.remove_roles(role, reason="Soutien désactivé")
                await chan.send(f"{EMOJIS.get('CROSS','✖️')} {member.mention} a désactivé le soutien. Rôle {role.mention} retiré.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Soutien(bot))
