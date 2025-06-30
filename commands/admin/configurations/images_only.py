#Commande validé et terminé, cette commande sert a envoyé uniquement des images 
#dans des salon spécifique.

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, ChannelSelect
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import images_only_collection


class ImagesOnlyView(View):
    def __init__(self, author: discord.Member, guild: discord.Guild, existing: list[int]):
        super().__init__(timeout=180)
        self.author = author
        self.guild = guild
        self.existing = existing  # salons déjà configurés
        self.to_add: list[int] = []
        self.to_remove: list[int] = []

        # Sélecteur pour ajout (tous salons texte)
        self.add_select = ChannelSelect(
            placeholder="➕ Sélectionnez des salons à ajouter…",
            min_values=1,
            max_values=len(guild.text_channels),
            channel_types=[discord.ChannelType.text]
        )
        self.add_select.callback = self.on_add_select
        self.add_item(self.add_select)

        # Sélecteur pour retrait (tous salons texte, filtrage en callback)
        self.remove_select = ChannelSelect(
            placeholder="➖ Sélectionnez des salons à retirer…",
            min_values=1,
            max_values=len(guild.text_channels),
            channel_types=[discord.ChannelType.text]
        )
        self.remove_select.callback = self.on_remove_select
        self.add_item(self.remove_select)

        # Bouton confirmer ajout
        self.add_btn = Button(
            label="✅ Ajouter",
            style=discord.ButtonStyle.success,
            emoji=EMOJIS.get("PLUS", "➕"),
            disabled=True,
            custom_id="confirm_add_images_only"
        )
        self.add_btn.callback = self.on_add
        self.add_item(self.add_btn)

        # Bouton confirmer retrait
        self.remove_btn = Button(
            label="✅ Retirer",
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS.get("MINUS", "➖"),
            disabled=True,
            custom_id="confirm_remove_images_only"
        )
        self.remove_btn.callback = self.on_remove
        self.add_item(self.remove_btn)

        # Bouton réinitialiser tout
        self.clear_btn = Button(
            label="🗑️ Réinitialiser tout",
            style=discord.ButtonStyle.danger,
            custom_id="clear_images_only"
        )
        self.clear_btn.callback = self.on_clear
        self.add_item(self.clear_btn)

        self.message: discord.Message | None = None

    async def on_add_select(self, interaction: discord.Interaction):
        """Gérer la sélection pour ajout et activer le bouton."""
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        self.to_add = [c.id for c in self.add_select.values]
        self.add_btn.disabled = not bool(self.to_add)
        await self.update_embed(interaction)

    async def on_remove_select(self, interaction: discord.Interaction):
        """Gérer la sélection pour retrait et activer le bouton."""
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        # Ne garder que ceux déjà configurés
        self.to_remove = [c.id for c in self.remove_select.values if c.id in self.existing]
        self.remove_btn.disabled = not bool(self.to_remove)
        await self.update_embed(interaction)

    async def on_add(self, interaction: discord.Interaction):
        """Ajouter les salons sélectionnés à la configuration."""
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        new_list = sorted(set(self.existing) | set(self.to_add))
        try:
            await images_only_collection.update_one(
                {"_id": self.guild.id}, {"$set": {"channels": new_list}}, upsert=True
            )
        except:
            return await interaction.response.send_message("❌ Erreur base de données.", ephemeral=True)
        self.existing = new_list
        self.to_add = []
        self.add_btn.disabled = True
        await self.update_embed(interaction, title="✅ Ajout effectué")

    async def on_remove(self, interaction: discord.Interaction):
        """Retirer les salons sélectionnés de la configuration."""
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        new_list = [cid for cid in self.existing if cid not in self.to_remove]
        try:
            await images_only_collection.update_one(
                {"_id": self.guild.id}, {"$set": {"channels": new_list}}
            )
        except:
            return await interaction.response.send_message("❌ Erreur base de données.", ephemeral=True)
        self.existing = new_list
        self.to_remove = []
        self.remove_btn.disabled = True
        await self.update_embed(interaction, title="✅ Retrait effectué")

    async def on_clear(self, interaction: discord.Interaction):
        """Réinitialiser complètement la configuration."""
        if interaction.user != self.author:
            return await interaction.response.send_message(MESSAGES["PERMISSION_ERROR"], ephemeral=True)
        try:
            await images_only_collection.delete_one({"_id": self.guild.id})
        except:
            return await interaction.response.send_message("❌ Erreur base de données.", ephemeral=True)
        self.existing = []
        self.to_add = []
        self.to_remove = []
        self.add_btn.disabled = True
        self.remove_btn.disabled = True
        await self.update_embed(interaction, title="🗑️ Tout réinitialisé")

    async def update_embed(self, interaction: discord.Interaction, title: str = "📷 Configuration Images-Only"):
        """Met à jour l'embed avec l'état actuel, ajout et retrait."""
        lines = ["**Salons configurés :**"]
        if self.existing:
            lines += [f"- {self.guild.get_channel(cid).mention}" for cid in self.existing]
        else:
            lines.append("Aucun")
        if self.to_add:
            lines.append("\n**À ajouter :**")
            lines += [f"- {self.guild.get_channel(cid).mention}" for cid in self.to_add]
        if self.to_remove:
            lines.append("\n**À retirer :**")
            lines += [f"- {self.guild.get_channel(cid).mention}" for cid in self.to_remove]
        embed = discord.Embed(title=title, description="\n".join(lines), color=EMBED_COLOR)
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=embed, view=self)


