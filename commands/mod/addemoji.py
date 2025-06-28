# commands/mod/addemoji.py

import re
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

class RenameEmojiModal(discord.ui.Modal, title="Renommer l'emoji"):
    new_name = discord.ui.TextInput(
        label="Nouveau nom de l'emoji",
        placeholder="Entrez le nouveau nom (lettres, chiffres, underscore)",
        max_length=32
    )

    def __init__(self, emoji: discord.Emoji):
        super().__init__()
        self.emoji = emoji

    async def on_submit(self, interaction: discord.Interaction):
        name = self.new_name.value.strip()
        # Validation du format
        if not re.match(r'^[A-Za-z0-9_]+$', name):
            return await interaction.response.send_message(
                "❌ Nom invalide : ne peut contenir que lettres, chiffres et underscore (pas d'espaces ni de caractères spéciaux).",
                ephemeral=True
            )

        # Tentative de renommage
        try:
            await self.emoji.edit(name=name)
        except discord.HTTPException as e:
            return await interaction.response.send_message(
                f"❌ Impossible de renommer l'emoji : {e}",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ Emoji renommé en `{name}`.",
            ephemeral=True
        )

class ChangeNameView(discord.ui.View):
    def __init__(self, emoji: discord.Emoji, *, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.emoji = emoji

    @discord.ui.button(label="Changer le nom de l'emoji", style=discord.ButtonStyle.secondary)
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_emojis:
            return await interaction.response.send_message(
                "🚫 Vous n'avez pas la permission de gérer les emojis.",
                ephemeral=True
            )
        await interaction.response.send_modal(RenameEmojiModal(self.emoji))

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)

class EmojiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="addemoji",
        description="Petit voleur va colle moi ton emojis."
    )
    @app_commands.describe(
        emoji="Un emoji personnalisé (ex : <:monemoji:123456789012345678>)"
    )
    @app_commands.checks.has_permissions(manage_emojis=True)
    async def addemoji(self, interaction: discord.Interaction, emoji: str):
        await interaction.response.defer()

        partial = discord.PartialEmoji.from_str(emoji)
        if partial.id is None:
            return await interaction.followup.send(
                "❌ Veuillez fournir un emoji personnalisé valide.",
                ephemeral=True
            )

        try:
            url = str(partial.url)
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    image_bytes = await resp.read()
        except Exception as e:
            return await interaction.followup.send(
                f"⚠️ Impossible de récupérer l'image de l'emoji : {e}",
                ephemeral=True
            )

        try:
            new_emoji = await interaction.guild.create_custom_emoji(
                name=partial.name,
                image=image_bytes,
                reason=f"Ajouté par {interaction.user}"
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "🚫 Je n'ai pas la permission de gérer les emojis.",
                ephemeral=True
            )
        except Exception as e:
            return await interaction.followup.send(
                f"⚠️ Erreur lors de la création de l'emoji : {e}",
                ephemeral=True
            )

        embed = discord.Embed(
            title="✅ Emoji ajouté !",
            description=(
                f"Je viens de t'ajouter un emoji sur **{interaction.guild.name}** : {new_emoji}\n\n"
                f"Nom actuel de l'emoji : `{new_emoji.name}`"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.set_image(url=str(new_emoji.url))

        view = ChangeNameView(new_emoji)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message

    @addemoji.error
    async def addemoji_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 Vous n'avez pas la permission `Gérer les emojis` pour utiliser cette commande.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Une erreur est survenue : {error}",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiCog(bot))
