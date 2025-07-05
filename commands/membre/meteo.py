# cogs/weather.py

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime


# Cartographie des weathercodes Open-Meteo → description FR
WEATHER_CODES = {
    0: "Ciel dégagé",
    1: "Principalement ensoleillé",
    2: "Partiellement nuageux",
    3: "Couvert",
    45: "Brouillard",
    48: "Brouillard givrant",
    51: "Bruine légère",
    53: "Bruine modérée",
    55: "Bruine dense",
    56: "Bruine verglaçante légère",
    57: "Bruine verglaçante dense",
    61: "Pluie légère",
    63: "Pluie modérée",
    65: "Pluie forte",
    66: "Pluie verglaçante légère",
    67: "Pluie verglaçante forte",
    71: "Chute de neige légère",
    73: "Chute de neige modérée",
    75: "Chute de neige forte",
    77: "Grains de neige",
    80: "Averses de pluie légères",
    81: "Averses modérées",
    82: "Averses fortes",
    85: "Averses de neige légères",
    86: "Averses de neige fortes",
    95: "Orage",
    96: "Orage avec grêle légère",
    99: "Orage avec grêle forte"
}


class WeatherCog(commands.Cog):
    """Affiche la météo actuelle pour n'importe quelle ville, sans clé API."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="weather",
        description="Affiche la météo actuelle d'une ville (ex. `/weather Paris,FR`)."
    )
    @app_commands.describe(
        location="Nom de la ville, éventuellement suivi de ,pays (ex. Montréal,CA)"
    )
    async def weather(
        self,
        interaction: discord.Interaction,
        location: str
    ):
        await interaction.response.defer()

        # 1) Géocodage via Nominatim
        nominatim_url = "https://nominatim.openstreetmap.org/search"
        params_geo = {"q": location, "format": "json", "limit": 1}
        async with aiohttp.ClientSession() as session:
            async with session.get(nominatim_url, params=params_geo) as resp:
                if resp.status != 200:
                    return await interaction.followup.send(
                        f"❌ Erreur géocodage ({resp.status}).", ephemeral=True
                    )
                data_geo = await resp.json()
        if not data_geo:
            return await interaction.followup.send(
                f"❌ Lieu non trouvé : `{location}`.", ephemeral=True
            )
        place = data_geo[0]
        lat, lon = float(place["lat"]), float(place["lon"])
        display_name = place["display_name"]

        # 2) Appel Open-Meteo pour météo courante + humidité
        meteourl = "https://api.open-meteo.com/v1/forecast"
        params_met = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "hourly": "relativehumidity_2m",
            "timezone": "auto"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(meteourl, params=params_met) as resp:
                if resp.status != 200:
                    return await interaction.followup.send(
                        f"❌ Erreur météo ({resp.status}).", ephemeral=True
                    )
                data_met = await resp.json()

        cw = data_met["current_weather"]
        temp = cw["temperature"]
        wind = cw["windspeed"]
        code = cw["weathercode"]
        desc = WEATHER_CODES.get(code, f"Code {code}")
        # Récupérer l'humidité horaire au même timestamp
        hum_times = data_met["hourly"]["time"]
        hum_vals  = data_met["hourly"]["relativehumidity_2m"]
        try:
            idx = hum_times.index(cw["time"])
            humidity = hum_vals[idx]
        except ValueError:
            humidity = None

        # 3) Construction de l'embed
        embed = discord.Embed(
            title=f"Météo à {display_name}",
            description=desc,
            color=0x1E90FF,
            timestamp=datetime.fromisoformat(cw["time"])
        )
        embed.add_field(name="🌡️ Température", value=f"{temp} °C", inline=True)
        if humidity is not None:
            embed.add_field(name="💧 Humidité", value=f"{humidity} %", inline=True)
        embed.add_field(name="🍃 Vent", value=f"{wind} m/s", inline=True)
        embed.set_footer(text="Source : Open-Meteo & OpenStreetMap")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WeatherCog(bot))
