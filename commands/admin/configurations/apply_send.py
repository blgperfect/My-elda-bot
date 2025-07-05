# cogs/apply_send.py

import logging
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

log = logging.getLogger(__name__)


class ApplySendView(discord.ui.View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg

        # Construire directement le Select avec ses options
        options = [
            discord.SelectOption(label=app, value=app, emoji=EMOJIS.get(app))
            for app in cfg["applications_enabled"]
        ]
        select = discord.ui.Select(
            placeholder="Choisissez un poste…",
            min_values=1,
            max_values=1,
            options=options
        )
        # on lui donne une callback ne prenant qu'un argument
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        # on récupère le Select via self.children[0]
        select: discord.ui.Select = self.children[0]
        app_name = select.values[0]
        questions = APPLICATION_QUESTIONS.get(app_name, [])

        if len(questions) > 5:
            return await interaction.response.send_message(
                f"❌ Impossible de traiter plus de 5 questions (actuellement {len(questions)}).",
                ephemeral=True
            )

        # Définition du Modal
        class AppModal(discord.ui.Modal, title=f"Candidature — {app_name}"):
            def __init__(modal_self):
                super().__init__()
                modal_self.app_name = app_name
                modal_self.questions = questions

                for key, text, mx in questions:
                    label = text if len(text) <= 45 else text[:42].rstrip() + "..."
                    modal_self.add_item(
                        discord.ui.TextInput(
                            custom_id=key,
                            label=label,
                            style=discord.TextStyle.paragraph,
                            placeholder="Votre réponse…",
                            max_length=mx,
                            required=True
                        )
                    )

            async def on_submit(modal_self, modal_inter: discord.Interaction):
                log.info("AppModal.on_submit démarré")
                try:
                    answers = {item.custom_id: item.value for item in modal_self.children}
                    doc = {
                        "server_id": modal_inter.guild.id,
                        "user_id": modal_inter.user.id,
                        "app_name": modal_self.app_name,
                        "answers": answers,
                        "status": "pending",
                        "timestamp": discord.utils.utcnow()
                    }
                    await apply_collection.insert_one(doc)

                    # Notification aux admins/mods
                    embed_admin = discord.Embed(
                        title=f"Nouvelle candidature — {modal_self.app_name}",
                        description=f"Membre : {modal_inter.user.mention}",
                        color=EMBED_COLOR,
                        timestamp=discord.utils.utcnow()
                    )
                    embed_admin.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
                    for q_key, _, _ in modal_self.questions:
                        embed_admin.add_field(
                            name=q_key, value=answers.get(q_key, "—"), inline=False
                        )

                    channel = modal_inter.guild.get_channel(self.cfg["channel_id"])
                    if channel:
                        await channel.send(embed=embed_admin)
                    else:
                        log.warning("Salon de réception non trouvé (ID %s)", self.cfg["channel_id"])

                    await modal_inter.response.send_message(
                        "✅ Merci ! Votre candidature a bien été enregistrée.",
                        ephemeral=True
                    )
                    log.info("Confirmation utilisateur envoyée")
                except Exception:
                    log.exception("Erreur dans AppModal.on_submit")
                    if not modal_inter.response.is_done():
                        await modal_inter.response.send_message(
                            "❌ Une erreur est survenue. Merci de réessayer plus tard.",
                            ephemeral=True
                        )

            async def on_error(modal_self, modal_inter: discord.Interaction, error: Exception):
                log.exception("Erreur inattendue dans AppModal")
                if not modal_inter.response.is_done():
                    await modal_inter.response.send_message(
                        "❌ Une erreur grave est survenue. Contactez un admin.",
                        ephemeral=True
                    )

        log.info("Envoi du modal au user %s", interaction.user)
        await interaction.response.send_modal(AppModal())


class ApplyFlowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="apply_send",
        description="Publie le menu de candidature"
    )
    async def apply_send(self, interaction: discord.Interaction):
        log.info("Commande /apply_send invoquée par %s", interaction.user)
        cfg = await apply_collection.find_one({"server_id": interaction.guild.id})

        if not cfg or not cfg.get("applications_enabled"):
            log.warning("Configuration manquante ou pas d'applications activées")
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=MESSAGES["NOT_CONFIGURED"],
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )

        embed = discord.Embed(
            title="📋 Menu de candidature",
            description="Sélectionnez le poste pour lequel vous souhaitez postuler :",
            color=EMBED_COLOR
        )
        for app in cfg["applications_enabled"]:
            embed.add_field(name=app, value=EMOJIS.get(app, "📝"), inline=True)

        view = ApplySendView(cfg)
        await interaction.response.send_message(embed=embed, view=view)
        log.info("Menu de candidature envoyé publiquement")


async def setup(bot: commands.Bot):
    await bot.add_cog(ApplyFlowCog(bot))
