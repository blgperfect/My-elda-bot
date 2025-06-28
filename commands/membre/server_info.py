# commands/admin/serverinfo.py
import discord
from discord import app_commands
from discord.ext import commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, EMOJIS


class ServerInfoView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], icon_url: str | None):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.index = 0

        # Bouton lien vers l'icône du serveur
        if icon_url:
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Icône du serveur",
                url=icon_url
            ))

        # Pagination si plusieurs pages
        if len(embeds) > 1:
            self.next_button = self.NextButton()
            self.add_item(self.next_button)

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                emoji=EMOJIS.get("ARROW", "➡️")
            )

        async def callback(self, interaction: discord.Interaction):
            view: ServerInfoView = self.view  # type: ignore
            view.index = (view.index + 1) % len(view.embeds)
            embed = view.embeds[view.index]
            # Change l'emoji pour indiquer le sens
            if view.index == 0:
                self.emoji = EMOJIS.get("ARROW", "➡️")
            else:
                self.emoji = EMOJIS.get("BACK", "⬅️")
            await interaction.response.edit_message(embed=embed, view=view)


class ServerInfo(commands.Cog):
    """Affiche les informations détaillées du serveur."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="serverinfo",
        description="Affiche les informations du serveur."
    )
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild

        # ── EMBED 1 : Infos générales ─────────────────────────────────────────
        embed1 = discord.Embed(
            title=f"🏷️ {guild.name}",
            description=guild.description or "_Pas de description_",
            color=EMBED_COLOR
        )
        if guild.icon:
            embed1.set_thumbnail(url=guild.icon.url)
        embed1.add_field(
            name="🆔 ID",
            value=guild.id,
            inline=True
        )
        embed1.add_field(
            name="👑 Propriétaire",
            value=guild.owner.mention,
            inline=True
        )
        embed1.add_field(
            name="📅 Créé le",
            value=guild.created_at.strftime("%d %B %Y"),
            inline=True
        )
        embed1.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # ── EMBED 2 : Statistiques ────────────────────────────────────────────
        # Comptage membres
        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots
        # Comptage salons & rôles & emojis/stickers
        txt = len(guild.text_channels)
        voice = len(guild.voice_channels)
        cats = len(guild.categories)
        roles_n = len(guild.roles)
        emojis_n = len(guild.emojis)
        stickers_n = len(guild.stickers)

        embed2 = discord.Embed(
            title="📊 Statistiques du serveur",
            color=EMBED_COLOR
        )
        embed2.add_field(
            name="👥 Membres",
            value=(
                f"Total : **{total}**\n"
                f"Humains : **{humans}**\n"
                f"Bots : **{bots}**"
            ),
            inline=False
        )
        embed2.add_field(
            name="📂 Salons",
            value=(
                f"Textuels : **{txt}**\n"
                f"Vocaux : **{voice}**\n"
                f"Catégories : **{cats}**"
            ),
            inline=False
        )
        embed2.add_field(
            name="🔖 Rôles",
            value=f"{roles_n}",
            inline=True
        )
        embed2.add_field(
            name="😃 Emojis",
            value=f"{emojis_n}",
            inline=True
        )
        embed2.add_field(
            name="🏷️ Stickers",
            value=f"{stickers_n}",
            inline=True
        )
        embed2.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # ── Envoi avec pagination & bouton Icône ─────────────────────────────
        view = ServerInfoView([embed1, embed2], guild.icon.url if guild.icon else None)
        await interaction.response.send_message(embed=embed1, view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerInfo(bot))
