# cogs/membre/memberstats.py

import datetime
import io

import matplotlib
# Use non-interactive backend to prevent GUI windows on macOS
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from config.params import EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL
from config.mongo import stats_collection

# Constants for layout
CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 600
BG_COLOR = (54, 57, 63)          # Discord dark background
TEXT_COLOR = (255, 255, 255)     # for Pillow drawing
ACCENT_COLOR = (114, 137, 218)   # Discord blurple (0–255)
VOICE_COLOR = (255,  99, 132)    # Pink accent (0–255)
SECTION_BG = (47, 49, 54)
FONT_PATH = "/Library/Fonts/Arial.ttf"  # Adapter selon ton système

# Normalize RGB (0–1) for Matplotlib
TEXT_RGB   = tuple(c/255 for c in TEXT_COLOR)
ACCENT_RGB = tuple(c/255 for c in ACCENT_COLOR)
VOICE_RGB  = tuple(c/255 for c in VOICE_COLOR)

class MemberStats(commands.Cog):
    """Cog pour générer une carte d'activité identique au mockup en image complète."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="member-stats", description="Affiche les statistiques d'un membre.")
    @app_commands.describe(member="Le membre à analyser. Si non précisé, vous-même.")
    async def member_stats(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        # Defer to avoid timeout
        await interaction.response.defer(thinking=True)

        member = member or interaction.user
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("Cette commande doit être utilisée dans un serveur.", ephemeral=True)

        # Fetch data
        today = datetime.date.today()
        start_30 = today - datetime.timedelta(days=29)
        docs = await stats_collection.find({"guild_id": guild.id, "user_id": member.id}).to_list(length=None)

        # Split documents
        daily = [d for d in docs if d.get("type") == "daily" and d.get("date") >= start_30.isoformat()]
        channels = [d for d in docs if d.get("type") == "channel"]

        # Build date maps
        msg_map = {d["date"]: d.get("msg_count", 0) for d in daily}
        voice_map = {d["date"]: d.get("voice_seconds", 0) for d in daily}
        dates = [start_30 + datetime.timedelta(days=i) for i in range(30)]
        msg_counts = [msg_map.get(d.isoformat(), 0) for d in dates]
        voice_minutes = [voice_map.get(d.isoformat(), 0) // 60 for d in dates]

        total_msgs = sum(msg_counts)
        total_voice = sum(voice_minutes)

        # Top channels
        top_msgs = sorted([c for c in channels if c.get("msg_count") is not None], key=lambda x: x["msg_count"], reverse=True)[:3]
        top_voices = sorted([c for c in channels if c.get("voice_seconds") is not None], key=lambda x: x["voice_seconds"], reverse=True)[:3]

        # Generate graph image
        plt.figure(figsize=(8, 2))
        plt.plot(dates, msg_counts, color=TEXT_RGB, alpha=0.8)
        plt.fill_between(dates, msg_counts, color=ACCENT_RGB, alpha=0.6)
        plt.plot(dates, voice_minutes, color=TEXT_RGB, alpha=0.6)
        plt.fill_between(dates, voice_minutes, color=VOICE_RGB, alpha=0.6)
        plt.axis('off')
        buf_graph = io.BytesIO()
        plt.savefig(buf_graph, dpi=100, bbox_inches='tight', transparent=True)
        plt.close()
        buf_graph.seek(0)
        graph_img = Image.open(buf_graph)

        # Create canvas
        canvas = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(canvas)

        # Load fonts
        title_font = ImageFont.truetype(FONT_PATH, 32)
        text_font = ImageFont.truetype(FONT_PATH, 20)
        small_font = ImageFont.truetype(FONT_PATH, 16)

        # Header: avatar + name
        avatar_bytes = await member.display_avatar.read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).resize((80,80)).convert('RGBA')
        mask = Image.new('L', (80,80), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0,0,80,80), fill=255)
        canvas.paste(avatar, (20,20), mask)
        draw.text((110, 30), str(member), font=title_font, fill=TEXT_COLOR)
        draw.text((110, 70), "Stats sur 30 jours", font=small_font, fill=(180,180,180))

        # Metrics (Messages, Voix)
        draw.text((850, 30), str(total_msgs), font=title_font, fill=TEXT_COLOR, anchor="mm")
        draw.text((850, 70), "Messages", font=small_font, fill=(180,180,180), anchor="mm")
        draw.text((950, 30), f"{total_voice} min", font=title_font, fill=TEXT_COLOR, anchor="mm")
        draw.text((950, 70), "Voix", font=small_font, fill=(180,180,180), anchor="mm")

        # Paste graph onto canvas
        canvas.paste(graph_img, (20, 120), graph_img)

        # Prepare section data
        def sum_period(mapping, days): return sum(mapping.get((today - datetime.timedelta(days=i)).isoformat(), 0) for i in range(days))
        msg_1, msg_7, msg_14 = sum_period(msg_map, 1), sum_period(msg_map, 7), sum_period(msg_map, 14)
        voice_1, voice_7, voice_14 = sum_period(voice_map, 1)//60, sum_period(voice_map, 7)//60, sum_period(voice_map, 14)//60

        sections = [
            ("🎧 Vocaux", [f"{i+1}. {guild.get_channel(c['channel_id']).name}: {c['voice_seconds']//60}m" for i,c in enumerate(top_voices)]),
            ("💬 Messages", [f"{i+1}. {guild.get_channel(c['channel_id']).name}: {c['msg_count']}" for i,c in enumerate(top_msgs)]),
            ("📊 Messages", [f"1j: {msg_1}", f"7j: {msg_7}", f"14j: {msg_14}"]),
            ("🔊 Voix", [f"1j: {voice_1}m", f"7j: {voice_7}m", f"14j: {voice_14}m"]),
        ]
        boxes = [(20, 350), (270, 350), (520, 350), (770, 350)]

        # Draw sections
        for (title, lines), (x, y) in zip(sections, boxes):
            draw.rectangle([x, y, x+245, y+200], fill=SECTION_BG)
            draw.text((x+10, y+10), title, font=text_font, fill=ACCENT_COLOR)
            for idx, line in enumerate(lines):
                draw.text((x+10, y+40+25*idx), line, font=text_font, fill=TEXT_COLOR)

        # Send image
        buf = io.BytesIO()
        canvas.save(buf, 'PNG')
        buf.seek(0)
        file = discord.File(buf, filename='stats.png')
        await interaction.followup.send(file=file)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemberStats(bot))
