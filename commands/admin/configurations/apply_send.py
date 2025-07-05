# cogs/apply_flow.py

import discord
from discord import app_commands
from discord.ext import commands
from config.mongo import apply_collection
from config.params import (
    EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL,
    MESSAGES, EMOJIS, APPLICATION_QUESTIONS
)

class ApplyFlowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="apply_send", description="Publie le menu de candidature")
    async def apply_send(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        # ⚠️ Bien awaiter le find_one
        cfg = await apply_collection.find_one({"server_id": guild_id})
        if not cfg or "channel_id" not in cfg:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=MESSAGES["NOT_CONFIGURED"],
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )

        channel = interaction.guild.get_channel(cfg["channel_id"])
        apps = cfg.get("applications_enabled", [])
        if not apps:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=MESSAGES["NO_APPS_ENABLED"],
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"Application staff — {interaction.guild.name}",
            description="Merci de sélectionner le poste pour lequel vous souhaitez postuler.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        select = discord.ui.Select(
            placeholder="Choisissez un poste",
            options=[discord.SelectOption(label=a, value=a) for a in apps],
            custom_id=f"apply_modal:{guild_id}",
            min_values=1, max_values=1
        )
        view = discord.ui.View(timeout=None)
        view.add_item(select)

        await channel.send(embed=embed, view=view)
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{EMOJIS['CHECK']} Menu publié !",
                color=EMBED_COLOR
            ),
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data
        cid = data.get("custom_id", "")

        # Sélection du poste → Modal
        if data.get("component_type") == 3 and cid.startswith("apply_modal:"):
            guild_id = interaction.guild.id
            app_name = data["values"][0]
            questions = APPLICATION_QUESTIONS[app_name]

            class AppModal(discord.ui.Modal, title=f"Application — {app_name}"):
                def __init__(self):
                    super().__init__()
                    for key, text, mx in questions:
                        self.add_item(discord.ui.TextInput(
                            label=text,
                            style=discord.TextStyle.paragraph,
                            custom_id=key,
                            max_length=mx
                        ))

                async def callback(self, modal_itf: discord.Interaction):
                    answers = {c.custom_id: c.value for c in self.children}
                    doc = {
                        "server_id": guild_id,
                        "user_id": interaction.user.id,
                        "app_name": app_name,
                        "answers": answers,
                        "status": "pending",
                        "timestamp": discord.utils.utcnow()
                    }
                    # ⚠️ await insert
                    res = await apply_collection.insert_one(doc)

                    eb = discord.Embed(
                        title=f"Nouvelle application — {app_name}",
                        description=f"Membre : {interaction.user.mention}",
                        color=EMBED_COLOR
                    )
                    for k, v in answers.items():
                        eb.add_field(name=k, value=v, inline=False)
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

                    # ⚠️ await find_one pour récupérer à nouveau la conf
                    cfg2 = await apply_collection.find_one({"server_id": guild_id})
                    staff_ch = interaction.guild.get_channel(cfg2["channel_id"])
                    await staff_ch.send(embed=eb, view=view)
                    await modal_itf.response.send_message(
                        embed=discord.Embed(
                            description=f"{EMOJIS['CHECK']} Candidature envoyée !",
                            color=EMBED_COLOR
                        ),
                        ephemeral=True
                    )

            return await interaction.response.send_modal(AppModal())

        # Boutons Accept/Refuse
        if data.get("component_type") == 2 and cid.startswith(("apply_accept:", "apply_refuse:")):
            action, app_id = cid.split(":", 1)

            # ⚠️ await find_one
            doc = await apply_collection.find_one({"_id": app_id})
            member = interaction.guild.get_member(doc["user_id"])

            if action == "apply_refuse":
                try:
                    await member.send(MESSAGES["REFUSE_DM"].format(server=interaction.guild.name))
                except discord.Forbidden:
                    await interaction.channel.send(MESSAGES["REFUSE_DM_FAILED"].format(user=member.mention))
                # ⚠️ await update
                await apply_collection.update_one({"_id": app_id}, {"$set": {"status": "refused"}})
                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"{EMOJIS['CROSS']} {member.mention} a été refusé.",
                        color=EMBED_COLOR
                    ),
                    ephemeral=True
                )

            # Accept
            cfg3 = await apply_collection.find_one({"server_id": interaction.guild.id})
            role_id = cfg3["roles_by_app"][doc["app_name"]]
            role = interaction.guild.get_role(role_id)
            await member.add_roles(role, reason="Candidature acceptée")
            # ⚠️ await update
            await apply_collection.update_one({"_id": app_id}, {"$set": {"status": "accepted"}})
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{EMOJIS['CHECK']} Rôle {role.mention} attribué à {member.mention}.",
                    color=EMBED_COLOR
                ),
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ApplyFlowCog(bot))
