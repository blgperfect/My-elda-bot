# commands/membre/memberstats.py

import datetime
from io import BytesIO

import discord
from discord import File, app_commands
from discord.ext import commands
import jinja2
from playwright.async_api import async_playwright

from config.mongo import stats_collection

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
        await stats_collection.update_one(
            {"guild_id": message.guild.id, "user_id": message.author.id, "type": "daily", "date": today_str},
            {"$inc": {"msg_count": 1}}, upsert=True
        )
        await stats_collection.update_one(
            {"guild_id": message.guild.id, "user_id": message.author.id, "type": "channel", "channel_id": message.channel.id},
            {"$inc": {"msg_count": 1}}, upsert=True
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot or not member.guild:
            return
        now_dt = datetime.datetime.utcnow()
        if before.channel is None and after.channel is not None:
            self.voice_sessions[member.id] = now_dt
        elif before.channel and (after.channel is None or after.channel.id != before.channel.id):
            start = self.voice_sessions.pop(member.id, None)
            if start:
                secs = int((now_dt - start).total_seconds())
                day_str = start.date().isoformat()
                await stats_collection.update_one(
                    {"guild_id": member.guild.id, "user_id": member.id, "type": "daily", "date": day_str},
                    {"$inc": {"voice_seconds": secs}}, upsert=True
                )
                await stats_collection.update_one(
                    {"guild_id": member.guild.id, "user_id": member.id, "type": "channel", "channel_id": before.channel.id},
                    {"$inc": {"voice_seconds": secs}}, upsert=True
                )

    @app_commands.command(name="member-stats", description="Affiche les statistiques d'un membre.")
    @app_commands.describe(member="Le membre à analyser. Si non précisé, vous-même.")
    async def member_stats(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        await interaction.response.send_message("🔄 Calcul de vos statistiques en cours…", ephemeral=True)
        member = member or interaction.user
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("Cette commande doit être utilisée dans un serveur.", ephemeral=True)

        # 1️⃣ Récupération des données
        today = datetime.date.today()
        start_30 = today - datetime.timedelta(days=29)
        docs = await stats_collection.find({"guild_id": guild.id, "user_id": member.id}).to_list(length=None)

        # 2️⃣ Séries quotidiennes
        daily_docs = [d for d in docs if d.get("type") == "daily" and d.get("date") >= start_30.isoformat()]
        dates = [start_30 + datetime.timedelta(days=i) for i in range(30)]
        msg_map = {d["date"]: d.get("msg_count", 0) for d in daily_docs}
        voice_map = {d["date"]: d.get("voice_seconds", 0) // 60 for d in daily_docs}

        msg_counts = [msg_map.get(d.isoformat(), 0) for d in dates]
        voice_mins = [voice_map.get(d.isoformat(), 0) for d in dates]

        total_msgs = sum(msg_counts)
        total_voice = sum(voice_mins)

        # 3️⃣ Activité récente
        def sum_last(n, data_map):
            return sum(data_map.get((today - datetime.timedelta(days=i)).isoformat(), 0) for i in range(n+1))

        m0 = msg_map.get(today.isoformat(), 0)           # messages 24h
        m7 = sum_last(7, msg_map)                        # messages 7j
        m14 = sum_last(14, msg_map)                      # messages 14j

        v0 = voice_map.get(today.isoformat(), 0)         # voix 24h
        v7 = sum_last(7, voice_map)                      # voix 7j
        v14 = sum_last(14, voice_map)                    # voix 14j

        # 4️⃣ Render le HTML
        html = template.render(
            avatar_url     = member.display_avatar.url,
            username       = member.display_name,
            server_name    = guild.name,
            joined_date    = member.joined_at.strftime("%d %b %Y"),
            total_messages = total_msgs,
            total_voice    = total_voice,
            m0 = m0, m7 = m7, m14 = m14,
            v0 = v0, v7 = v7, v14 = v14,
            generated_on   = datetime.datetime.utcnow().strftime("%d %B %Y à %H:%M")
        )

        # 5️⃣ Capture headless Chrome avec Playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            # viewport ajusté en hauteur pour ne rien couper
            page = await browser.new_page(viewport={"width": 700, "height": 600})
            await page.set_content(html, wait_until="networkidle")
            card = await page.query_selector(".card")
            png = await card.screenshot(omit_background=True)
            await browser.close()

        # 6️⃣ Envoi du PNG
        await interaction.followup.send(file=File(BytesIO(png), "profile_stats.png"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemberStats(bot))
