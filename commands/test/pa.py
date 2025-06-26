# commands/ping.py
import discord
from discord import app_commands
from discord.ext import commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, EMOJIS

class Ping(commands.Cog):
    """Commande slash /ping pour tester la latence du bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Teste la latence du bot."
    )
    async def ping(self, interaction: discord.Interaction):
        # Calcul de la latence en ms
        latency_ms = self.bot.latency * 1000
        # Construction de l'embed
        embed = discord.Embed(
            title="🏓 Pong !",
            description=f"{EMOJIS.get('CHECK', '')} Latence : **{latency_ms:.2f} ms**",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        # Envoi de la réponse
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    # Pour discord.py ≥2.0, on utilise bot.add_cog via setup
    await bot.add_cog(Ping(bot))
