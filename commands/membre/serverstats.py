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


def get_channel_name(guild: discord.Guild, channel_id: int) -> str:
    chan = guild.get_channel(channel_id)
    return chan.name if chan else f"#{channel_id}"


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
    count: int  # msg_count or voice_min


class StatsService:
    @staticmethod
    async def fetch(guild: discord.Guild) -> dict:
        docs = await stats_collection.find({"guild_id": guild.id}).to_list(None)
        today = datetime.date.today().isoformat()
        daily = [d for d in docs if d.get("type") == "daily" and d.get("date") == today]
        chan = [d for d in docs if d.get("type") == "channel"]
        return {"daily": daily, "channel": chan}


class StatsRenderer:
    def __init__(self, template_name: str = "server_stats.html"):
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.template = env.get_template(template_name)

    def render_html(self,
                    guild: discord.Guild,
                    users: List[UserStat],
                    text_ch: List[ChannelStat],
                    voice_ch: List[ChannelStat]
                   ) -> str:
        return self.template.render(
            guild_pfp=guild.icon.url if guild.icon else "",
            guild_name=guild.name,
            member_count=guild.member_count,
            generated_on=datetime.datetime.utcnow().strftime("%d %B %Y • %H:%M UTC"),
            users=users, text_channels=text_ch, voice_channels=voice_ch,
            footer_text=f"Stats generated on {datetime.datetime.utcnow().strftime('%B %d, %Y at %I:%M %p')}"
        )

    async def to_png(self, html: str) -> bytes:
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(args=["--no-sandbox"])
                page = await browser.new_page(viewport={"width": 1902, "height": 800, "deviceScaleFactor": 3})
                await page.set_content(html, wait_until="networkidle")
                element = await page.query_selector(".container")
                png = await (element.screenshot(omit_background=True)
                             if element else page.screenshot(omit_background=True))
                await browser.close()
                return png
        except PWError as e:
            logger.exception("Playwright error during screenshot generation")
            raise RuntimeError("Échec de génération de l'image") from e


class ServerStatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.renderer = StatsRenderer()

    @app_commands.command(
        name="server-stats", description="Génère un visuel des stats d'activité du serveur"
    )
    async def server_stats(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "🔄 Génération des statistiques du serveur…",
            ephemeral=True
        )
        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send(
                "Cette commande doit être utilisée dans un serveur.",
                ephemeral=True
            )

        data = await StatsService.fetch(guild)

        # Top 3 users
        top_users = sorted(data["daily"], key=lambda d: d.get("msg_count", 0), reverse=True)[:3]
        users_stats = []
        for i, d in enumerate(top_users, start=1):
            m = guild.get_member(d["user_id"])
            users_stats.append(UserStat(
                rank=i,
                avatar_url=m.display_avatar.url if m else "",
                username=m.name if m else str(d["user_id"]),
                total_msgs=d.get("msg_count", 0),
                total_voice_min=d.get("voice_seconds", 0) // 60,
                daily_msgs=d.get("msg_count", 0)
            ))

        # Top 3 text channels
        text_raw = [d for d in data["channel"] if d.get("msg_count", 0) > 0]
        text_stats = [
            ChannelStat(
                rank=i+1,
                name=get_channel_name(guild, d["channel_id"]),
                category=(guild.get_channel(d["channel_id"]).category.name
                          if guild.get_channel(d["channel_id"]) and guild.get_channel(d["channel_id"]).category else "N/A"),
                count=d.get("msg_count", 0)
            )
            for i, d in enumerate(sorted(text_raw, key=lambda x: x["msg_count"], reverse=True)[:3])
        ]

        # Top 3 voice channels
        voice_raw = [d for d in data["channel"] if d.get("voice_seconds", 0) > 0]
        voice_stats = [
            ChannelStat(
                rank=i+1,
                name=get_channel_name(guild, d["channel_id"]),
                category=(guild.get_channel(d["channel_id"]).category.name
                          if guild.get_channel(d["channel_id"]) and guild.get_channel(d["channel_id"]).category else "N/A"),
                count=d.get("voice_seconds", 0) // 60
            )
            for i, d in enumerate(sorted(voice_raw, key=lambda x: x["voice_seconds"], reverse=True)[:3])
        ]

        html = self.renderer.render_html(guild, users_stats, text_stats, voice_stats)

        try:
            png = await self.renderer.to_png(html)
        except RuntimeError as err:
            return await interaction.followup.send(f"❌ Erreur : {err}", ephemeral=True)

        await interaction.followup.send(
            file=File(BytesIO(png), filename="server_stats.png")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerStatsCog(bot))
