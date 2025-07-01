import discord
from discord.ext import commands
from discord import app_commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

VIEW_TIMEOUT = 900  # 15 minutes

class EmbedBuilderView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, destination: discord.TextChannel):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.interaction = interaction
        self.destination = destination
        self.embed_data = {
            "title": None,
            "description": None,
            "color": EMBED_COLOR,
            "thumbnail": None,
            "image": None,
            "footer_text": EMBED_FOOTER_TEXT,
            "footer_icon_url": EMBED_FOOTER_ICON_URL,
            "fields": []
        }

    def build_embed(self) -> discord.Embed:
        e = discord.Embed(color=self.embed_data["color"])
        if self.embed_data["title"]:
            e.title = self.embed_data["title"]
        if self.embed_data["description"]:
            e.description = self.embed_data["description"]
        for name, value, inline in self.embed_data["fields"]:
            e.add_field(name=name, value=value, inline=inline)
        if self.embed_data["thumbnail"]:
            e.set_thumbnail(url=self.embed_data["thumbnail"])
        if self.embed_data["image"]:
            e.set_image(url=self.embed_data["image"])
        e.set_footer(text=self.embed_data["footer_text"], icon_url=self.embed_data["footer_icon_url"])
        return e

    async def update_message(self, inter: discord.Interaction):
        await inter.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.interaction.edit_original_response(content="⏱️ Le menu a expiré après 15 minutes.", view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Envoyer", style=discord.ButtonStyle.success)
    async def send_button(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer()
        # Envoi de l'embed
        await self.destination.send(embed=self.build_embed())
        try:
            await inter.edit_original_response(content="✅ Embed envoyé.", embed=None, view=None)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Titre", style=discord.ButtonStyle.primary)
    async def edit_title(self, inter: discord.Interaction, button: discord.ui.Button):
        class TitleModal(discord.ui.Modal, title="Modifier le titre"):
            title_input = discord.ui.TextInput(label="Titre", required=False, max_length=256)
            def __init__(self, parent: EmbedBuilderView):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                self.parent.embed_data["title"] = self.title_input.value or None
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(TitleModal(self))

    @discord.ui.button(label="Description", style=discord.ButtonStyle.primary)
    async def edit_description(self, inter: discord.Interaction, button: discord.ui.Button):
        class DescModal(discord.ui.Modal, title="Modifier la description"):
            desc_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=False)
            def __init__(self, parent: EmbedBuilderView):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                self.parent.embed_data["description"] = self.desc_input.value or None
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(DescModal(self))

    @discord.ui.button(label="Ajouter champ", style=discord.ButtonStyle.secondary)
    async def edit_field(self, inter: discord.Interaction, button: discord.ui.Button):
        class FieldModal(discord.ui.Modal, title="Ajouter un champ"):
            name = discord.ui.TextInput(label="Nom du champ", required=True)
            value = discord.ui.TextInput(label="Valeur du champ", style=discord.TextStyle.paragraph, required=True)
            inline = discord.ui.TextInput(label="Inline (True/False)", required=True)
            def __init__(self, parent: EmbedBuilderView):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                inline_bool = self.inline.value.lower() in ("true", "1", "yes", "y")
                self.parent.embed_data["fields"].append((self.name.value, self.value.value, inline_bool))
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(FieldModal(self))

    @discord.ui.button(label="Couleur (hex)", style=discord.ButtonStyle.secondary)
    async def edit_color(self, inter: discord.Interaction, button: discord.ui.Button):
        class ColorModal(discord.ui.Modal, title="Modifier la couleur"):
            color_input = discord.ui.TextInput(label="Hex (ex : #FF0000)", required=True, max_length=7)
            def __init__(self, parent: EmbedBuilderView):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                raw = self.color_input.value.strip().lstrip("#")
                try:
                    self.parent.embed_data["color"] = int(raw, 16)
                except ValueError:
                    return await modal_interaction.response.send_message("Hex invalide.", ephemeral=True)
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(ColorModal(self))

    @discord.ui.button(label="Vignette URL", style=discord.ButtonStyle.secondary)
    async def edit_thumbnail(self, inter: discord.Interaction, button: discord.ui.Button):
        class ThumbModal(discord.ui.Modal, title="URL de la vignette"):
            url_input = discord.ui.TextInput(label="URL", required=False)
            def __init__(self, parent: EmbedBuilderView):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                url = self.url_input.value.strip()
                if url and not url.startswith(("http://", "https://")):
                    return await modal_interaction.response.send_message("URL invalide.", ephemeral=True)
                self.parent.embed_data["thumbnail"] = url or None
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(ThumbModal(self))

    @discord.ui.button(label="Image URL", style=discord.ButtonStyle.secondary)
    async def edit_image(self, inter: discord.Interaction, button: discord.ui.Button):
        class ImageModal(discord.ui.Modal, title="URL de l'image"):
            url_input = discord.ui.TextInput(label="URL", required=False)
            def __init__(self, parent: EmbedBuilderView):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                url = self.url_input.value.strip()
                if url and not url.startswith(("http://", "https://")):
                    return await modal_interaction.response.send_message("URL invalide.", ephemeral=True)
                self.parent.embed_data["image"] = url or None
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(ImageModal(self))

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.secondary)
    async def edit_footer(self, inter: discord.Interaction, button: discord.ui.Button):
        class FooterModal(discord.ui.Modal, title="Modifier le footer"):
            text_input = discord.ui.TextInput(label="Footer", required=False, max_length=2048)
            def __init__(self, parent: EmbedBuilderView):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                self.parent.embed_data["footer_text"] = self.text_input.value or None
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(FooterModal(self))

    @discord.ui.button(label="Tout réinitialiser", style=discord.ButtonStyle.danger)
    async def clear_all(self, inter: discord.Interaction, button: discord.ui.Button):
        self.embed_data.update({
            "title": None,
            "description": None,
            "color": EMBED_COLOR,
            "thumbnail": None,
            "image": None,
            "footer_text": EMBED_FOOTER_TEXT,
            "fields": []
        })
        await self.update_message(inter)

class EmbedCog(commands.Cog):
    """Cog pour création rapide des embeds sans persistance."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="make_embed", description="Créer un embed personnalisé.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def make_embed(self, interaction: discord.Interaction, channel: discord.TextChannel):
        view = EmbedBuilderView(interaction, channel)
        await interaction.response.send_message(
            content="Ce menu expirera dans 15 minutes.",
            embed=view.build_embed(),
            view=view
        )

    @make_embed.error
    async def perm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("🔒 Vous devez être administrateur.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot))
