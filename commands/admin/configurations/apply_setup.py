# cogs/apply_setup.py

import discord
from discord import app_commands
from discord.ext import commands
from config.mongo import apply_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES, EMOJIS, APPLICATION_QUESTIONS

class SetupView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.step = 0
        self.selected_apps: list[str] = []

        # Aucun composant au départ ; on placera au lancement
    async def start(self, interaction: discord.Interaction):
        # Étape 0 : demander le salon par argument (déjà fait par la commande)
        # Étape 1 : affichage du select applications
        self.step = 1
        embed = discord.Embed(
            title="Configuration Applications",
            description="✅ **Salon configuré.** Maintenant, cochez les **applications** à activer :",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        # construit le menu
        options = [discord.SelectOption(label=a, value=a) for a in APPLICATION_QUESTIONS]
        select = discord.ui.Select(placeholder="Sélectionnez…", options=options,
                                   min_values=1, max_values=len(options), custom_id="setup_apps")
        self.clear_items()
        self.add_item(select)
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.select(custom_id="setup_apps")
    async def choose_apps(self, select: discord.ui.Select, interaction: discord.Interaction):
        self.selected_apps = select.values
        apply_collection.update_one(
            {"server_id": self.guild_id},
            {"$set": {"applications_enabled": self.selected_apps}},
            upsert=True
        )
        # Étape 2 : demander les rôles
        self.step = 2
        embed = discord.Embed(
            title="Configuration Applications",
            description=f"{EMOJIS['CHECK']} Applications enregistrées : {', '.join(self.selected_apps)}\n"
                        f"Maintenant, pour chaque application, choisissez **le rôle** à attribuer.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        # on passe à la liaison rôle pour la première appli
        self.index = 0
        self.clear_items()
        # build a role select for selected_apps[0]
        roles = interaction.guild.roles
        opts = [discord.SelectOption(label=r.name, value=str(r.id))
                for r in roles if not r.managed and r != r.guild.default_role]
        role_select = discord.ui.Select(
            placeholder=f"Rôle pour {self.selected_apps[0]}",
            options=opts, min_values=1, max_values=1,
            custom_id="setup_role"
        )
        self.add_item(role_select)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(custom_id="setup_role")
    async def choose_role(self, select: discord.ui.Select, interaction: discord.Interaction):
        role_id = int(select.values[0])
        app = self.selected_apps[self.index]
        apply_collection.update_one(
            {"server_id": self.guild_id},
            {"$set": {f"roles_by_app.{app}": role_id}},
            upsert=True
        )
        self.index += 1
        if self.index < len(self.selected_apps):
            # encore d’autres apps
            next_app = self.selected_apps[self.index]
            embed = discord.Embed(
                title="Configuration Applications",
                description=f"{EMOJIS['CHECK']} Rôle pour **{app}** enregistré.\n"
                            f"Choisissez le rôle pour **{next_app}** :",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            # rebuild options (mêmes rôles)
            roles = interaction.guild.roles
            opts = [discord.SelectOption(label=r.name, value=str(r.id))
                    for r in roles if not r.managed and r != r.guild.default_role]
            select.options = opts
            select.placeholder = f"Rôle pour {next_app}"
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # terminé
            embed = discord.Embed(
                title="Configuration terminée",
                description=f"{EMOJIS['CHECK']} Toutes les applications et les rôles ont été enregistrés.\n"
                            f"Vous pouvez maintenant exécuter `/apply_send` dans le salon public.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            self.clear_items()
            await interaction.response.edit_message(embed=embed, view=None)

class ApplySetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="apply_setup", description="Configure le système d'application (admin only)")
    @app_commands.describe(channel="Salon où recevoir les candidatures")
    async def apply_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send(
                embed=discord.Embed(description=MESSAGES["PERMISSION_ERROR"], color=EMBED_COLOR),
                ephemeral=True
            )

        guild_id = interaction.guild.id
        apply_collection.update_one(
            {"server_id": guild_id},
            {"$set": {"channel_id": channel.id}},
            upsert=True
        )
        # envoie initial, on éditera ce message
        embed = discord.Embed(
            title="Configuration Applications",
            description=f"{EMOJIS['CHECK']} Salon de candidatures enregistré : {channel.mention}\n"
                        "Préparation du menu…",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = SetupView(guild_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.start(interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(ApplySetupCog(bot))
