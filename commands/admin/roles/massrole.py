# commands/admin/roles/mass_role.py
# commande complété 
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import time
import datetime

from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

class MassRole(commands.Cog):
    """Cog pour ajouter ou retirer massivement un rôle à tous les membres."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Groupe de slash-commands /massrole
    massrole = app_commands.Group(
        name="massrole",
        description="Ajouter ou retirer un rôle à tous les membres"
    )

    @massrole.command(name="add", description="Ajouter un rôle à tous les membres")
    @app_commands.describe(role="Le rôle à attribuer")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def add(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        await self._mass_modify(interaction, role, add=True)

    @massrole.command(name="remove", description="Retirer un rôle à tous les membres")
    @app_commands.describe(role="Le rôle à retirer")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        await self._mass_modify(interaction, role, add=False)

    async def _mass_modify(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        add: bool
    ):
        # Vérification runtime
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(
                description="❌ Vous devez être administrateur pour utiliser cette commande.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        start_time = time.monotonic()

        # Récupère tous les membres (Intent Members requis)
        members = [m async for m in guild.fetch_members(limit=None)]
        total = len(members)
        processed = 0

        # Embed initial
        embed = discord.Embed(
            title=f"{'Ajout' if add else 'Retrait'} de rôle en cours…",
            color=EMBED_COLOR
        )
        embed.add_field(name="Rôle", value=f"<@&{role.id}>", inline=True)
        embed.add_field(name="Progression", value=f"{processed}/{total}", inline=True)
        embed.add_field(name="Restant", value=str(total), inline=True)
        embed.add_field(name="ETA", value="Calcul en cours…", inline=True)
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        progress_message = await interaction.followup.send(embed=embed)

        # Boucle d’assignation/retrait
        for member in members:
            try:
                if add:
                    await member.add_roles(role, reason="MassRole operation")
                else:
                    await member.remove_roles(role, reason="MassRole operation")
            except Exception:
                # Vous pouvez logger l’erreur ici si besoin
                pass

            processed += 1

            # Mise à jour toutes les 20 itérations ou à la fin
            if processed % 20 == 0 or processed == total:
                elapsed = time.monotonic() - start_time
                avg = elapsed / processed
                remaining = total - processed
                eta = datetime.timedelta(seconds=int(remaining * avg))

                embed = discord.Embed(
                    title=f"{'Ajout' if add else 'Retrait'} de rôle en cours…",
                    color=EMBED_COLOR
                )
                embed.add_field(name="Rôle", value=f"<@&{role.id}>", inline=True)
                embed.add_field(name="Progression", value=f"{processed}/{total}", inline=True)
                embed.add_field(name="Restant", value=str(remaining), inline=True)
                embed.add_field(name="ETA", value=str(eta), inline=True)
                embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

                await progress_message.edit(embed=embed)

        # Embed de fin
        embed = discord.Embed(
            title="Opération terminée ✅",
            description=(
                f"{'Ajout' if add else 'Retrait'} du rôle "
                f"<@&{role.id}> terminé pour **{total}** membres."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await progress_message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        """Gestion des erreurs pour les commandes du groupe /massrole."""
        cmd = interaction.command
        if not cmd or not getattr(cmd, "parent", None):
            return  # pas une sous-commande
        if cmd.parent.name != "massrole":
            return  # pas notre groupe

        # Permission manquante
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                description="❌ Vous n'avez pas la permission nécessaire pour effectuer cette action.",
                color=EMBED_COLOR
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        # Vous pouvez gérer d’autres AppCommandError ici si besoin

async def setup(bot: commands.Bot):
    await bot.add_cog(MassRole(bot))
