# cogs/membre/memberstats.py

import datetime
import io
import matplotlib
# Backend non interactif pour macOS
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from config.params import EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL
from config.mongo import stats_collection

# Dimensions et couleurs (0–255)
WIDTH, HEIGHT   = 1024, 600
BG_COLOR        = (54, 57, 63)
PANEL_BG        = (47, 49, 54)
TEXT_COLOR      = (255, 255, 255)
SUBTEXT_COLOR   = (180, 180, 180)
BLUE            = (114, 137, 218)
PINK            = (255,  99, 132)
GRID_COLOR      = (100/255, 100/255, 100/255)
FONT_PATH       = "/Library/Fonts/Arial.ttf"  # Adapter selon ton système

# Normalisation pour Matplotlib (0–1)
BG_RGB     = tuple(c/255 for c in BG_COLOR)
PANEL_RGB  = tuple(c/255 for c in PANEL_BG)
TEXT_RGB   = tuple(c/255 for c in TEXT_COLOR)
BLUE_RGB   = tuple(c/255 for c in BLUE)
PINK_RGB   = tuple(c/255 for c in PINK)

class MemberStats(commands.Cog):
    """Cog pour tracker et afficher les stats d'un membre."""
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # stocke les timestamps de connexion vocale
        self.voice_sessions: dict[int, datetime.datetime] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignorer bots
        if message.author.bot or not message.guild:
            return
        now = datetime.date.today().isoformat()
        # incrémenter message quotidien
        await stats_collection.update_one(
            {"guild_id": message.guild.id, "user_id": message.author.id, "type": "daily", "date": now},
            {"$inc": {"msg_count": 1}}, upsert=True
        )
        # incrémenter message par canal
        await stats_collection.update_one(
            {"guild_id": message.guild.id, "user_id": message.author.id, "type": "channel", "channel_id": message.channel.id},
            {"$inc": {"msg_count": 1}}, upsert=True
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        # ignore if not guild user
        if member.bot or not member.guild:
            return
        now_dt = datetime.datetime.utcnow()
        # join
        if before.channel is None and after.channel is not None:
            self.voice_sessions[member.id] = now_dt
        # leave or switch
        if before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
            start = self.voice_sessions.pop(member.id, None)
            if start:
                seconds = int((now_dt - start).total_seconds())
                day = start.date().isoformat()
                # incrément temps quotidien
                await stats_collection.update_one(
                    {"guild_id": member.guild.id, "user_id": member.id, "type": "daily", "date": day},
                    {"$inc": {"voice_seconds": seconds}}, upsert=True
                )
                # incrément temps par canal vocal
                chan_id = before.channel.id if before.channel else None
                if chan_id:
                    await stats_collection.update_one(
                        {"guild_id": member.guild.id, "user_id": member.id, "type": "channel", "channel_id": chan_id},
                        {"$inc": {"voice_seconds": seconds}}, upsert=True
                    )

    @app_commands.command(name="member-stats", description="Affiche les statistiques d'un membre.")
    @app_commands.describe(member="Le membre à analyser. Si non précisé, vous-même.")
    async def member_stats(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        await interaction.response.defer(thinking=True)
        member = member or interaction.user
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("Cette commande doit être utilisée dans un serveur.", ephemeral=True)

        # Récupérer données
        today    = datetime.date.today()
        start_30 = today - datetime.timedelta(days=29)
        docs = await stats_collection.find({"guild_id": guild.id, "user_id": member.id}).to_list(length=None)

        # journaliers vs canaux
        daily   = [d for d in docs if d.get("type")=="daily" and d.get("date")>=start_30.isoformat()]
        channel = [d for d in docs if d.get("type")=="channel"]

        # séries temporelles
        dates         = [start_30 + datetime.timedelta(days=i) for i in range(30)]
        msg_map       = {d["date"]: d.get("msg_count", 0) for d in daily}
        voice_map     = {d["date"]: d.get("voice_seconds", 0)//60 for d in daily}
        msg_counts    = [msg_map.get(d.isoformat(), 0) for d in dates]
        voice_minutes = [voice_map.get(d.isoformat(), 0) for d in dates]
        total_msgs    = sum(msg_counts)
        total_voice   = sum(voice_minutes)

        # tops
        top_msgs  = sorted([c for c in channel if c.get("msg_count")],    key=lambda x: x["msg_count"], reverse=True)[:3]
        top_voice = sorted([c for c in channel if c.get("voice_seconds")], key=lambda x: x["voice_seconds"], reverse=True)[:3]

        # Generer graphique
        fig, ax = plt.subplots(figsize=(10,3), facecolor=BG_RGB)
        ax.plot(dates, msg_counts,    color=BLUE_RGB, linewidth=2)
        ax.fill_between(dates, msg_counts,    color=BLUE_RGB, alpha=0.3)
        ax.plot(dates, voice_minutes, color=PINK_RGB, linewidth=2)
        ax.fill_between(dates, voice_minutes, color=PINK_RGB, alpha=0.3)
        ax.set_facecolor(PANEL_RGB)
        ax.grid(True, color=GRID_COLOR, linestyle='--', linewidth=0.5)
        ax.set_title("Activité sur 30 jours", color=TEXT_RGB, pad=10)
        # ticks
        ticks = dates[::5]
        ax.set_xticks(ticks)
        ax.set_xticklabels([d.strftime('%b %d') for d in ticks], rotation=45, color=TEXT_RGB)
        ax.tick_params(axis='y', colors=TEXT_RGB)
        ax.tick_params(axis='x', colors=TEXT_RGB)
        legend = ax.legend(["Messages","Activité vocale"], loc='upper center', bbox_to_anchor=(0.5,1.15), ncol=2, frameon=False)
        for text in legend.get_texts():
            text.set_color(TEXT_RGB)

        buf_graph = io.BytesIO()
        plt.savefig(buf_graph, format='PNG', dpi=100, bbox_inches='tight', transparent=True)
        plt.close(fig)
        buf_graph.seek(0)
        graph_img = Image.open(buf_graph)

        # Canvas
        canvas = Image.new('RGB', (WIDTH, HEIGHT), BG_COLOR)
        draw   = ImageDraw.Draw(canvas)
        # fonts
        head_f     = ImageFont.truetype(FONT_PATH, 32)
        txt_f      = ImageFont.truetype(FONT_PATH, 18)
        small_f    = ImageFont.truetype(FONT_PATH, 14)
        subtitle_f = ImageFont.truetype(FONT_PATH, 16)

        # header
        avatar_bytes = await member.display_avatar.read()
        av = Image.open(io.BytesIO(avatar_bytes)).resize((64,64)).convert('RGBA')
        mask = Image.new('L', (64,64), 0)
        ImageDraw.Draw(mask).ellipse((0,0,64,64), fill=255)
        canvas.paste(av, (20,20), mask)
        draw.text((100, 25), str(member), font=head_f, fill=TEXT_COLOR)
        draw.text((100, 60), "Made in free", font=subtitle_f, fill=SUBTEXT_COLOR)
        # metrics top-right
        draw.text((800, 25), str(total_msgs), font=head_f, fill=TEXT_COLOR)
        draw.text((800, 60), "Messages", font=subtitle_f, fill=SUBTEXT_COLOR)
        draw.text((920, 25), f"{total_voice} min", font=head_f, fill=TEXT_COLOR)
        draw.text((920, 60), "Activité vocale", font=subtitle_f, fill=SUBTEXT_COLOR)

        # coller graph
        canvas.paste(graph_img, (20,100), graph_img)

        # panels hauts
        panels = [
            ("🏆 Vocaux", top_voice, lambda c: f"{c['voice_seconds']//60} min", BLUE),
            ("💬 Messages", top_msgs, lambda c: f"{c['msg_count']} msgs", PINK),
        ]
        x0, y0, w, h = 20, 330, 490, 130
        for idx, (title, items, fmt, color) in enumerate(panels):
            x = x0 + idx*(w+24)
            draw.rectangle((x,y0,x+w,y0+h), fill=PANEL_BG)
            draw.rectangle((x,y0,x+4,y0+h), fill=color)
            draw.text((x+10, y0+10), title, font=txt_f, fill=TEXT_COLOR)
            for i, doc in enumerate(items):
                chan = guild.get_channel(doc['channel_id'])
                name = chan.name if chan else f"#{doc['channel_id']}"
                draw.text((x+10, y0+40+i*30), f"{i+1}. {name}", font=small_f, fill=TEXT_COLOR)
                draw.text((x+w-120, y0+40+i*30), fmt(doc), font=small_f, fill=SUBTEXT_COLOR)

        # panels bas
        def sum_p(m,n): return sum(m.get((today-datetime.timedelta(days=i)).isoformat(),0) for i in range(n))
        m1,m7,m14 = sum_p(msg_map,1), sum_p(msg_map,7), sum_p(msg_map,14)
        v1,v7,v14 = sum_p(voice_map,1), sum_p(voice_map,7), sum_p(voice_map,14)
        bottom = [
            ("🔊 Vocale", [("1j", v1, "min"),("7j", v7, "min"),("14j", v14, "min")]),
            ("✉️ Messages", [("1j", m1, "msgs"),("7j", m7, "msgs"),("14j", m14, "msgs")])
        ]
        y1 = y0 + h + 20
        for idx, (title, rows) in enumerate(bottom):
            x = x0 + idx*(w+24)
            draw.rectangle((x,y1,x+w,y1+h), fill=PANEL_BG)
            draw.rectangle((x,y1,x+4,y1+h), fill=PINK)
            draw.text((x+10,y1+10), title, font=txt_f, fill=TEXT_COLOR)
            for j, (lbl,val,unit) in enumerate(rows):
                draw.text((x+10,y1+40+j*30), lbl, font=small_f, fill=TEXT_COLOR)
                draw.text((x+w-120,y1+40+j*30), f"{val} {unit}", font=small_f, fill=SUBTEXT_COLOR)

        # envoi
        buf = io.BytesIO()
        canvas.save(buf, 'PNG')
        buf.seek(0)
        await interaction.followup.send(file=discord.File(buf, 'stats.png'))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemberStats(bot))
