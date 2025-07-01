# commands/membre/serverstats.py

import datetime
import logging
from io import BytesIO
from dataclasses import dataclass
from typing import List

import discord
from discord import File, app_commands
from discord.ext import commands
from playwright.async_api import async_playwright, Error as PWError

from config.mongo import stats_collection

logger = logging.getLogger(__name__)


@dataclass
class UserStat:
    rank: int
    avatar_url: str
    username: str
    total_msgs: int
    total_voice_min: int
    daily_msgs: int


@dataclass
class ChannelStat:
    rank: int
    name: str
    category: str
    count: int  # renamed to match template usage


class StatsService:
    @staticmethod
    async def fetch_all(guild: discord.Guild) -> dict:
        docs = await stats_collection.find({"guild_id": guild.id}).to_list(length=None)
        today_iso = datetime.date.today().isoformat()
        daily = [d for d in docs if d.get("type") == "daily" and d.get("date") == today_iso]
        channels = [d for d in docs if d.get("type") == "channel"]
        return {"daily": daily, "channel": channels}


class StatsRenderer:
    def __init__(self, template_name: str = "server_stats.html"):
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        env = Environment(
            loader=FileSystemLoader("templates"),            # dossier templates/
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.template = env.get_template(template_name)

    def render_html(
        self,
        guild: discord.Guild,
        users: List[UserStat],
        text_ch: List[ChannelStat],
        voice_ch: List[ChannelStat],
    ) -> str:
        return self.template.render(
            guild_pfp=guild.icon.url if guild.icon else "",
            guild_name=guild.name,
            member_count=guild.member_count,
            generated_on=datetime.datetime.utcnow().strftime("%d %B %Y • %H:%M UTC"),
            users=users,
            text_channels=text_ch,
            voice_channels=voice_ch,
        )

    async def to_png(self, html: str) -> bytes:
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(args=["--no-sandbox"])
                page = await browser.new_page(viewport={"width": 1902, "height": 1200, "deviceScaleFactor": 3})
                await page.set_content(html, wait_until="networkidle")

                # full-page capture in case content is larger
                png = await page.screenshot(omit_background=True, full_page=True)
                await browser.close()
                return png

        except PWError as e:
            logger.exception("Playwright rendering failed")
            raise RuntimeError("Échec de génération de l’image") from e


class ServerStatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.renderer = StatsRenderer()

    @app_commands.command(
        name="server-stats",
        description="Génère un visuel pro des stats d'activité du serveur"
    )
    async def server_stats(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("🔄 Génération des statistiques…", ephemeral=True)
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("❌ Cette commande doit être utilisée dans un serveur.", ephemeral=True)

        data = await StatsService.fetch_all(guild)

        # Top 3 users by messages today
        top_users = sorted(data["daily"], key=lambda d: d.get("msg_count", 0), reverse=True)[:3]
        users_stats: List[UserStat] = []
        for i, doc in enumerate(top_users, start=1):
            member = guild.get_member(doc["user_id"])
            users_stats.append(UserStat(
                rank=i,
                avatar_url=member.display_avatar.url if member else "",
                username=member.name if member else str(doc["user_id"]),
                total_msgs=doc.get("msg_count", 0),
                total_voice_min=doc.get("voice_seconds", 0) // 60,
                daily_msgs=doc.get("msg_count", 0),
            ))

        # Top 3 text channels
        txt = [d for d in data["channel"] if d.get("msg_count", 0) > 0]
        top_text = sorted(txt, key=lambda d: d["msg_count"], reverse=True)[:3]
        text_stats: List[ChannelStat] = []
        for i, doc in enumerate(top_text, start=1):
            chan = guild.get_channel(doc["channel_id"])
            text_stats.append(ChannelStat(
                rank=i,
                name=chan.name if chan else f"#{doc['channel_id']}",
                category=(chan.category.name if chan and chan.category else "N/A"),
                count=doc.get("msg_count", 0),
            ))

        # Top 3 voice channels
        vc = [d for d in data["channel"] if d.get("voice_seconds", 0) > 0]
        top_voice = sorted(vc, key=lambda d: d["voice_seconds"], reverse=True)[:3]
        voice_stats: List[ChannelStat] = []
        for i, doc in enumerate(top_voice, start=1):
            chan = guild.get_channel(doc["channel_id"])
            voice_stats.append(ChannelStat(
                rank=i,
                name=chan.name if chan else f"#{doc['channel_id']}",
                category=(chan.category.name if chan and chan.category else "N/A"),
                count=doc.get("voice_seconds", 0) // 60,
            ))

        # Render and screenshot
        html = self.renderer.render_html(guild, users_stats, text_stats, voice_stats)
        try:
            png = await self.renderer.to_png(html)
        except RuntimeError as e:
            return await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

        await interaction.followup.send(file=File(BytesIO(png), filename="server_stats.png"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerStatsCog(bot))
