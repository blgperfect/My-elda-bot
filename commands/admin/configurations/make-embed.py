import discord
from discord.ext import commands
from discord import app_commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

class EmbedBuilderView(discord.ui.View):
    def __init__(self, destination: discord.TextChannel):
        super().__init__(timeout=300)
        self.destination = destination
        self.embed_data = {
            "title": None,
            "description": None,
            "color": EMBED_COLOR,
            "thumbnail": None,
            "image": None,
            "footer_text": EMBED_FOOTER_TEXT,
            "footer_icon_url": EMBED_FOOTER_ICON_URL,
            "fields": []  # list of (name, value, inline)
        }

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(color=self.embed_data["color"])
        if self.embed_data["title"]:
            embed.title = self.embed_data["title"]
        if self.embed_data["description"]:
            embed.description = self.embed_data["description"]
        for name, value, inline in self.embed_data["fields"]:
            embed.add_field(name=name, value=value, inline=inline)
        if self.embed_data["thumbnail"]:
            embed.set_thumbnail(url=self.embed_data["thumbnail"])
        if self.embed_data["image"]:
            embed.set_image(url=self.embed_data["image"])
        embed.set_footer(text=self.embed_data["footer_text"], icon_url=self.embed_data["footer_icon_url"])
        return embed

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Edit Title", style=discord.ButtonStyle.primary)
    async def edit_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        class TitleModal(discord.ui.Modal, title="Edit Embed Title"):
            title_input = discord.ui.TextInput(label="Title", placeholder="Enter embed title", required=False, max_length=256)
            def __init__(self, parent_view: EmbedBuilderView):
                super().__init__()
                self.parent_view = parent_view
            async def on_submit(self, modal_interaction: discord.Interaction):
                self.parent_view.embed_data["title"] = self.title_input.value or None
                await self.parent_view.update_message(modal_interaction)
        await interaction.response.send_modal(TitleModal(self))

    @discord.ui.button(label="Edit Description", style=discord.ButtonStyle.primary)
    async def edit_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        class DescModal(discord.ui.Modal, title="Edit Embed Description"):
            desc_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=False)
            def __init__(self, parent_view: EmbedBuilderView):
                super().__init__()
                self.parent_view = parent_view
            async def on_submit(self, modal_interaction: discord.Interaction):
                self.parent_view.embed_data["description"] = self.desc_input.value or None
                await self.parent_view.update_message(modal_interaction)
        await interaction.response.send_modal(DescModal(self))

    @discord.ui.button(label="Edit Color (Hex)", style=discord.ButtonStyle.secondary)
    async def edit_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ColorModal(discord.ui.Modal, title="Edit Embed Color"):
            color_input = discord.ui.TextInput(label="Hex Color (e.g. #FF0000)", placeholder="#", required=True, max_length=7)
            def __init__(self, parent_view: EmbedBuilderView):
                super().__init__()
                self.parent_view = parent_view
            async def on_submit(self, modal_interaction: discord.Interaction):
                raw = self.color_input.value.strip().lstrip('#')
                try:
                    self.parent_view.embed_data["color"] = int(raw, 16)
                except ValueError:
                    await modal_interaction.response.send_message("Invalid hex color.", ephemeral=True)
                    return
                await self.parent_view.update_message(modal_interaction)
        await interaction.response.send_modal(ColorModal(self))

    @discord.ui.button(label="Set Thumbnail URL", style=discord.ButtonStyle.secondary)
    async def edit_thumbnail(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ThumbModal(discord.ui.Modal, title="Set Thumbnail URL"):
            url_input = discord.ui.TextInput(label="Thumbnail URL", placeholder="https://...", required=False)
            def __init__(self, parent_view: EmbedBuilderView):
                super().__init__()
                self.parent_view = parent_view
            async def on_submit(self, modal_interaction: discord.Interaction):
                url = self.url_input.value.strip()
                if url and not url.startswith(('http://', 'https://')):
                    await modal_interaction.response.send_message("URL invalide.", ephemeral=True)
                    return
                self.parent_view.embed_data["thumbnail"] = url or None
                await self.parent_view.update_message(modal_interaction)
        await interaction.response.send_modal(ThumbModal(self))

    @discord.ui.button(label="Set Image URL", style=discord.ButtonStyle.secondary)
    async def edit_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ImageModal(discord.ui.Modal, title="Set Image URL"):
            url_input = discord.ui.TextInput(label="Image URL", placeholder="https://...", required=False)
            def __init__(self, parent_view: EmbedBuilderView):
                super().__init__()
                self.parent_view = parent_view
            async def on_submit(self, modal_interaction: discord.Interaction):
                url = self.url_input.value.strip()
                if url and not url.startswith(('http://', 'https://')):
                    await modal_interaction.response.send_message("URL invalide.", ephemeral=True)
                    return
                self.parent_view.embed_data["image"] = url or None
                await self.parent_view.update_message(modal_interaction)
        await interaction.response.send_modal(ImageModal(self))

    @discord.ui.button(label="Edit Footer Text", style=discord.ButtonStyle.secondary)
    async def edit_footer_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        class FooterModal(discord.ui.Modal, title="Edit Footer Text"):
            text_input = discord.ui.TextInput(label="Footer Text", required=False, max_length=2048)
            def __init__(self, parent_view: EmbedBuilderView):
                super().__init__()
                self.parent_view = parent_view
            async def on_submit(self, modal_interaction: discord.Interaction):
                self.parent_view.embed_data["footer_text"] = self.text_input.value or None
                await self.parent_view.update_message(modal_interaction)
        await interaction.response.send_modal(FooterModal(self))

    @discord.ui.button(label="Clear All Fields", style=discord.ButtonStyle.danger)
    async def clear_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed_data["fields"].clear()
        await self.update_message(interaction)

    @discord.ui.button(label="Send Embed", style=discord.ButtonStyle.success)
    async def send_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Envoie final dans le salon choisi
        await self.destination.send(embed=self.build_embed())
        await interaction.response.edit_message(content="Embed envoyé !", embed=None, view=None)

class EmbedTools(commands.Cog):
    """
    Cog fournissant une commande slash pour créer des embeds personnalisés.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="make_embed", description="Crée un message embed entièrement personnalisé.")
    @app_commands.describe(channel="Salon où envoyer l'embed final")
    async def make_embed(self, interaction: discord.Interaction, channel: discord.TextChannel):
        view = EmbedBuilderView(destination=channel)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedTools(bot))
