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
        avatar_url  = data.get("avatar_url", ""),
        nickname    = data.get("nickname")    or "inconnu",
        age         = data.get("age")         or "inconnu",
        gender      = data.get("gender")      or "inconnu",
        pronoun     = data.get("pronoun")     or "inconnu",
        birthday    = data.get("birthday")    or "inconnu",
        description = data.get("description") or "aucune"
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width":600,"height":350})
        await page.set_content(html, wait_until="networkidle")
        card = await page.query_selector(".card")
        png  = await card.screenshot(omit_background=True) if card else await page.screenshot(omit_background=True)
        await browser.close()
    buf = BytesIO(png)
    buf.seek(0)
    return buf


class CreateProfileModal(discord.ui.Modal, title="Créer votre profil"):
    surname     = discord.ui.TextInput(label="Surnom", max_length=100, required=False)
    age         = discord.ui.TextInput(label="Âge",    max_length=3,   required=False)
    pronoun     = discord.ui.TextInput(label="Pronom", max_length=20,  required=False)
    birthday    = discord.ui.TextInput(label="Anniversaire (JJ/MM/AAAA)", max_length=10, required=False)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=300, required=False)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            "nickname":    self.surname.value,
            "age":         self.age.value,
            "pronoun":     self.pronoun.value,
            "birthday":    self.birthday.value,
            "description": self.description.value
        }
        view = GenderSelectView(self.bot, data)
        await interaction.response.send_message(
            "Dernière étape : sélectionnez votre genre ci-dessous.",
            view=view, ephemeral=True
        )


class GenderSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, data: dict):
        super().__init__(timeout=None)
        self.bot  = bot
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
        user  = interaction.user

        # 1️⃣ Vérifier qu'il n'existe pas déjà un profil
        exists = await profile_collection.find_one({
            "guild_id": guild.id,
            "user_id":  user.id
        })
        if exists:
            return await interaction.response.send_message(
                "❌ Vous avez déjà un profil.", ephemeral=True
            )

        # 2️⃣ Enregistrer les données en base
        doc = {
            **self.data,
            "guild_id": guild.id,
            "user_id":  user.id
        }
        await profile_collection.insert_one(doc)

        # 3️⃣ Générer et envoyer l’image du profil
        buffer = await render_profile_to_image({
            "avatar_url": user.display_avatar.url,
            **self.data
        })
        cfg = await profile_collection.find_one({"_id": f"config_{guild.id}"})
        mapping = {
            "female": cfg.get("female_channel"),
            "male":   cfg.get("male_channel"),
            "other":  cfg.get("other_channel")
        }
        chan_id = mapping[self.data["gender"]]
        channel = guild.get_channel(chan_id)
        emoji_str = cfg.get("emoji", "💖")
        try:
            emoji_obj = discord.PartialEmoji.from_str(emoji_str)
        except:
            emoji_obj = emoji_str
        view = LikeView(self.bot, guild.id, user.id, emoji_obj)
        msg = await channel.send(file=File(buffer, "profile.png"), view=view)
        self.bot.add_view(view, message_id=msg.id)

        await interaction.followup.send("✅ Votre profil a été créé !", ephemeral=True)


class ProfileActionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Créer", style=discord.ButtonStyle.blurple, custom_id="profile_create")
    async def create_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateProfileModal(self.bot))

    @discord.ui.button(label="Modifier", style=discord.ButtonStyle.gray, custom_id="profile_modify")
    async def modify_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        doc = await profile_collection.find_one({
            "guild_id": interaction.guild.id,
            "user_id":  interaction.user.id
        })
        if not doc:
            return await interaction.response.send_message(
                "❌ Vous n’avez pas de profil à modifier.", ephemeral=True
            )
        modal = CreateProfileModal(self.bot)
        modal.surname.default     = doc.get("nickname", "")
        modal.age.default         = doc.get("age", "")
        modal.pronoun.default     = doc.get("pronoun", "")
        modal.birthday.default    = doc.get("birthday", "")
        modal.description.default = doc.get("description", "")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.red, custom_id="profile_delete")
    async def delete_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        res = await profile_collection.delete_one({
            "guild_id": interaction.guild.id,
            "user_id":  interaction.user.id
        })
        if res.deleted_count == 0:
            return await interaction.response.send_message(
                "❌ Aucun profil trouvé à supprimer.", ephemeral=True
            )
        await interaction.response.send_message("🗑️ Votre profil a été supprimé.", ephemeral=True)


