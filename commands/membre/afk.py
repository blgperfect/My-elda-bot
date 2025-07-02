import discord
from discord.ext import commands
from discord import app_commands, Embed
from discord.ui import View, button, Button
from datetime import datetime
from typing import Optional

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
from config.mongo import afk_collection

class AFKListView(View):
    def __init__(self, pages: list[list[str]]):
        super().__init__(timeout=180)
        self.pages = pages
        self.current = 0

    def make_embed(self, guild: discord.Guild) -> Embed:
        embed = Embed(
            title=f"Membres AFK — {guild.name}",
            color=EMBED_COLOR
        )
        if not self.pages or not self.pages[0]:
            embed.description = "Aucun membre n'est AFK."
        else:
            embed.description = "\n".join(self.pages[self.current])
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        return embed

    @button(label="⬅️", style=discord.ButtonStyle.grey)
    async def previous(self, interaction: discord.Interaction, button: Button):
        if not self.pages:
            return
        self.current = (self.current - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.make_embed(interaction.guild), view=self)

    @button(label="➡️", style=discord.ButtonStyle.grey)
    async def next(self, interaction: discord.Interaction, button: Button):
        if not self.pages:
            return
        self.current = (self.current + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.make_embed(interaction.guild), view=self)

class AFK(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    afk = app_commands.Group(name="afk", description="Commandes AFK")

    @afk.command(name="set", description="Définir votre statut AFK")
    @app_commands.describe(reason="Raison du AFK (optionnel)")
    async def set(self, interaction: discord.Interaction, reason: Optional[str] = None):
        guild = interaction.guild
        user = interaction.user

        # 1) Vérifier si déjà AFK
        existing = await afk_collection.find_one({"guild_id": guild.id, "user_id": user.id})
        if existing:
            embed = Embed(
                title=MESSAGES.get('afk_error_title', 'Erreur AFK'),
                description=MESSAGES.get('afk_already_set', 'Vous êtes déjà en mode AFK.'),
                color=discord.Color.red()
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 2) Vérifier longueur de la raison
        if reason and len(reason) > 256:
            embed = Embed(
                title=MESSAGES.get('afk_error_title', 'Erreur AFK'),
                description=MESSAGES.get('afk_reason_too_long', 'La raison est trop longue (max 256 caractères).'),
                color=discord.Color.red()
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 3) Enregistrer en base
        original_nick = user.display_name
        now = datetime.utcnow()
        try:
            await afk_collection.update_one(
                {"guild_id": guild.id, "user_id": user.id},
                {"$set": {
                    "reason": reason,
                    "original_nickname": original_nick,
                    "start_time": now
                }},
                upsert=True
            )
        except Exception:
            embed = Embed(
                title=MESSAGES.get('afk_error_title', 'Erreur AFK'),
                description=MESSAGES.get('afk_db_error', 'Impossible d’enregistrer votre statut AFK.'),
                color=discord.Color.red()
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 4) Changer le pseudo si permission
        me = guild.me or guild.get_member(self.bot.user.id)
        if not me.guild_permissions.manage_nicknames:
            embed = Embed(
                title=MESSAGES.get('afk_error_title', 'Erreur AFK'),
                description=MESSAGES.get('afk_no_perm_nick', 'Je n’ai pas la permission de modifier les pseudos.'),
                color=discord.Color.red()
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await guild.get_member(user.id).edit(nick=f"⚠️[AFK] {original_nick}")
        except Exception:
            pass

        # 5) Confirmation AFK
        embed = Embed(
            title=MESSAGES.get('afk_set_title', 'Vous êtes maintenant AFK'),
            description=f"{EMOJIS.get('afk', '')} {user.mention} {MESSAGES.get('afk_set_desc', 'est maintenant AFK !')}",
            color=EMBED_COLOR
        )
        embed.add_field(
            name=MESSAGES.get('afk_reason_label', 'Raison'),
            value=reason or MESSAGES.get('afk_no_reason', 'Aucune raison mentionnée'),
            inline=False
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await interaction.response.send_message(embed=embed)

    @afk.command(name="list", description="Liste des membres AFK")
    async def list(self, interaction: discord.Interaction):
        guild = interaction.guild
        try:
            docs = await afk_collection.find({"guild_id": guild.id}).to_list(length=None)
        except Exception:
            embed = Embed(
                title=MESSAGES.get('afk_error_title', 'Erreur AFK'),
                description=MESSAGES.get('afk_db_error', 'Impossible de récupérer la liste AFK.'),
                color=discord.Color.red()
            )
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        entries = []
        for d in docs:
            member = guild.get_member(d['user_id'])
            if member:
                reason = d.get('reason') or MESSAGES.get('afk_no_reason', 'Aucune raison mentionnée')
                entries.append(f"{member.mention} — {reason}")
        pages = [entries[i:i+10] for i in range(0, len(entries), 10)]
        view = AFKListView(pages)
        embed = view.make_embed(guild)
        await interaction.response.send_message(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild = message.guild
        author = message.author

        # Retour d'AFK
        doc = await afk_collection.find_one({"guild_id": guild.id, "user_id": author.id})
        if doc:
            await afk_collection.delete_one({"guild_id": guild.id, "user_id": author.id})
            try:
                await guild.get_member(author.id).edit(nick=doc.get('original_nickname'))
            except Exception:
                pass

            # Calcul de la durée
            delta = datetime.utcnow() - doc.get('start_time')
            days, rem = divmod(delta.total_seconds(), 86400)
            hours, rem = divmod(rem, 3600)
            mins, _ = divmod(rem, 60)
            parts = [
                f"{int(days)} j" if days else None,
                f"{int(hours)} h" if hours else None,
                f"{int(mins)} min" if mins else None
            ]
            duration = ", ".join([p for p in parts if p]) or MESSAGES.get('afk_short_duration', 'moins d’une minute')

            embed = Embed(
                description=f"{EMOJIS.get('back', '')} {author.mention} {MESSAGES.get('afk_back_desc', 'n’est plus AFK !')}",
                color=EMBED_COLOR
            )
            embed.add_field(name=MESSAGES.get('afk_duration_label', "Durée d'AFK"), value=duration, inline=False)
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await message.channel.send(embed=embed)

        # Mention d'AFK
        for user in message.mentions:
            doc = await afk_collection.find_one({"guild_id": guild.id, "user_id": user.id})
            if doc:
                try:
                    await message.delete()
                except Exception:
                    pass
                embed = Embed(
                    description=f"{EMOJIS.get('warning', '')} {user.mention} {MESSAGES.get('afk_mention_desc', 'est actuellement AFK')}",
                    color=EMBED_COLOR
                )
                embed.add_field(
                    name=MESSAGES.get('afk_reason_label', 'Raison'),
                    value=doc.get('reason') or MESSAGES.get('afk_no_reason', 'Aucune raison mentionnée'),
                    inline=False
                )
                embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
                await message.channel.send(embed=embed)
                break

async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
