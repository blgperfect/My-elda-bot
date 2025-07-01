import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, ChannelSelect, Button

# Import de la collection MongoDB dédiée
from config.mongo import custom_voc_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

class CustomVocView(View):
    def __init__(self, bot: commands.Bot, existing: bool, guild: discord.Guild):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild = guild
        self.existing = existing
        self.category_id: int | None = None
        self.channel_id: int | None = None

        # Étape 1: sélection de la catégorie (avec recherche)
        self.category_select = ChannelSelect(
            placeholder="1️⃣ Choisissez la catégorie pour les salons vocaux personnalisés",
            custom_id="customvoc_select_category",
            channel_types=[discord.ChannelType.category],
            min_values=1,
            max_values=1
        )
        self.category_select.callback = self.on_category_selected
        self.add_item(self.category_select)

        # Boutons d'action
        self.btn_create = Button(label="Créer la config", style=discord.ButtonStyle.success, custom_id="customvoc_btn_create")
        self.btn_delete = Button(label="Supprimer la config", style=discord.ButtonStyle.danger, custom_id="customvoc_btn_delete")
        self.btn_create.disabled = existing
        self.btn_delete.disabled = not existing
        self.btn_create.callback = self.on_create_clicked
        self.btn_delete.callback = self.on_delete_clicked
        self.add_item(self.btn_create)
        self.add_item(self.btn_delete)

    async def on_category_selected(self, interaction: discord.Interaction):
        self.category_id = self.category_select.values[0].id
        self.clear_items()
        # Étape 2: sélection du salon de création (avec recherche)
        self.channel_select = ChannelSelect(
            placeholder="2️⃣ Choisissez le salon vocal pour lancer la création",
            custom_id="customvoc_select_channel",
            channel_types=[discord.ChannelType.voice],
            min_values=1,
            max_values=1
        )
        self.channel_select.callback = self.on_channel_selected
        self.add_item(self.channel_select)

        # Ré-ajouter les boutons
        self.btn_create.disabled = self.existing
        self.btn_delete.disabled = not self.existing
        self.add_item(self.btn_create)
        self.add_item(self.btn_delete)

        embed = discord.Embed(
            title="Configuration Custom Voc",
            description=(f"**Catégorie choisie :** <#{self.category_id}>\n\n"
                         "2️⃣ Sélectionnez maintenant le salon vocal pour lancer la création."),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_channel_selected(self, interaction: discord.Interaction):
        self.channel_id = self.channel_select.values[0].id
        embed = discord.Embed(
            title="Configuration Custom Voc",
            description=(f"**Catégorie :** <#{self.category_id}>\n"
                         f"**Salon de création :** <#{self.channel_id}>\n\n"
                         "Appuyez sur **Créer la config** pour valider ou sur **Supprimer la config** pour réinitialiser."),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_create_clicked(self, interaction: discord.Interaction):
        if not (self.category_id and self.channel_id):
            return await interaction.response.send_message("❌ Sélectionnez d'abord catégorie et salon.", ephemeral=True)
        # Sauvegarde en base
        await custom_voc_collection.replace_one(
            {"guild_id": self.guild.id},
            {"guild_id": self.guild.id, "category_id": self.category_id, "create_channel_id": self.channel_id},
            upsert=True
        )
        embed = discord.Embed(
            title="✅ Configuration enregistrée",
            description=(f"Les salons vocaux personnalisés seront créés dans <#{self.category_id}> "
                         f"lorsque des membres rejoindront <#{self.channel_id}>."),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_delete_clicked(self, interaction: discord.Interaction):
        await custom_voc_collection.delete_one({"guild_id": self.guild.id})
        embed = discord.Embed(
            title="🗑️ Configuration supprimée",
            description="La configuration Custom Voc a été réinitialisée. Vous pouvez en créer une nouvelle.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=embed, view=None)

class CustomVocCog(commands.Cog):
    """Cog pour gérer les salons vocaux personnalisés"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_channels.start()

    @app_commands.command(
        name="custom-voc",
        description="Configurer/réinitialiser le système de salons vocaux personnalisés"
    )
    @app_commands.default_permissions(administrator=True)
    async def custom_voc(self, interaction: discord.Interaction):
        existing = await custom_voc_collection.find_one({"guild_id": interaction.guild.id}) is not None
        embed = discord.Embed(
            title="Configuration Custom Voc",
            description=("Bienvenue dans la configuration des salons vocaux personnalisés !\n\n"
                         "1️⃣ Choisissez la **catégorie** où seront créés les salons.\n"
                         "2️⃣ Choisissez le **salon** où les membres pourront lancer la création."),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = CustomVocView(self.bot, existing, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        # Lorsque l'utilisateur rejoint le salon de création
        if after.channel and before.channel != after.channel:
            config = await custom_voc_collection.find_one({"guild_id": member.guild.id})
            if config and after.channel.id == config["create_channel_id"]:
                # Créer un salon personnalisé dans la catégorie configurée
                category = member.guild.get_channel(config["category_id"])
                new_channel = await member.guild.create_voice_channel(
                    name=f"salon de {member.display_name}",
                    category=category,
                    user_limit=0,
                    reason="Salon vocal custom"
                )
                # Transférer l'utilisateur dans le nouveau salon
                await member.move_to(new_channel)

        # Lorsque le salon custom se vide, le supprimer
        if before.channel and before.channel.category_id == (await custom_voc_collection.find_one({"guild_id": member.guild.id}))["category_id"]:
            # Vérifier si le salon est vide
            channel = before.channel
            if isinstance(channel, discord.VoiceChannel) and len(channel.members) == 0:
                # Ne pas supprimer le salon de création principal
                config = await custom_voc_collection.find_one({"guild_id": member.guild.id})
                if channel.id != config.get("create_channel_id"):
                    await channel.delete(reason="Salon vocal custom vidé")

    @tasks.loop(minutes=10)
    async def cleanup_channels(self):
        # Sécurise la suppression de salons oubliés (au cas où)
        async for config in custom_voc_collection.find({}):
            guild = self.bot.get_guild(config["guild_id"])
            if not guild:
                continue
            category = guild.get_channel(config["category_id"])
            for channel in category.voice_channels:
                if channel.id != config.get("create_channel_id") and len(channel.members) == 0:
                    await channel.delete(reason="Cleanup salons vocaux personnalisés vides")

    @cleanup_channels.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(CustomVocCog(bot))