class ImagesOnly(commands.Cog):
    """Cog pour configurer et appliquer le mode images-only."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_listener(self.on_message, "on_message")
        bot.add_listener(self.on_guild_remove, "on_guild_remove")

    @app_commands.command(
        name="imagesonly",
        description="Gérer la configuration images-only (ajout/retrait/réinitialisation)."
    )
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def imagesonly(self, interaction: discord.Interaction):
        """Afficher le menu interactif de gestion images-only."""
        try:
            config = await images_only_collection.find_one({"_id": interaction.guild.id})
            existing = config.get("channels", []) if config else []
        except:
            existing = []
        lines = ["**Salons configurés :**"]
        if existing:
            lines += [f"- {interaction.guild.get_channel(cid).mention}" for cid in existing]
        else:
            lines.append("Aucun")
        embed = discord.Embed(title="🔧 Configuration Images-Only", description="\n".join(lines), color=EMBED_COLOR)
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = ImagesOnlyView(interaction.user, interaction.guild, existing)
        # initialement aucun ajout/retrait
        view.add_btn.disabled = True
        view.remove_btn.disabled = True
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @imagesonly.error
    async def imagesonly_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            embed = discord.Embed(
                title=MESSAGES["PERMISSION_ERROR"],
                description="Vous devez avoir la permission **Gérer les messages** pour utiliser cette commande.",
                color=EMBED_COLOR
            )
        else:
            embed = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                color=EMBED_COLOR
            )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        perms = message.author.guild_permissions
        if perms.administrator or perms.manage_messages:
            return
        try:
            config = await images_only_collection.find_one({"_id": message.guild.id})
        except:
            return
        if not config or message.channel.id not in config.get("channels", []):
            return
        bot_perms = message.channel.permissions_for(message.guild.me)
        if not bot_perms.manage_messages:
            return
        if not message.attachments and not any(e.image or e.thumbnail for e in message.embeds):
            try:
                await message.delete()
            except:
                pass
            warn = discord.Embed(
                description="🚫 Seules les images sont autorisées dans ce salon. Votre message a été supprimé.",
                color=EMBED_COLOR
            )
            warn.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await message.channel.send(f"{message.author.mention}", embed=warn, delete_after=5)

    async def on_guild_remove(self, guild: discord.Guild):
        try:
            await images_only_collection.delete_one({"_id": guild.id})
        except:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ImagesOnly(bot))
