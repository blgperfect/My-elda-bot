import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from bson import ObjectId
from urllib.parse import urlparse

from config.mongo import challenges_collection
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES
)

EMOJIS = {"participate": "✅", "finish": "⏱️"}


def is_valid_image_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    return p.path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))


class SubmissionModal(discord.ui.Modal, title="Soumettre une participation"):
    url = discord.ui.TextInput(label="URL de l'image", style=discord.TextStyle.short, required=False)
    description = discord.ui.TextInput(
        label="Description (optionnel)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000
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

        embed = discord.Embed(title="Nouvelle participation", description=embed_desc, color=EMBED_COLOR)
        if sub["url"] and is_valid_image_url(sub["url"]):
            embed.set_image(url=sub["url"])

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Voter",
            custom_id=f"vote_{sub['submission_id']}",
            style=discord.ButtonStyle.secondary
        ))

        try:
            await self.thread.send(embed=embed, view=view)
        except discord.HTTPException:
            return await interaction.response.send_message(
                "Une erreur est survenue lors de l’envoi de votre participation.", ephemeral=True
            )

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
        user_id = str(interaction.user.id)
        # 1) empêcher participations multiples
        exists = await challenges_collection.count_documents({
            "_id": self.challenge_id,
            "submissions.author_id": user_id
        })
        if exists:
            return await interaction.response.send_message(
                "Vous avez déjà soumis une participation à ce challenge.", ephemeral=True
            )
        # 2) sinon ouvrir le modal
        await interaction.response.send_modal(SubmissionModal(self.challenge_id, self.thread))

    @discord.ui.button(label="Finir Maintenant", style=discord.ButtonStyle.danger, custom_id="challenge_finish")
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)
        # finir le challenge
        await self._finish(interaction)
        # désactiver chaque bouton de cette view
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
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
        expired = await challenges_collection.find({
            "deadline": {"$lte": now},
            "channel_id": {"$exists": True},
            "thread_id": {"$exists": True},
        }).to_list(100)

        for chal in expired:
            channel = self.bot.get_channel(chal["channel_id"])
            thread = discord.utils.get(channel.threads, id=chal["thread_id"])
            await self._finish_challenge(None, chal["_id"], thread)

            # désactiver les boutons du message initial
            original = await thread.parent.fetch_message(chal["message_id"])
            if original.components:
                view = original.view or discord.ui.View.from_message(original)
                for item in view.children:
                    item.disabled = True
                await original.edit(view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        cid = interaction.data.get("custom_id", "")
        if not cid.startswith("vote_"):
            return

        submission_id = ObjectId(cid.split("_", 1)[1])
        user_id = str(interaction.user.id)

        chal = await challenges_collection.find_one({
            "submissions.submission_id": submission_id
        })
        if not chal:
            return await interaction.response.send_message("Participation introuvable.", ephemeral=True)

        sub = next(s for s in chal["submissions"] if s["submission_id"] == submission_id)

        # auto-vote
        if sub["author_id"] == user_id:
            return await interaction.response.send_message(
                "Vous ne pouvez pas voter pour votre propre participation.", ephemeral=True
            )
        # vote multiple
        if user_id in sub["votes"]:
            return await interaction.response.send_message(
                "Vous avez déjà voté pour cette participation.", ephemeral=True
            )

        # enregistrer le vote
        await challenges_collection.update_one(
            {"_id": chal["_id"], "submissions.submission_id": submission_id},
            {"$push": {"submissions.$.votes": user_id}}
        )

        # mettre à jour l’embed
        msg = await interaction.channel.fetch_message(interaction.message.id)
        embed = msg.embeds[0]
        lines = [l for l in embed.description.split("\n") if not l.startswith("Votes")]
        votes_count = len(sub["votes"]) + 1
        lines.append(f"Votes : {votes_count}")
        embed.description = "\n".join(lines)
        await msg.edit(embed=embed)

        await interaction.response.send_message("Votre vote a bien été pris en compte !", ephemeral=True)

    async def _finish_challenge(
        self,
        interaction: discord.Interaction,
        challenge_id: ObjectId,
        thread: discord.Thread
    ):
        chal = await challenges_collection.find_one({"_id": challenge_id})
        subs = chal.get("submissions", [])
        ranked = sorted(subs, key=lambda s: len(s["votes"]), reverse=True)[:3]
        medals = ["🥇", "🥈", "🥉"]
        desc = "\n".join(
            f"{medals[i]} <@{r['author_id']}> — {len(r['votes'])} votes"
            for i, r in enumerate(ranked)
        ) or "Aucune participation."

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
    async def create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        nom: str,
        deadline: str
    ):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("Permission refusée.", ephemeral=True)

        unit = deadline[-1]
        qty = int(deadline[:-1])
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
            {"$set": {
                "channel_id": channel.id,
                "thread_id": thread.id,
                "message_id": msg.id
            }}
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
