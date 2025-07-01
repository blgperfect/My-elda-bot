import discord
from discord.ext import commands
from discord import app_commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL
from config.mongo import embed_collection

MAX_SAVED = 5
VIEW_TIMEOUT = 900  # 15 minutes

class EmbedBuilderView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, destination: discord.TextChannel, save_name: str | None = None):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.interaction = interaction
        self.destination = destination
        self.save_name = save_name
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
        await self.destination.send(embed=self.build_embed())
        if self.save_name:
            guild_id = self.interaction.guild_id
            total = await embed_collection.count_documents({"guild": guild_id})
            if total >= MAX_SAVED:
                await inter.followup.send(f"Limite atteinte : {MAX_SAVED} embeds maximum.", ephemeral=True)
            else:
                await embed_collection.insert_one({
                    "guild": guild_id,
                    "name": self.save_name,
                    "channel": self.destination.id,
                    "data": self.embed_data
                })
                await inter.followup.send(f"Embed sauvegardé sous `{self.save_name}`.", ephemeral=True)
        try:
            await inter.edit_original_response(content="✅ Embed envoyé.", embed=None, view=None)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Titre", style=discord.ButtonStyle.primary)
    async def edit_title(self, inter: discord.Interaction, button: discord.ui.Button):
        class TitleModal(discord.ui.Modal, title="Modifier le titre"):
            title_input = discord.ui.TextInput(label="Titre", required=False, max_length=256)
            def __init__(self, parent):
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
            def __init__(self, parent):
                super().__init__()
                self.parent = parent
            async def on_submit(self, modal_interaction: discord.Interaction):
                self.parent.embed_data["description"] = self.desc_input.value or None
                await self.parent.update_message(modal_interaction)
        await inter.response.send_modal(DescModal(self))

    @discord.ui.button(label="Ajouter champ", style=discord.ButtonStyle.secondary)
    async def edit_field(self, inter: discord.Interaction, button: discord.ui.Button):
        class FieldModal(discord.ui.Modal, title="Ajouter/Modifier un champ"):
            name = discord.ui.TextInput(label="Nom du champ", required=True)
            value = discord.ui.TextInput(label="Valeur du champ", style=discord.TextStyle.paragraph, required=True)
            inline = discord.ui.TextInput(label="Inline (True/False)", required=True)
            def __init__(self, parent):
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
            def __init__(self, parent):
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
            def __init__(self, parent):
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
            def __init__(self, parent):
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
        class FooterModal(discord.ui.Modal, title="Texte du footer"):
            text_input = discord.ui.TextInput(label="Footer", required=False, max_length=2048)
            def __init__(self, parent):
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

class EmbedPaginatorView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], author: discord.Member):
        super().__init__(timeout=None)
        self.embeds = embeds
        self.index = 0
        self.author = author
        self.prev_button.disabled = True
        self.next_button.disabled = len(embeds) <= 1

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user != self.author:
            return await inter.response.defer()
        self.index -= 1
        self.next_button.disabled = False
        self.prev_button.disabled = self.index == 0
        await inter.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_button(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user != self.author:
            return await inter.response.defer()
        self.index += 1
        self.prev_button.disabled = False
        self.next_button.disabled = self.index == len(self.embeds)-1
        await inter.response.edit_message(embed=self.embeds[self.index], view=self)

class EmbedCog(commands.Cog):
    """Cog pour création et gestion rapide des embeds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="make_embed", description="Créer un embed personnalisé. Optionnellement sauvegarder.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def make_embed(self, interaction: discord.Interaction, channel: discord.TextChannel, name: str | None = None):
        view = EmbedBuilderView(interaction, channel, save_name=name)
        await interaction.response.send_message(
            content="Ce menu expirera dans 15 minutes.", embed=view.build_embed(), view=view
        )

    @app_commands.command(name="list_embeds", description="Afficher et gérer les embeds sauvegardés.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def list_embeds(self, interaction: discord.Interaction):
        docs = await embed_collection.find({"guild": interaction.guild_id}).to_list(length=None)
        if not docs:
            return await interaction.response.send_message("Aucun embed enregistré.", ephemeral=True)

        embeds = []
        for d in docs:
            data = d.get("data", d.get("embed", {}))
            e = discord.Embed(color=data.get("color", EMBED_COLOR))
            if data.get("title"): e.title = data["title"]
            if data.get("description"): e.description = data["description"]
            for fn, fv, fi in data.get("fields", []): e.add_field(name=fn, value=fv, inline=fi)
            if data.get("thumbnail"): e.set_thumbnail(url=data["thumbnail"])
            if data.get("image"): e.set_image(url=data["image"])
            e.set_footer(text=f"Nom : {d['name']}")
            embeds.append(e)

        view = EmbedPaginatorView(embeds, interaction.user)
        await interaction.response.send_message(embed=embeds[0], view=view)

    @make_embed.error
    @list_embeds.error
    async def perm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("🔒 Vous devez être administrateur.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot))
