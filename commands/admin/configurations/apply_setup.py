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
        # Enregistrement du salon
        await apply_collection.update_one(
            {"server_id": guild_id},
            {"$set": {"channel_id": channel.id}},
            upsert=True
        )

        # Construction du Select d'applications
        apps = list(APPLICATION_QUESTIONS.keys())
        app_select = discord.ui.Select(
            placeholder="Sélectionnez les applications à activer…",
            options=[discord.SelectOption(label=a, value=a) for a in apps],
            min_values=1,
            max_values=len(apps)
        )
        app_view = discord.ui.View(timeout=None)

        async def on_apps_select(app_inter: discord.Interaction):
            chosen_apps = app_select.values
            if not chosen_apps:
                return await app_inter.response.send_message(
                    embed=discord.Embed(
                        description=MESSAGES["NO_APPS_ENABLED"],
                        color=EMBED_COLOR
                    ),
                    ephemeral=True
                )

            # Sauvegarde applications + salon
            await apply_collection.update_one(
                {"server_id": guild_id},
                {"$set": {"applications_enabled": chosen_apps}},
                upsert=True
            )
            # Lancement du choix de rôles
            await self._ask_role_for(
                idx=0,
                interaction=app_inter,
                chosen_apps=chosen_apps,
                guild_id=guild_id
            )

        app_select.callback = on_apps_select
        app_view.add_item(app_select)

        # Envoi du message initial
        await interaction.followup.send(
            embed=discord.Embed(
                description="Quelle(s) application(s) voulez-vous activer ?",
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
        app_name = chosen_apps[idx]
        roles = [
            r for r in interaction.guild.roles
            if not r.managed and r != interaction.guild.default_role
        ]
        if not roles:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"❌ Aucun rôle disponible pour **{app_name}**.",
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )
            return

        role_select = discord.ui.Select(
            placeholder=f"Choisissez les rôles pour {app_name}",
            options=[discord.SelectOption(label=r.name, value=str(r.id)) for r in roles],
            min_values=1,
            max_values=len(roles)
        )
        view = discord.ui.View(timeout=None)

        async def on_role_select(role_inter: discord.Interaction):
            role_ids = [int(v) for v in role_select.values]
            await apply_collection.update_one(
                {"server_id": guild_id},
                {"$set": {f"roles_by_app.{app_name}": role_ids}},
                upsert=True
            )
            mentions = " ".join(f"<@&{rid}>" for rid in role_ids)

            if idx + 1 < len(chosen_apps):
                await role_inter.response.edit_message(
                    embed=discord.Embed(
                        description=(
                            f"{EMOJIS['CHECK']} Roles pour **{app_name}** : {mentions}\n"
                            f"Passons à **{chosen_apps[idx+1]}**…"
                        ),
                        color=EMBED_COLOR
                    ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL),
                    view=None
                )
                await self._ask_role_for(
                    idx=idx+1,
                    interaction=role_inter,
                    chosen_apps=chosen_apps,
                    guild_id=guild_id
                )
            else:
                await role_inter.response.edit_message(
                    embed=discord.Embed(
                        description=(
                            f"{EMOJIS['CHECK']} Toutes les applications "
                            f"({', '.join(chosen_apps)}) sont configurées !\n"
                            "Faites `/apply_send` pour publier le menu."
                        ),
                        color=EMBED_COLOR
                    ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL),
                    view=None
                )

        role_select.callback = on_role_select
        view.add_item(role_select)

        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    description=f"Quelle(s) rôle(s) pour **{app_name}** ?",
                    color=EMBED_COLOR
                ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL),
                view=view
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"Quelle(s) rôle(s) pour **{app_name}** ?",
                    color=EMBED_COLOR
                ).set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL),
                view=view,
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ApplySetupCog(bot))
