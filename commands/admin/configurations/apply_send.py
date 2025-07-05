# cogs/apply_send.py

import discord
from discord import app_commands
from discord.ext import commands
from config.mongo import apply_collection
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
    APPLICATION_QUESTIONS
)

class ApplySendView(discord.ui.View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        self.cfg = cfg
        self.add_item(self.PostSelect(cfg["applications_enabled"]))

    class PostSelect(discord.ui.Select):
        def __init__(self, apps: list[str]):
            options = [discord.SelectOption(label=app, value=app) for app in apps]
            super().__init__(
                placeholder="Choisissez un poste…",
                options=options,
                custom_id="apply_modal"
            )

        async def callback(self, interaction: discord.Interaction):
            app_name = self.values[0]
            questions = APPLICATION_QUESTIONS[app_name]

            class AppModal(discord.ui.Modal, title=f"Candidature — {app_name}"):
                def __init__(modal_self):
                    super().__init__()
                    for key, text, mx in questions:
                        label = text if len(text) <= 45 else text[:42].rstrip() + "..."
                        modal_self.add_item(discord.ui.TextInput(
                            label=label,
                            style=discord.TextStyle.paragraph,
                            custom_id=key,
                            placeholder="Votre réponse…",
                            max_length=mx
                        ))

                async def callback(modal_self, modal_inter: discord.Interaction):
                    answers = {c.custom_id: c.value for c in modal_self.children}
                    doc = {
                        "server_id": interaction.guild.id,
                        "user_id": interaction.user.id,
                        "app_name": app_name,
                        "answers": answers,
                        "status": "pending",
                        "timestamp": discord.utils.utcnow()
                    }
                    res = await apply_collection.insert_one(doc)

                    eb = discord.Embed(
                        title=f"Nouvelle candidature — {app_name}",
                        description=f"Membre : {interaction.user.mention}",
                        color=EMBED_COLOR
                    )
                    for k, v in answers.items():
                        eb.add_field(name=k.upper(), value=v, inline=False)
                    eb.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

                    view = discord.ui.View(timeout=None)
                    view.add_item(discord.ui.Button(
                        label="✅ Accepter",
                        style=discord.ButtonStyle.success,
                        custom_id=f"apply_accept:{res.inserted_id}"
                    ))
                    view.add_item(discord.ui.Button(
                        label="❌ Refuser",
                        style=discord.ButtonStyle.danger,
                        custom_id=f"apply_refuse:{res.inserted_id}"
                    ))

                    cfg2 = await apply_collection.find_one({"server_id": interaction.guild.id})
                    channel = interaction.guild.get_channel(cfg2["channel_id"])
                    await channel.send(embed=eb, view=view)

                    # SEUL message ephemeral
                    await modal_inter.response.send_message(
                        "✅ Ta candidature a bien été envoyée !",
                        ephemeral=True
                    )

            # Envoi du modal sans re-defer
            await interaction.response.send_modal(AppModal())

class ApplyFlowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="apply_send", description="Publie le menu de candidature")
    async def apply_send(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        cfg = await apply_collection.find_one({"server_id": guild_id})
        if not cfg or not cfg.get("applications_enabled"):
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=MESSAGES["NOT_CONFIGURED"],
                    color=EMBED_COLOR
                )
            )

        embed = discord.Embed(
            title="📋 Menu de candidature",
            description="Sélectionnez le poste pour lequel vous souhaitez postuler :",
            color=EMBED_COLOR
        )
        for app in cfg["applications_enabled"]:
            embed.add_field(name=app, value=EMOJIS.get(app, "📝"), inline=True)

        view = ApplySendView(cfg)
        # PUBLIC : pas d’ephemeral
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(ApplyFlowCog(bot))
