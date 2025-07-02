import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from bson import ObjectId

from config.mongo import challenges_collection
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES
)

# Emojis
EMOJIS = {"participate": "✅", "finish": "⏱️"}


class SubmissionModal(discord.ui.Modal, title="Soumettre une participation"):
    url = discord.ui.TextInput(
        label="URL de l'image",
        style=discord.TextStyle.short,
        required=False
    )
    description = discord.ui.TextInput(
        label="Description (optionnel)",
        style=discord.TextStyle.paragraph,
        required=False
    )

    def __init__(self, challenge_id: ObjectId, thread: discord.Thread):
        super().__init__()
        self.challenge_id = challenge_id
        self.thread = thread

    async def on_submit(self, interaction: discord.Interaction):
        if not (self.url.value or self.description.value):
            return await interaction.response.send_message(
                "Vous devez fournir une URL ou une description.", ephemeral=True
            )
        sub = {
            "submission_id": ObjectId(),
            "author_id": str(interaction.user.id),
            "url": self.url.value,
            "description": self.description.value,
            "votes": []
        }
        await challenges_collection.update_one(
            {"_id": self.challenge_id},
            {"$push": {"submissions": sub}}
        )
        embed_desc = f"Par <@{interaction.user.id}>"
        if sub["description"]:
            embed_desc += f"\n{sub['description']}"
        embed = discord.Embed(
            title="Nouvelle participation",
            description=embed_desc,
            color=EMBED_COLOR
        )
        if sub["url"]:
            embed.set_image(url=sub["url"])
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Voter",
            custom_id=f"vote_{sub['submission_id']}",
            style=discord.ButtonStyle.secondary
        ))
        await self.thread.send(embed=embed, view=view)
        await interaction.response.send_message(
            MESSAGES.get("submit_success", "Participation enregistrée !"),
            ephemeral=True
        )


class ChallengeView(discord.ui.View):
    def __init__(self, challenge_id: ObjectId, thread: discord.Thread):
        super().__init__(timeout=None)
        self.challenge_id = challenge_id
        self.thread = thread

    @discord.ui.button(label="Participer", style=discord.ButtonStyle.primary, custom_id="challenge_participate")
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SubmissionModal(self.challenge_id, self.thread))

    @discord.ui.button(label="Finir Maintenant", style=discord.ButtonStyle.danger, custom_id="challenge_finish")
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        await self._finish(interaction)
        await interaction.response.defer()

    async def _finish(self, interaction: discord.Interaction):
        await interaction.client.get_cog("Challenge")._finish_challenge(
            interaction, self.challenge_id, self.thread
        )


class Challenge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_deadlines.start()

    def cog_unload(self):
        self.check_deadlines.cancel()

    @tasks.loop(minutes=1)
    async def check_deadlines(self):
        now = datetime.utcnow()
        expired = await challenges_collection.find({"deadline": {"$lte": now}}).to_list(100)
        for chal in expired:
            channel = self.bot.get_channel(chal["channel_id"])
            thread = discord.utils.get(channel.threads, id=chal["thread_id"])
            await self._finish_challenge(None, chal["_id"], thread)

    async def _finish_challenge(self, interaction: discord.Interaction, challenge_id: ObjectId, thread: discord.Thread):
        chal = await challenges_collection.find_one({"_id": challenge_id})
        subs = chal.get("submissions", [])
        ranked = sorted(subs, key=lambda s: len(s["votes"]), reverse=True)[:3]
        medals = ["🥇", "🥈", "🥉"]
        desc_lines = []
        for i, r in enumerate(ranked):
            desc_lines.append(f"{medals[i]} <@{r['author_id']}> — {len(r['votes'])} votes")
        desc = "\n".join(desc_lines) or "Aucune participation."
        original = await thread.parent.fetch_message(chal["message_id"])
        await original.edit(
            embed=discord.Embed(
                title=f"Challenge {chal['name']} terminé",
                description=desc,
                color=EMBED_COLOR
            )
        )
        await thread.edit(locked=True, archived=True)
        await challenges_collection.delete_one({"_id": challenge_id})

    @app_commands.guild_only()
    @app_commands.command(name="challenge_create", description="Créer un challenge")
    @app_commands.describe(
        channel="Salon pour le challenge",
        nom="Nom du challenge",
        deadline="Durée avant expiration (m,h,d,w)"
    )
    async def create(self, interaction: discord.Interaction,
                     channel: discord.TextChannel, nom: str, deadline: str):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        unit = deadline[-1]; qty = int(deadline[:-1])
        arg_map = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
        deadline_dt = datetime.utcnow() + timedelta(**{arg_map[unit]: qty})
        chal_doc = {"name": nom, "deadline": deadline_dt, "submissions": []}
        res = await challenges_collection.insert_one(chal_doc)
        chal_id = res.inserted_id
        embed = discord.Embed(
            title=f"Challenge {nom} {EMOJIS['participate']}",
            description=(
                f"Deadline: {deadline_dt:%Y-%m-%d %H:%M}\n"
                "Cliquez sur Participer pour soumettre."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        msg = await channel.send(embed=embed)
        thread = await channel.create_thread(name="participations", message=msg)
        await challenges_collection.update_one(
            {"_id": chal_id},
            {"$set": {"channel_id": channel.id, "thread_id": thread.id, "message_id": msg.id}}
        )
        await msg.edit(view=ChallengeView(chal_id, thread))
        await interaction.response.send_message("Challenge créé !", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="challenge_list", description="Lister les challenges actifs")
    async def list(self, interaction: discord.Interaction):
        docs = await challenges_collection.find().to_list(50)
        embed = discord.Embed(title="Challenges actifs", color=EMBED_COLOR)
        for c in docs:
            ch = self.bot.get_channel(c["channel_id"])
            embed.add_field(
                name=c["name"],
                value=f"Salon: {ch.mention} | Deadline: {c['deadline']:%Y-%m-%d %H:%M}"
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Challenge(bot))
