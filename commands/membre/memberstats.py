import datetime
import io
from io import BytesIO

import discord
from discord import File
from discord import app_commands
from discord.ext import commands
import jinja2
from playwright.async_api import async_playwright

from config.mongo import stats_collection

# Jinja2 template setup
template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("templates"),
    autoescape=jinja2.select_autoescape(["html"])
)
template = template_env.get_template("user_stats.html")

class MemberStats(commands.Cog):
    """Cog pour tracker et afficher les stats d'un membre."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.voice_sessions: dict[int, datetime.datetime] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        today_str = datetime.date.today().isoformat()
        # Incrémente messages quotidiens
        await stats_collection.update_one(
            {"guild_id": message.guild.id, "user_id": message.author.id, "type": "daily", "date": today_str},
            {"$inc": {"msg_count": 1}}, upsert=True
        )
        # Incrémente messages par canal
        await stats_collection.update_one(
            {"guild_id": message.guild.id, "user_id": message.author.id, "type": "channel", "channel_id": message.channel.id},
            {"$inc": {"msg_count": 1}}, upsert=True
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot or not member.guild:
            return
        now_dt = datetime.datetime.utcnow()
        # Commence session
        if before.channel is None and after.channel is not None:
            self.voice_sessions[member.id] = now_dt
        # Termine session
        if before.channel and (after.channel is None or after.channel.id != before.channel.id):
            start = self.voice_sessions.pop(member.id, None)
            if start:
                secs = int((now_dt - start).total_seconds())
                day_str = start.date().isoformat()
                # Update quotidien
                await stats_collection.update_one(
                    {"guild_id": member.guild.id, "user_id": member.id, "type": "daily", "date": day_str},
                    {"$inc": {"voice_seconds": secs}}, upsert=True
                )
                # Update canal vocal
                if before.channel:
                    await stats_collection.update_one(
                        {"guild_id": member.guild.id, "user_id": member.id, "type": "channel", "channel_id": before.channel.id},
                        {"$inc": {"voice_seconds": secs}}, upsert=True
                    )

    @app_commands.command(name="member-stats", description="Affiche les statistiques d'un membre.")
    @app_commands.describe(member="Le membre à analyser. Si non précisé, vous-même.")
    async def member_stats(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        await interaction.response.defer(thinking=True)
        member = member or interaction.user
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("Cette commande doit être utilisée dans un serveur.", ephemeral=True)

        # Récupération données
        today = datetime.date.today()
        start_30 = today - datetime.timedelta(days=29)
        docs = await stats_collection.find({"guild_id": guild.id, "user_id": member.id}).to_list(length=None)
        # Filtrer les types
        daily_docs = [d for d in docs if d.get("type") == "daily" and d.get("date") >= start_30.isoformat()]
        chan_docs = [d for d in docs if d.get("type") == "channel"]

        # Séries temporelles
        dates = [start_30 + datetime.timedelta(days=i) for i in range(30)]
        msg_map = {d["date"]: d.get("msg_count", 0) for d in daily_docs}
        voice_map = {d["date"]: d.get("voice_seconds", 0) // 60 for d in daily_docs}
        msg_counts = [msg_map.get(d.isoformat(), 0) for d in dates]
        voice_mins = [voice_map.get(d.isoformat(), 0) for d in dates]
        total_msgs = sum(msg_counts)
        total_voice = sum(voice_mins)

        # Préparation du HTML
        html = template.render(
            avatar_url     = member.display_avatar.url,
            username       = member.display_name,
            total_messages = total_msgs,
            total_voice    = total_voice,
            message_data   = msg_counts,
            voice_data     = voice_mins,
            time_labels    = [d.strftime("%b %d") for d in dates]
        )

        # Rendu headless Chrome via Playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 1024, "height": 360})
            await page.set_content(html, wait_until="networkidle")
            card = await page.query_selector(".card")
            png = await card.screenshot(omit_background=True)
            await browser.close()

        # Envoi du PNG à Discord
        file = File(BytesIO(png), filename="stats.png")
        await interaction.followup.send(file=file)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemberStats(bot))
