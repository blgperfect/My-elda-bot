# cogs/apply_reset.py

import discord
from discord import app_commands
from discord.ext import commands
from config.mongo import apply_collection
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, MESSAGES, EMOJIS

class ResetView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary, custom_id="reset_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        eb = discord.Embed(
            description=f"{EMOJIS['INFO']} Réinitialisation annulée.",
            color=EMBED_COLOR
        )
        eb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=eb, view=None)

    @discord.ui.button(label="✅ Confirmer", style=discord.ButtonStyle.danger, custom_id="reset_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Suppression effective
        await apply_collection.delete_many({"server_id": self.guild_id})
        eb = discord.Embed(
            description=f"{EMOJIS['CHECK']} Configuration remise à zéro.",
            color=EMBED_COLOR
        )
        eb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.edit_message(embed=eb, view=None)

class ApplyResetCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="apply_reset", description="Réinitialise la configuration apply (admin only)")
    async def apply_reset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send(
                embed=discord.Embed(description=MESSAGES["PERMISSION_ERROR"], color=EMBED_COLOR),
                ephemeral=True
            )

        # Vérification async de l'existence de config
        count = await apply_collection.count_documents({"server_id": interaction.guild.id})
        if count == 0:
            eb = discord.Embed(
                description=f"{EMOJIS['WARNING']} Il n'y a rien à réinitialiser. Utilisez la commande `/apply_setup` !",
                color=EMBED_COLOR
            )
            eb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.followup.send(embed=eb, ephemeral=True)

        # Si au moins un document, on affiche la confirmation
        view = ResetView(interaction.guild.id)
        eb = discord.Embed(
            description=f"{EMOJIS['WARNING']} Attention, cela supprimera toute la configuration du serveur. Confirmez ?",
            color=EMBED_COLOR
        )
        eb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.followup.send(embed=eb, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ApplyResetCog(bot))
