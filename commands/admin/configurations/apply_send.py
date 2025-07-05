# cogs/apply_send.py

import discord
from discord import app_commands
from discord.ext import commands
from config.mongo import apply_collection
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
    APPLICATION_QUESTIONS
)

class ApplyFlowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="apply_send", description="Publie le menu de candidature")
    async def apply_send(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild.id
        cfg = await apply_collection.find_one({"server_id": guild_id})
        if not cfg or not cfg.get("applications_enabled"):
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=MESSAGES["NOT_CONFIGURED"],
                    color=EMBED_COLOR
                ),
                ephemeral=False
            )

        # Construction de l'embed menu
        embed = discord.Embed(
            title="📋 Menu de candidature",
            description="Sélectionnez le poste pour lequel vous souhaitez postuler :",
            color=EMBED_COLOR
        )
        for app in cfg["applications_enabled"]:
            embed.add_field(name=app, value=EMOJIS.get(app, "📝"), inline=True)

        # Select pour ouvrir le modal
        select = discord.ui.Select(
            placeholder="Choisissez un poste…",
            options=[
                discord.SelectOption(label=app, value=app)
                for app in cfg["applications_enabled"]
            ],
            custom_id="apply_modal"
        )
        view = discord.ui.View(timeout=None)
        view.add_item(select)

        await interaction.followup.send(embed=embed, view=view, ephemeral=False)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # On ne gère que les selects du menu d'apply
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data
        if data.get("component_type") == 3 and data.get("custom_id") == "apply_modal":
            app_name = data["values"][0]
            questions = APPLICATION_QUESTIONS[app_name]

            # Modal dynamique
            class AppModal(discord.ui.Modal, title=f"Candidature — {app_name}"):
                def __init__(self):
                    super().__init__()
                    for key, text, mx in questions:
                        # Label = question (max 45 chars)
                        if len(text) <= 45:
                            label = text
                        else:
                            label = text[:42].rstrip() + "..."
                        # Placeholder générique
                        placeholder = "Votre réponse…"
                        self.add_item(discord.ui.TextInput(
                            label=label,
                            style=discord.TextStyle.paragraph,
                            custom_id=key,
                            placeholder=placeholder,
                            max_length=mx
                        ))

                async def callback(self, modal_inter: discord.Interaction):
                    answers = {c.custom_id: c.value for c in self.children}
                    doc = {
                        "server_id": interaction.guild.id,
                        "user_id": interaction.user.id,
                        "app_name": app_name,
                        "answers": answers,
                        "status": "pending",
                        "timestamp": discord.utils.utcnow()
                    }
                    res = await apply_collection.insert_one(doc)

                    # Embed de notification
                    eb = discord.Embed(
                        title=f"Nouvelle candidature — {app_name}",
                        description=f"Membre : {interaction.user.mention}",
                        color=EMBED_COLOR
                    )
                    for k, v in answers.items():
                        eb.add_field(name=k.upper(), value=v, inline=False)
                    eb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

                    # Boutons pour gérer la candidature
                    view = discord.ui.View(timeout=None)
                    view.add_item(discord.ui.Button(
                        label="✅ Accepter",
                        style=discord.ButtonStyle.success,
                        custom_id=f"apply_accept:{res.inserted_id}"
                    ))
                    view.add_item(discord.ui.Button(
                        label="❌ Refuser",
                        style=discord.ButtonStyle.danger,
                        custom_id=f"apply_refuse:{res.inserted_id}"
                    ))

                    # Envoi dans le canal configuré
                    cfg = await apply_collection.find_one({"server_id": interaction.guild.id})
                    channel = interaction.guild.get_channel(cfg["channel_id"])
                    await channel.send(embed=eb, view=view)

                    # Confirmation à l’utilisateur
                    await modal_inter.response.send_message(
                        "✅ Ta candidature a bien été envoyée !",
                        ephemeral=True
                    )

            # Envoi du modal (ici, on ne defer pas de nouveau)
            await interaction.response.send_modal(AppModal())

async def setup(bot: commands.Bot):
    await bot.add_cog(ApplyFlowCog(bot))