class ProfileSetupView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = {}

    @discord.ui.select(
        placeholder="Salon de création",
        custom_id="setup_create_channel",
        min_values=1,
        max_values=1
    )
    async def on_create(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.config["create_channel"] = int(select.values[0])
        await interaction.response.defer(ephemeral=True)

    @discord.ui.select(
        placeholder="Salon pour femmes",
        custom_id="setup_female_channel",
        min_values=1,
        max_values=1
    )
    async def on_female(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.config["female_channel"] = int(select.values[0])
        await interaction.response.defer(ephemeral=True)

    @discord.ui.select(
        placeholder="Salon pour hommes",
        custom_id="setup_male_channel",
        min_values=1,
        max_values=1
    )
    async def on_male(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.config["male_channel"] = int(select.values[0])
        await interaction.response.defer(ephemeral=True)

    @discord.ui.select(
        placeholder="Salon autre genre",
        custom_id="setup_other_channel",
        min_values=1,
        max_values=1
    )
    async def on_other(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.config["other_channel"] = int(select.values[0])
        await interaction.response.defer(ephemeral=True)

    @discord.ui.button(
        label="Terminer",
        style=discord.ButtonStyle.success,
        custom_id="setup_confirm"
    )
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Enregistrer la config initiale
        await profile_collection.update_one(
            {"_id": f"config_{interaction.guild.id}"},
            {"$set": self.config},
            upsert=True
        )
        # Demander l'emoji custom
        await interaction.response.send_message(
            "Envoyez maintenant l'**emoji custom** (ou tapez `skip` pour 💖 par défaut)",
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

        cfg = await profile_collection.find_one_and_update(
            {"_id": f"config_{interaction.guild.id}"},
            {"$set": {"emoji": emoji}},
            return_document=ReturnDocument.AFTER
        )
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
        liker_doc = await profile_collection.find_one({
            "guild_id": self.guild_id,
            "user_id":  liker.id
        })
        if not liker_doc:
            return await interaction.response.send_message(
                "❌ Vous devez avoir un profil pour liker.", ephemeral=True
            )
        buffer = await render_profile_to_image({
            "avatar_url": liker.display_avatar.url,
            **liker_doc
        })
        guild = self.bot.get_guild(self.guild_id)
        owner = guild.get_member(self.owner_id) or await guild.fetch_member(self.owner_id)
        dm = await owner.create_dm()
        ar_view = AcceptRejectView(self.bot, self.guild_id, self.owner_id, liker.id)
        msg = await dm.send(
            content=(
                f"💌 Bonjour ! Votre profil a été liké par **{liker.display_name}** sur **{guild.name}**."
            ),
            file=File(buffer, "like.png"),
            view=ar_view
        )
        self.bot.add_view(ar_view, message_id=msg.id)
        await interaction.response.send_message("👍 Votre like a bien été envoyé !", ephemeral=True)


class AcceptRejectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, owner_id: int, liker_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.liker_id = liker_id

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, custom_id="accept")
    async def accept(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)
        owner = await self.bot.fetch_user(self.owner_id)
        liker = await self.bot.fetch_user(self.liker_id)
        owner_dm = await owner.create_dm()
        liker_dm = await liker.create_dm()
        await liker_dm.send(f"✅ **{owner.display_name}** a accepté votre like ! Son pseudo est `{owner.display_name}`.")
        await owner_dm.send(f"✅ Vous avez accepté le like de **{liker.display_name}**. Son pseudo est `{liker.display_name}`.")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, custom_id="refuse")
    async def refuse(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Non autorisé.", ephemeral=True)
        liker = await self.bot.fetch_user(self.liker_id)
        dm = await liker.create_dm()
        await dm.send("❌ Désolé, votre like n'a pas été retenu.")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)


class ProfileCog(commands.Cog):
    """Cog de gestion du système de profils Meet & Friendly."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(ProfileActionsView(bot))
        self.republish_profiles.start()

    @app_commands.command(
        name="profile_setup",
        description="Configure les salons pour le système de profils."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def profile_setup(self, interaction: discord.Interaction):
        guild = interaction.guild
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
        for item in view.children:
            if isinstance(item, discord.ui.Select):
                item.options = [
                    discord.SelectOption(label=chan.name, value=str(chan.id))
                    for chan in guild.text_channels
                ]
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.command(name="profile_menu")
    async def profile_menu(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Gestion de votre profil",
            description="Cliquez sur les boutons ci-dessous pour gérer votre profil.",
            color=discord.Color.green()
        )
        view = ProfileActionsView(self.bot)
        await ctx.send(embed=embed, view=view)

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
                buffer = await render_profile_to_image({
                    "avatar_url": member.display_avatar.url,
                    **doc
                })
                chan_id = cfg.get(f"{doc['gender']}_channel")
                channel = guild.get_channel(chan_id)
                if not channel:
                    continue
                emoji_str = cfg.get("emoji", "💖")
                try:
                    emoji_obj = discord.PartialEmoji.from_str(emoji_str)
                except:
                    emoji_obj = emoji_str
                view = LikeView(self.bot, guild.id, doc["user_id"], emoji_obj)
                msg = await channel.send(file=File(buffer, "profile.png"), view=view)
                self.bot.add_view(view, message_id=msg.id)

    @republish_profiles.before_loop
    async def before_republish(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
