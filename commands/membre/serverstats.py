# commands/membre/serverstats.py

import datetime
from io import BytesIO

import discord
from discord import File, app_commands
from discord.ext import commands
import jinja2
from playwright.async_api import async_playwright

from config.mongo import stats_collection

# Helper pour récupérer le nom d’un channel
def get_channel_name(guild: discord.Guild, channel_id: int) -> str:
    chan = guild.get_channel(channel_id)
    return chan.name if chan else f"#{channel_id}"

# Setup Jinja2
template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("templates"),
    autoescape=jinja2.select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True
)
template = template_env.get_template("server_stats.html")


class ServerStats(commands.Cog):
    """Affiche le top des utilisateurs et salons les plus actifs."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="server-stats",
        description="Génère un visuel des stats d'activité du serveur"
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

        # 1️⃣ Récupère tous les documents stats de cette guilde
        docs = await stats_collection.find({"guild_id": guild.id}).to_list(length=None)

        # 2️⃣ Sépare daily / channel
        today = datetime.date.today().isoformat()
        daily_docs = [d for d in docs if d.get("type") == "daily" and d.get("date") == today]
        chan_docs  = [d for d in docs if d.get("type") == "channel"]

        # 3️⃣ Top 3 utilisateurs (messages)
        top_users = sorted(daily_docs, key=lambda d: d.get("msg_count", 0), reverse=True)[:3]

        # 4️⃣ Top 3 channels textuels
        top_text = sorted(
            [d for d in chan_docs if d.get("msg_count", 0) > 0],
            key=lambda d: d.get("msg_count", 0), reverse=True
        )[:3]

        # 5️⃣ Top 3 channels vocaux
        top_voice = sorted(
            [d for d in chan_docs if d.get("voice_seconds", 0) > 0],
            key=lambda d: d.get("voice_seconds", 0), reverse=True
        )[:3]

        # 6️⃣ Prépare les données pour le template
        users_data = []
        for rank, doc in enumerate(top_users, start=1):
            member = guild.get_member(doc["user_id"])
            users_data.append({
                "rank": rank,
                "avatar_url": member.display_avatar.url if member else "",
                "username": member.name if member else str(doc["user_id"]),
                "total_msgs": doc.get("msg_count", 0),
                "total_voice_min": doc.get("voice_seconds", 0) // 60,
                "daily_msgs": doc.get("msg_count", 0),
            })

        text_data = []
        for rank, doc in enumerate(top_text, start=1):
            cid = doc["channel_id"]
            text_data.append({
                "rank": rank,
                "icon": "#",
                "name": get_channel_name(guild, cid),
                "category": (guild.get_channel(cid).category.name
                             if guild.get_channel(cid) and guild.get_channel(cid).category
                             else "N/A"),
                "msg_count": doc.get("msg_count", 0)
            })

        voice_data = []
        for rank, doc in enumerate(top_voice, start=1):
            cid = doc["channel_id"]
            voice_data.append({
                "rank": rank,
                "icon": "🎤",
                "name": get_channel_name(guild, cid),
                "category": (guild.get_channel(cid).category.name
                             if guild.get_channel(cid) and guild.get_channel(cid).category
                             else "N/A"),
                "voice_min": doc.get("voice_seconds", 0) // 60
            })

        # 7️⃣ Rend le HTML avec Jinja2
        html = template.render(
            guild_pfp     = guild.icon.url if guild.icon else "",
            guild_name    = guild.name,
            member_count  = guild.member_count,
            generated_on  = datetime.datetime.utcnow().strftime("%d %B %Y à %H:%M"),
            users         = users_data,
            text_channels = text_data,
            voice_channels= voice_data,
            footer_text   = f"Stats generated on {datetime.datetime.utcnow().strftime('%B %d, %Y at %I:%M %p')}"
        )

        # 8️⃣ Capture headless via Playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page(
                viewport={"width": 1902, "height": 1080, "deviceScaleFactor": 3}
            )
            await page.set_content(html, wait_until="networkidle")

            # Capture uniquement la carte .container
            element = await page.query_selector(".container")
            if element:
                png = await element.screenshot(omit_background=True)
            else:
                png = await page.screenshot(omit_background=True)

            await browser.close()

        # 9️⃣ Envoi de l’image dans Discord
        await interaction.followup.send(
            file=File(BytesIO(png), filename="server_stats.png")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerStats(bot))
