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


class AdminActionView(discord.ui.View):
    def __init__(self, member: discord.Member, app_name: str, channel: discord.TextChannel, cfg: dict):
        super().__init__(timeout=None)
        self.member = member
        self.app_name = app_name
        self.channel = channel
        self.cfg = cfg

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Vérifie d'abord si le bot a la permission de gérer les rôles
        me = interaction.guild.me
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "❌ Je n'ai pas la permission `Gérer les rôles`. Merci de la m'accorder.",
                ephemeral=True
            )

        roles_map = self.cfg.get("application_roles", {})
        role_id = roles_map.get(self.app_name)
        if not role_id:
            return await interaction.response.send_message(
                f"❌ Aucun rôle configuré pour {self.app_name}.", ephemeral=True
            )

        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message(
                f"❌ Le rôle configuré (ID {role_id}) est introuvable sur ce serveur.", ephemeral=True
            )

        # Vérifie la hiérarchie : le bot doit être au-dessus du rôle cible
        if me.top_role <= role:
            return await interaction.response.send_message(
                "❌ Je ne peux pas attribuer ce rôle car il est supérieur ou égal à mon rôle le plus haut.",
                ephemeral=True
            )

        # Tente d'ajouter le rôle
        try:
            await self.member.add_roles(role, reason="Candidature acceptée")
            await interaction.response.send_message(
                f"✅ Le rôle {role.mention} a été attribué à {self.member.mention}.",
                ephemeral=False
            )
            log.info("Rôle %s attribué à %s", role.name, self.member)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Impossible d'ajouter le rôle en raison de permissions manquantes ou d'une hiérarchie trop élevée.",
                ephemeral=True
            )
        except Exception as e:
            log.exception("Erreur lors de l'ajout du rôle", exc_info=e)
            await interaction.response.send_message(
                "❌ Une erreur est survenue lors de l'attribution du rôle.",
                ephemeral=True
            )

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        dm_message = (
            f"Désolé {self.member.name}, vous avez été refusé pour le poste **{self.app_name}** "
            f"sur le serveur **{interaction.guild.name}**."
        )
        try:
            await self.member.send(dm_message)
            await interaction.response.send_message(
                f"Utilisateur {self.member.mention} informé en DM du refus.", ephemeral=False
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"Le message privé à {self.member.mention} n'a pas pu être envoyé. "
                "Veuillez le contacter manuellement.", ephemeral=False
            )


class ApplySendView(discord.ui.View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg

        options = [
            discord.SelectOption(label=app, value=app, emoji=EMOJIS.get(app))
            for app in cfg.get("applications_enabled", [])
        ]
        select = discord.ui.Select(
            placeholder="Choisissez un poste…",
            min_values=1,
            max_values=1,
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        app_name = interaction.data["values"][0]
        questions = APPLICATION_QUESTIONS.get(app_name, [])

        if len(questions) > 5:
            return await interaction.response.send_message(
                f"❌ Impossible de traiter plus de 5 questions (actuellement {len(questions)}).",
                ephemeral=True
            )

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
                log.info("AppModal.on_submit démarré pour %s", modal_inter.user)
                answers = {item.custom_id: item.value for item in modal_self.children}

                # Prépare la config en surchargeant le channel staff configuré dans setup
                owner_cog = modal_inter.client.get_cog("ApplyFlowCog")
                cfg = owner_cog.cfg.copy()
                cfg["channel_id"] = cfg.get("channel_id")  # salon configuré via /apply_setup
                cfg["application_roles"] = owner_cog.cfg.get("application_roles", {})

                # Enregistrement de la candidature
                doc = {
                    "server_id": modal_inter.guild.id,
                    "user_id": modal_inter.user.id,
                    "app_name": modal_self.app_name,
                    "answers": answers,
                    "status": "pending",
                    "timestamp": discord.utils.utcnow(),
                    "application_roles": cfg["application_roles"]
                }
                await apply_collection.insert_one(doc)

                # Embed staff
                embed_admin = discord.Embed(
                    title=f"Nouvelle candidature — {modal_self.app_name}",
                    description=f"Membre : {modal_inter.user.mention}",
                    color=EMBED_COLOR,
                    timestamp=discord.utils.utcnow()
                ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
                for key, text, _ in modal_self.questions:
                    embed_admin.add_field(name=text, value=answers.get(key, "—"), inline=False)

                staff_channel = modal_inter.guild.get_channel(cfg["channel_id"])
                if staff_channel:
                    view = AdminActionView(modal_inter.user, modal_self.app_name, staff_channel, cfg)
                    await staff_channel.send(embed=embed_admin, view=view)
                else:
                    log.warning("Salon de réception non trouvé (ID %s)", cfg["channel_id"])

                await modal_inter.response.send_message(
                    "✅ Merci ! Votre candidature a bien été enregistrée.",
                    ephemeral=True
                )

            async def on_error(modal_self, modal_inter: discord.Interaction, error: Exception):
                log.exception("Erreur inattendue dans AppModal", exc_info=error)
                if not modal_inter.response.is_done():
                    await modal_inter.response.send_message(
                        "❌ Une erreur grave est survenue. Contactez un admin.",
                        ephemeral=True
                    )

        await interaction.response.send_modal(AppModal())


class ApplyFlowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cfg = {}

    @app_commands.command(
        name="apply_send",
        description="Publie le menu de candidature dans ce salon"
    )
    async def apply_send(self, interaction: discord.Interaction):
        log.info("Commande /apply_send invoquée par %s", interaction.user)

        # Chargement de la configuration (canal staff + mapping roles_by_app)
        self.cfg = await apply_collection.find_one({"server_id": interaction.guild.id}) or {}

        if not self.cfg.get("applications_enabled"):
            log.warning("Configuration manquante ou pas d'applications activées")
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=MESSAGES["NOT_CONFIGURED"],
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )

        # Conversion en int des rôles_by_app
        roles_map = self.cfg.get("roles_by_app", {})
        self.cfg["roles_by_app"] = {app: [int(r) for r in lst] for app, lst in roles_map.items()}
        # Prépare mapping simple pour AdminActionView (1er rôle si plusieurs)
        self.cfg["application_roles"] = {app: ids[0] for app, ids in self.cfg["roles_by_app"].items()}

        # Surcharge dynamique du salon staff reste la config de setup
        # L'embed candidat est posté directement dans le salon courant
        self.cfg["channel_id"] = self.cfg.get("channel_id")

        # Embed candidat
        embed = discord.Embed(
            title="📋 Menu de candidature",
            description="Sélectionnez le poste pour lequel vous souhaitez postuler :",
            color=EMBED_COLOR
        )
        for app in self.cfg["applications_enabled"]:
            embed.add_field(name=app, value=EMOJIS.get(app, "📝"), inline=True)
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        view = ApplySendView(self.cfg)
        await interaction.response.send_message(embed=embed, view=view)
        log.info("Menu de candidature envoyé dans #%s (ID %d)", interaction.channel.name, interaction.channel_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(ApplyFlowCog(bot))
