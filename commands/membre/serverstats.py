import datetime
from io import BytesIO

import discord
from discord import File, app_commands
from discord.ext import commands
import jinja2
from playwright.async_api import async_playwright

from config.mongo import stats_collection

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

        docs = await stats_collection.find({"guild_id": guild.id}).to_list(length=None)
        today = datetime.date.today().isoformat()
        daily = [d for d in docs if d.get("type") == "daily" and d.get("date") == today]
        chan  = [d for d in docs if d.get("type") == "channel"]

        top_users = sorted(daily, key=lambda d: d.get("msg_count", 0), reverse=True)[:3]
        top_text  = sorted([d for d in chan if d.get("msg_count", 0) > 0],
                           key=lambda d: d.get("msg_count", 0), reverse=True)[:3]
        top_voice = sorted([d for d in chan if d.get("voice_seconds", 0) > 0],
                           key=lambda d: d.get("voice_seconds", 0), reverse=True)[:3]

        users_data, text_data, voice_data = [], [], []

        for rank, d in enumerate(top_users, start=1):
            m = guild.get_member(d["user_id"])
            users_data.append({
                "rank": rank,
                "avatar_url": m.display_avatar.url if m else "",
                "username": m.name if m else str(d["user_id"]),
                "total_msgs": d.get("msg_count", 0),
                "total_voice_min": d.get("voice_seconds", 0) // 60,
                "daily_msgs": d.get("msg_count", 0),
            })

        for rank, d in enumerate(top_text, start=1):
            cid = d["channel_id"]
            text_data.append({
                "rank": rank,
                "name": get_channel_name(guild, cid),
                "category": (guild.get_channel(cid).category.name
                             if guild.get_channel(cid) and guild.get_channel(cid).category else "N/A"),
                "msg_count": d.get("msg_count", 0)
            })

        for rank, d in enumerate(top_voice, start=1):
            cid = d["channel_id"]
            voice_data.append({
                "rank": rank,
                "name": get_channel_name(guild, cid),
                "category": (guild.get_channel(cid).category.name
                             if guild.get_channel(cid) and guild.get_channel(cid).category else "N/A"),
                "voice_min": d.get("voice_seconds", 0) // 60
            })

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

        # Capture headless via Playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page(
                viewport={"width": 1902, "height": 800, "deviceScaleFactor": 3}
            )
            await page.set_content(html, wait_until="networkidle")

            element = await page.query_selector(".container")
            if element:
                png = await element.screenshot(omit_background=True)
            else:
                png = await page.screenshot(omit_background=True)

            await browser.close()

        await interaction.followup.send(
            file=File(BytesIO(png), filename="server_stats.png")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerStats(bot))
