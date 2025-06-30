import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, ChannelSelect
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES, EMOJIS
from config.mongo import images_only_collection


class ImagesOnlyView(View):
    def __init__(self, author: discord.Member, guild: discord.Guild):
        super().__init__(timeout=180)
        self.author = author
        self.guild = guild
        self.selected: list[int] = []

        # Sélecteur multi‐salons texte
        sel = ChannelSelect(
            placeholder="🔍 Sélectionnez un ou plusieurs salons…",
            min_values=1,
            max_values=len(guild.text_channels),
            channel_types=[discord.ChannelType.text]
        )
        sel.callback = self.select_channels
        self.add_item(sel)

        # Bouton de confirmation
        self.finish_btn = Button(
            label="✅ Terminer",
            style=discord.ButtonStyle.success,
            emoji=EMOJIS.get("CHECK", "✔️"),
            disabled=True,
            custom_id="finish_images_only"
        )
        self.finish_btn.callback = self.finish
        self.add_item(self.finish_btn)

        self.message: discord.Message | None = None

    async def select_channels(self, interaction: discord.Interaction):
        """Gérer la sélection de salons et afficher la preview."""
        if interaction.user != self.author:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        sel = next(i for i in self.children if isinstance(i, ChannelSelect))  # type: ignore
        self.selected = [c.id for c in sel.values]  # type: ignore

        channels_list = "\n".join(
            f"- {self.guild.get_channel(cid).mention}" for cid in self.selected
        )
        embed = discord.Embed(
            title="📷 Salons « images only »",
            description=(
                "Cette commande sert à autoriser **seulement les images** dans les salons choisis.\n\n"
                f"{channels_list}"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        self.finish_btn.disabled = False
        await interaction.response.edit_message(embed=embed, view=self)

    async def finish(self, interaction: discord.Interaction):
        """Terminer la configuration : sauvegarde en base et confirmation."""
        if interaction.user != self.author:
            return await interaction.response.send_message(
                MESSAGES["PERMISSION_ERROR"], ephemeral=True
            )

        # Tentative de mise à jour en base MongoDB
        try:
            await images_only_collection.update_one(
                {"_id": self.guild.id},
                {"$set": {"channels": self.selected}},
                upsert=True
            )
        except Exception:
            # Erreur BD : message explicite
            embed_err = discord.Embed(
                title=MESSAGES["INTERNAL_ERROR"],
                description="❌ Impossible de sauvegarder la configuration en base de données. Réessayez plus tard.",
                color=EMBED_COLOR
            )
            embed_err.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed_err, ephemeral=True)

        # Confirmation
        embed = discord.Embed(
            description=MESSAGES["ACTION_SUCCESS"],
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Verrouille la vue
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)


class ImagesOnly(commands.Cog):
    """Cog pour configurer et appliquer le mode images-only."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_listener(self.on_message, "on_message")
        bot.add_listener(self.on_guild_remove, "on_guild_remove")

    @app_commands.command(
        name="imagesonly",
        description="Configure les salons où seuls les messages avec images sont autorisés."
    )
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def imagesonly(self, interaction: discord.Interaction):
        """Démarrer la configuration interactive images-only."""
        embed = discord.Embed(
            title="🔧 Configuration Images-Only",
            description="Sélectionnez ci-dessous les salons dans lesquels **seules les images** sont autorisées.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        view = ImagesOnlyView(interaction.user, interaction.guild)  # type: ignore
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @imagesonly.error
    async def imagesonly_error(self, interaction: discord.Interaction, error):
        """Gestion des erreurs de la commande /imagesonly."""
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
        """Appliquer la règle images-only aux nouveaux messages."""
        if message.author.bot or message.guild is None:
            return
        if message.author.guild_permissions.administrator:
            return

        try:
            config = await images_only_collection.find_one({"_id": message.guild.id})
        except Exception:
            return  # En cas d'erreur BD, on n'interfère pas

        if not config or message.channel.id not in config.get("channels", []):
            return

        has_attachment = bool(message.attachments)
        has_embed_image = any(e.image or e.thumbnail for e in message.embeds)
        if has_attachment or has_embed_image:
            return

        try:
            await message.delete()
        except Exception:
            pass

        warn = discord.Embed(
            description="🚫 Seules les images sont autorisées dans ce salon. Votre message a été supprimé.",
            color=EMBED_COLOR
        )
        warn.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await message.channel.send(f"{message.author.mention}", embed=warn, delete_after=5)

    async def on_guild_remove(self, guild: discord.Guild):
        """Supprime la config images-only si le bot est expulsé."""
        try:
            await images_only_collection.delete_one({"_id": guild.id})
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ImagesOnly(bot))
