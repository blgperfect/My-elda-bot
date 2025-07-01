import asyncio
import discord
from discord import File
from discord.ext import commands, tasks
from discord import app_commands
from io import BytesIO
import jinja2
from playwright.async_api import async_playwright
from pymongo import ReturnDocument

from config.mongo import profile_collection

# --- Setup Jinja2 pour charger le template HTML ---
template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("templates"),
    autoescape=jinja2.select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True
)
template = template_env.get_template("profile_template.html")


async def render_profile_to_image(data: dict) -> BytesIO:
    """Rend la carte HTML en PNG et retourne un buffer BytesIO."""
    html = template.render(
        avatar_url=data.get("avatar_url", ""),
        nickname=data.get("nickname") or "inconnu",
        age=data.get("age") or "inconnu",
        gender=data.get("gender") or "inconnu",
        pronoun=data.get("pronoun") or "inconnu",
        birthday=data.get("birthday") or "inconnu",
        description=data.get("description") or "aucune"
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 600, "height": 350})
        await page.set_content(html, wait_until="networkidle")
        card = await page.query_selector(".card")
        png = await (card.screenshot(omit_background=True) if card else page.screenshot(omit_background=True))
        await browser.close()
    buf = BytesIO(png)
    buf.seek(0)
    return buf


class CreateProfileModal(discord.ui.Modal, title="Créer votre profil"):
    surname = discord.ui.TextInput(label="Surnom", max_length=100, required=False)
    age = discord.ui.TextInput(label="Âge", max_length=3, required=False)
    pronoun = discord.ui.TextInput(label="Pronom", max_length=20, required=False)
    birthday = discord.ui.TextInput(label="Anniversaire (JJ/MM/AAAA)", max_length=10, required=False)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=300, required=False)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            "nickname": self.surname.value,
            "age": self.age.value,
            "pronoun": self.pronoun.value,
            "birthday": self.birthday.value,
            "description": self.description.value
        }
        view = GenderSelectView(self.bot, data)
        await interaction.response.send_message(
            "Dernière étape : sélectionnez votre genre ci-dessous.",
            view=view,
            ephemeral=True
        )


class GenderSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, data: dict):
        super().__init__(timeout=None)
        self.bot = bot
        self.data = data
        options = [
            discord.SelectOption(label="Femme", value="female"),
            discord.SelectOption(label="Homme", value="male"),
            discord.SelectOption(label="Autre", value="other"),
        ]
        self.add_item(discord.ui.Select(
            placeholder="Votre genre",
            options=options,
            custom_id="gender_select"
        ))

    @discord.ui.select(custom_id="gender_select")
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.data["gender"] = select.values[0]
        guild = interaction.guild
        user = interaction.user

        if await profile_collection.find_one({"guild_id": guild.id, "user_id": user.id}):
            return await interaction.response.send_message(
                "❌ Vous avez déjà un profil.", ephemeral=True
            )

        doc = {**self.data, "guild_id": guild.id, "user_id": user.id}
        await profile_collection.insert_one(doc)

        buffer = await render_profile_to_image({"avatar_url": user.display_avatar.url, **self.data})
        cfg = await profile_collection.find_one({"_id": f"config_{guild.id}"})
        channel_id = cfg.get(f"{self.data['gender']}_channel")
        channel = guild.get_channel(channel_id)
        emoji_str = cfg.get("emoji", "💖")
        try:
            emoji_obj = discord.PartialEmoji.from_str(emoji_str)
        except:
            emoji_obj = emoji_str
        view = LikeView(self.bot, guild.id, user.id, emoji_obj)
        msg = await channel.send(file=File(buffer, "profile.png"), view=view)
        self.bot.add_view(view, message_id=msg.id)

        await interaction.followup.send(
            "✅ Votre profil a été créé !", ephemeral=True
        )


class ProfileActionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Créer", style=discord.ButtonStyle.blurple, custom_id="profile_create")
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateProfileModal(self.bot))

    @discord.ui.button(label="Modifier", style=discord.ButtonStyle.gray, custom_id="profile_modify")
    async def modify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        doc = await profile_collection.find_one({"guild_id": interaction.guild.id, "user_id": interaction.user.id})
        if not doc:
            return await interaction.response.send_message(
                "❌ Pas de profil à modifier.", ephemeral=True
            )
        modal = CreateProfileModal(self.bot)
        modal.surname.default = doc.get("nickname", "")
        modal.age.default = doc.get("age", "")
        modal.pronoun.default = doc.get("pronoun", "")
        modal.birthday.default = doc.get("birthday", "")
        modal.description.default = doc.get("description", "")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.red, custom_id="profile_delete")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        res = await profile_collection.delete_one({"guild_id": interaction.guild.id, "user_id": interaction.user.id})
        if res.deleted_count == 0:
            return await interaction.response.send_message(
                "❌ Pas de profil à supprimer.", ephemeral=True
            )
        await interaction.response.send_message(
            "🗑️ Profil supprimé.", ephemeral=True
        )


