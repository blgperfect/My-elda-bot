# cogs/apply_setup.py

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

class ApplySetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="apply_setup",
        description="Configure le système d'application (admin only)"
    )
    @app_commands.describe(channel="Salon où recevoir les candidatures")
    async def apply_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        # 1) Vérification des permissions et enregistrement du salon
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=MESSAGES["PERMISSION_ERROR"],
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )
        guild_id = interaction.guild.id
        await apply_collection.update_one(
            {"server_id": guild_id},
            {"$set": {"channel_id": channel.id}},
            upsert=True
        )

        # 2) Construction du Select d'applications
        apps = list(APPLICATION_QUESTIONS.keys())
        app_select = discord.ui.Select(
            placeholder="Sélectionnez les applications à activer…",
            options=[discord.SelectOption(label=a, value=a) for a in apps],
            min_values=1,
            max_values=len(apps)
        )
        app_view = discord.ui.View(timeout=None)
        app_view.add_item(app_select)

        # Callback pour le choix d'applications
        async def on_apps_select(app_inter: discord.Interaction):
            chosen_apps = app_select.values
            # Enregistrement des applications activées
            await apply_collection.update_one(
                {"server_id": guild_id},
                {"$set": {"applications_enabled": chosen_apps}},
                upsert=True
            )
            # Lancement de la séquence de choix de rôles
            await self._ask_role_for(
                idx=0,
                interaction=app_inter,
                chosen_apps=chosen_apps,
                guild_id=guild_id
            )

        app_select.callback = on_apps_select

        # 3) Envoi du message initial
        await interaction.followup.send(
            embed=discord.Embed(
                description=(
                    f"{EMOJIS['CHECK']} Salon de candidatures enregistré : {channel.mention}\n"
                    "Sélectionnez les applications à activer :"
                ),
                color=EMBED_COLOR
            ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL),
            view=app_view,
            ephemeral=True
        )

    async def _ask_role_for(
        self,
        idx: int,
        interaction: discord.Interaction,
        chosen_apps: list[str],
        guild_id: int
    ):
        """
        Pose la question de choix de rôles pour chosen_apps[idx].
        Enregistre la sélection, puis passe à idx+1 ou termine.
        """
        app_name = chosen_apps[idx]

        # Construction de la liste des rôles disponibles
        roles = [
            r for r in interaction.guild.roles
            if not r.managed and r != interaction.guild.default_role
        ]
        role_select = discord.ui.Select(
            placeholder=f"Choisissez les rôles pour **{app_name}**…",
            options=[discord.SelectOption(label=r.name, value=str(r.id)) for r in roles],
            min_values=1,
            max_values=len(roles)
        )
        view = discord.ui.View(timeout=None)
        view.add_item(role_select)

        async def on_role_select(role_inter: discord.Interaction):
            role_ids = [int(v) for v in role_select.values]
            # Enregistrement des rôles pour l'application courante
            await apply_collection.update_one(
                {"server_id": guild_id},
                {"$set": {f"roles_by_app.{app_name}": role_ids}},
                upsert=True
            )
            mentions = " ".join(f"<@&{rid}>" for rid in role_ids)

            if idx + 1 < len(chosen_apps):
                # Préparation du message intermédiaire
                await role_inter.response.edit_message(
                    embed=discord.Embed(
                        description=(
                            f"{EMOJIS['CHECK']} Application **{app_name}** configurée avec {mentions}.\n"
                            f"Passons maintenant à **{chosen_apps[idx+1]}** :"
                        ),
                        color=EMBED_COLOR
                    ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL),
                    view=None
                )
                # Appel récursif pour l'application suivante
                await self._ask_role_for(
                    idx=idx + 1,
                    interaction=role_inter,
                    chosen_apps=chosen_apps,
                    guild_id=guild_id
                )
            else:
                # Toutes les applications sont configurées → fin
                await role_inter.response.edit_message(
                    embed=discord.Embed(
                        description=(
                            f"{EMOJIS['CHECK']} Toutes les applications "
                            f"({', '.join(chosen_apps)}) sont maintenant configurées !\n"
                            "Vous pouvez lancer `/apply_send`."
                        ),
                        color=EMBED_COLOR
                    ),
                    view=None
                )

        role_select.callback = on_role_select

        # Envoi ou édition du message pour la sélection de rôles
        embed = discord.Embed(
            description=f"Quelle rôle(s) pour **{app_name}** ?",
            color=EMBED_COLOR
        ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        try:
            # Premier tour : éditer le message de l'interaction initiale
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.InteractionResponded:
            # Tours suivants : envoi d'un followup pour éviter l'erreur
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ApplySetupCog(bot))
