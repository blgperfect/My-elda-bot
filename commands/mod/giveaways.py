                # Planifier la fin automatique
                async def finish_giveaway():
                    await asyncio.sleep(duration_delta.total_seconds())
                    # Tirage final
                    parts = data["participants"]
                    if len(parts) < data["winners"]:
                        await chan.send("⚠️ Giveaway terminé, pas assez de participants.")
                        # Conserver juste reroll
                        try:
                            await msg.edit(view=view.make_reroll_only())
                        except discord.NotFound:
                            pass
                        return
                    winners = random.sample(parts, data["winners"])
                    mentions = " ".join(f"<@{w}>" for w in winners)
                    await chan.send(f"🎊 {mentions}, félicitations !")
                    # Mise à jour embed
                    embed_fin = msg.embeds[0]
                    embed_fin.add_field(name="🎊 Gagnants", value=mentions, inline=False)
                    try:
                        await msg.edit(embed=embed_fin, view=view.make_reroll_only())
                    except discord.NotFound:
                        pass
                    await giveaways_collection.update_one({"_id": data["_id"]}, {"$set": {"winners_list": winners}})

                asyncio.create_task(finish_giveaway())

        select_view = View(timeout=None)
        select_view.add_item(ChannelSelectView())
        await interaction.channel.send(f"{interaction.user.mention}, choisis le salon :", view=select_view)


class GiveawayView(View):
    def __init__(self, data: dict, end_time: datetime):
        super().__init__(timeout=None)
        self.data = data
        self.end_time = end_time
        # Bouton participer
        raw = data.get("button_label", "Participer")
        label, emoji = parse_label_and_emoji(raw)
        part_btn = Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary, custom_id="giveaway_participate")
        part_btn.callback = self.participate
        self.add_item(part_btn)
        # Annuler
        cancel_btn = Button(label="Annuler", style=discord.ButtonStyle.danger, custom_id="giveaway_cancel")
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)
        # Reroll
        reroll_btn = Button(label="Reroll", style=discord.ButtonStyle.secondary, custom_id="giveaway_reroll")
        reroll_btn.callback = self.reroll
        self.add_item(reroll_btn)
        # Tirage immédiat
        draw_btn = Button(label="Tirer Maintenant", style=discord.ButtonStyle.success, custom_id="giveaway_draw")
        draw_btn.callback = self.draw_now
        self.add_item(draw_btn)

    def make_reroll_only(self) -> View:
        view = View(timeout=None)
        btn = Button(label="Reroll", style=discord.ButtonStyle.secondary, custom_id="giveaway_reroll")
        btn.callback = self.reroll
        view.add_item(btn)
        return view

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id", "")
        if cid in ("giveaway_cancel", "giveaway_reroll", "giveaway_draw") and not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
            return False
        return True

    async def participate(self, interaction: discord.Interaction):
        uid = interaction.user.id
        parts = self.data["participants"]
        if uid in parts:
            parts.remove(uid)
            await interaction.response.send_message("❌ Participation retirée.", ephemeral=True)
        else:
            parts.append(uid)
            await interaction.response.send_message("✅ Participation ajoutée.", ephemeral=True)
        await giveaways_collection.update_one({"_id": self.data["_id"]}, {"$set": {"participants": parts}})
        # Maj embed
        msg = interaction.message
        ts = int(self.end_time.timestamp())
        embed = msg.embeds[0]
        embed.description = (
            f"Récompense : **{self.data['reward']}**\n"
            f"Gagnants : **{self.data['winners']}**\n"
            f"Participants : **{len(parts)}**\n"
            f"Fin dans : <t:{ts}:R>"
        )
        await msg.edit(embed=embed)

    async def cancel(self, interaction: discord.Interaction):
        await interaction.message.delete()
        await giveaways_collection.delete_one({"_id": self.data["_id"]})
        await interaction.response.send_message("🚫 Giveaway annulé.", ephemeral=True)

    async def reroll(self, interaction: discord.Interaction):
        parts = self.data.get("participants", [])
        if not parts:
            return await interaction.response.send_message("⚠️ Aucun participant.", ephemeral=True)
        winner = random.choice(parts)
        await interaction.response.send_message(f"🎉 <@{winner}>, tu as gagné !", ephemeral=False)

    async def draw_now(self, interaction: discord.Interaction):
        parts = self.data.get("participants", [])
        if len(parts) < self.data["winners"]:
            return await interaction.response.send_message("⚠️ Pas assez de participants.", ephemeral=True)
        winners = random.sample(parts, self.data["winners"])
        mentions = " ".join(f"<@{w}>" for w in winners)
        await interaction.channel.send(f"🎊 {mentions}, félicitations !")
        # Maj embed
        msg = interaction.message
        embed = msg.embeds[0]
        embed.add_field(name="🎊 Gagnants", value=mentions, inline=False)
        await msg.edit(embed=embed, view=self.make_reroll_only())
        await giveaways_collection.update_one({"_id": self.data["_id"]}, {"$set": {"winners_list": winners}})
        await interaction.response.send_message("✅ Tirage effectué.", ephemeral=True)


class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_expired.start()

    @tasks.loop(seconds=60)
    async def cleanup_expired(self):
        now = datetime.now(timezone.utc)
        async for gw in giveaways_collection.find({}):
            created = gw.get("created_at")
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            try:
                end = created + parse_duration(gw["duration"])
            except Exception:
                continue
            if end < now:
                await giveaways_collection.delete_one({"_id": gw["_id"]})

    @cleanup_expired.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="giveaway", description="Créer un nouveau giveaway")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def giveaway(self, interaction: discord.Interaction):
        await interaction.response.send_modal(GiveawayModal())

async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))