class ProfileSetupView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = {}
        # Sélecteurs de salon avec recherche
        channels = [
            ("create_channel", "Salon de création"),
            ("female_channel", "Salon pour femmes"),
            ("male_channel", "Salon pour hommes"),
            ("other_channel", "Salon autre genre"),
        ]
        for idx, (key, placeholder) in enumerate(channels):
            select = discord.ui.ChannelSelect(
                placeholder=placeholder,
                custom_id=f"setup_{key}",
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1,
                row=idx
            )
            async def select_callback(interaction: discord.Interaction, select=select, key=key):
                self.config[key] = select.values[0].id
                await interaction.response.defer(ephemeral=True)
            select.callback = select_callback
            self.add_item(select)

        # Bouton Terminer
        confirm_button = discord.ui.Button(
            label="Terminer",
            style=discord.ButtonStyle.success,
            custom_id="setup_confirm",
            row=len(channels)
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)

    async def confirm_callback(self, interaction: discord.Interaction):
        # Enregistrer la configuration
        await profile_collection.update_one(
            {"_id": f"config_{interaction.guild.id}"},
            {"$set": self.config},
            upsert=True
        )
        # Demande de l'emoji custom
        await interaction.response.send_message(
            "Envoyez maintenant l'emoji custom (ou tapez `skip` pour 💖).",
            ephemeral=True
        )

        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await interaction.client.wait_for("message", timeout=60.0, check=check)
            emoji = msg.content.strip()
            if emoji.lower() == "skip":
                emoji = "💖"
        except asyncio.TimeoutError:
            emoji = "💖"

        # Mettre à jour l'emoji
        await profile_collection.find_one_and_update(
            {"_id": f"config_{interaction.guild.id}"},
            {"$set": {"emoji": emoji}},
            return_document=ReturnDocument.AFTER
        )

        # Envoyer le menu de profil dans le salon de création
        create_ch_id = self.config.get("create_channel")
        if create_ch_id:
            create_channel = interaction.guild.get_channel(create_ch_id)
            if create_channel:
                from discord import Embed
                menu_embed = Embed(
                    title="Gestion de votre profil",
                    description="Cliquez sur les boutons ci-dessous pour gérer votre profil.",
                    color=discord.Color.green()
                )
                await create_channel.send(embed=menu_embed, view=ProfileActionsView(self.bot))

        await interaction.followup.send(f"✅ Configuration terminée avec l'emoji : {emoji}", ephemeral=True)

class LikeView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, owner_id: int, emoji):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            emoji=emoji,
            custom_id=f"like:{guild_id}:{owner_id}"
        )
        button.callback = self.on_like
        self.add_item(button)

    async def on_like(self, interaction: discord.Interaction):
        liker = interaction.user
        if liker.id == self.owner_id:
            return await interaction.response.send_message(
                "❌ Vous ne pouvez pas liker votre propre profil.", ephemeral=True
            )
        liker_doc = await profile_collection.find_one({"guild_id": self.guild_id, "user_id": liker.id})
        if not liker_doc:
            return await interaction.response.send_message(
                "❌ Vous devez avoir un profil pour liker.", ephemeral=True
            )
        buffer = await render_profile_to_image({"avatar_url": liker.display_avatar.url, **liker_doc})
        guild = self.bot.get_guild(self.guild_id)
        owner = guild.get_member(self.owner_id) or await guild.fetch_member(self.owner_id)
        dm = await owner.create_dm()
        ar = AcceptRejectView(self.bot, self.guild_id, self.owner_id, liker.id)
        msg = await dm.send(
            f"💌 Votre profil a été liké par **{liker.display_name}**.",
            file=File(buffer, "like.png"), view=ar
        )
        self.bot.add_view(ar, message_id=msg.id)
        await interaction.response.send_message("👍 Like envoyé !", ephemeral=True)


class AcceptRejectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, owner_id: int, liker_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.liker_id = liker_id

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, custom_id="accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)
        owner = await self.bot.fetch_user(self.owner_id)
        liker = await self.bot.fetch_user(self.liker_id)
        await liker.create_dm().send(f"✅ **{owner.display_name}** a accepté votre like.")
        await owner.create_dm().send(f"✅ Vous avez accepté le like de {liker.display_name}.")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, custom_id="refuse")
    async def refuse(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)
        liker = await self.bot.fetch_user(self.liker_id)
        await liker.create_dm().send("❌ Votre like n'a pas été retenu.")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)


class ProfileCog(commands.Cog):
    """Cog de gestion du système de profils Meet & Friendly."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(ProfileActionsView(bot))
        self.republish_profiles.start()

    @app_commands.command(name="profile_setup", description="Configure les salons pour le système de profils.")
    @app_commands.checks.has_permissions(administrator=True)
    async def profile_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Configuration du système de profils",
            description=(
                "**Bienvenue !**\n"
                "Sélectionnez ci-dessous les salons dédiés à chaque étape.\n"
                "Cliquez ensuite sur **Terminer**."
            ),
            color=discord.Color.blurple()
        )
        view = ProfileSetupView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.command(name="profile_menu")
    async def profile_menu(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Gestion de votre profil",
            description="Cliquez sur les boutons ci-dessous pour gérer votre profil.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed, view=ProfileActionsView(self.bot))

    @tasks.loop(hours=24)
    async def republish_profiles(self):
        for guild in self.bot.guilds:
            cfg = await profile_collection.find_one({"_id": f"config_{guild.id}"})
            if not cfg:
                continue
            cursor = profile_collection.find({"guild_id": guild.id, "user_id": {"$ne": None}})
            async for doc in cursor:
                member = guild.get_member(doc["user_id"])
                if not member:
                    continue
                buf = await render_profile_to_image({"avatar_url": member.display_avatar.url, **doc})
                ch = guild.get_channel(cfg.get(f"{doc['gender']}_channel"))
                if not ch:
                    continue
                emo_str = cfg.get("emoji", "💖")
                try:
                    emo = discord.PartialEmoji.from_str(emo_str)
                except:
                    emo = emo_str
                view = LikeView(self.bot, guild.id, doc["user_id"], emo)
                msg = await ch.send(file=File(buf, "profile.png"), view=view)
                self.bot.add_view(view, message_id=msg.id)

    @republish_profiles.before_loop
    async def before_republish(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
