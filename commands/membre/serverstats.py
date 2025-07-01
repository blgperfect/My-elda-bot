# cogs/serverstats.py

import datetime
from io import BytesIO

import discord
from discord import File, app_commands
from discord.ext import commands
import jinja2
from playwright.async_api import async_playwright

from config.mongo import stats_collection

# Récupère simplement le nom d'un canal
def getChannelName(guild: discord.Guild, channel_id: int) -> str:
    chan = guild.get_channel(channel_id)
    return chan.name if chan else f"#{channel_id}"

# --- Setup Jinja2 ---
template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("templates"),
    autoescape=jinja2.select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True
)
template = template_env.get_template("server_stats.html")


class ServerStats(commands.Cog):
    """Cog pour afficher les statistiques globales du serveur."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="server-stats",
        description="Affiche le top des utilisateurs et des salons du serveur"
    )
    async def server_stats(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "🔄 Génération des statistiques du serveur…",
            ephemeral=True
        )
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send(
                "Cette commande doit être utilisée dans un serveur.",
                ephemeral=True
            )

        # 1️⃣ Récupération de tous les docs pour cette guilde
        docs = await stats_collection.find(
            {"guild_id": guild.id}
        ).to_list(length=None)

        # 2️⃣ Séparation par type
        today_iso = datetime.date.today().isoformat()
        daily_docs = [
            d for d in docs
            if d.get("type") == "daily" and d.get("date") == today_iso
        ]
        chan_docs = [d for d in docs if d.get("type") == "channel"]

        # 3️⃣ Top 3 des USERS (par msg_count)
        top_users = sorted(
            daily_docs,
            key=lambda d: d.get("msg_count", 0),
            reverse=True
        )[:3]

        # 4️⃣ Top 3 des SALONS TEXTUELS (par msg_count)
        top_text = sorted(
            [d for d in chan_docs if d.get("msg_count", 0) > 0],
            key=lambda d: d.get("msg_count", 0),
            reverse=True
        )[:3]

        # 5️⃣ Top 3 des SALONS VOCAUX (par voice_seconds)
        top_voice = sorted(
            [d for d in chan_docs if d.get("voice_seconds", 0) > 0],
            key=lambda d: d.get("voice_seconds", 0),
            reverse=True
        )[:3]

        # 6️⃣ Préparation des données pour Jinja
        users_data, text_data, voice_data = [], [], []

        for rank, doc in enumerate(top_users, start=1):
            user = guild.get_member(doc["user_id"])
            users_data.append({
                "rank": rank,
                "avatar_url": user.display_avatar.url if user else "",
                "username": user.name if user else str(doc["user_id"]),
                "total_msgs": doc.get("msg_count", 0),
                "total_voice_min": doc.get("voice_seconds", 0) // 60,
            })

        for rank, doc in enumerate(top_text, start=1):
            ch_id = doc["channel_id"]
            chan = guild.get_channel(ch_id)
            text_data.append({
                "rank": rank,
                "icon": "#",
                "name": chan.name if chan else str(ch_id),
                "category": chan.category.name if chan and chan.category else "N/A",
                "stat_label": f"{doc.get('msg_count', 0)} Messages"
            })

        for rank, doc in enumerate(top_voice, start=1):
            ch_id = doc["channel_id"]
            chan = guild.get_channel(ch_id)
            voice_data.append({
                "rank": rank,
                "icon": "🎤",
                "name": chan.name if chan else str(ch_id),
                "category": chan.category.name if chan and chan.category else "N/A",
                "stat_label": f"{doc.get('voice_seconds', 0)//60} Minutes"
            })

        # 7️⃣ Rendu du template
        html = template.render(
            guild_name=guild.name,
            member_count=guild.member_count,
            generated_on=datetime.datetime.utcnow().strftime("%d %B %Y à %H:%M"),
            users=users_data,
            text_channels=text_data,
            voice_channels=voice_data,
        )

        # 8️⃣ Capture headless avec Playwright (cible la classe .card)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page(
                viewport={"width": 1024, "height": 900, "deviceScaleFactor": 3}
            )
            await page.set_content(html, wait_until="networkidle")

            element = await page.query_selector(".card")
            if element:
                png = await element.screenshot(omit_background=True)
            else:
                png = await page.screenshot(omit_background=True)

            await browser.close()

        # 9️⃣ Envoi de l’image
        await interaction.followup.send(
            file=File(BytesIO(png), filename="server_stats.png")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerStats(bot))
