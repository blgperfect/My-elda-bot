# commands/admin/inviteinfo.py

import re
import discord
from discord import app_commands
from discord.ext import commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, EMOJIS


class InviteInfoView(discord.ui.View):
    def __init__(
        self,
        embeds: list[discord.Embed],
        invite_url: str,
        icon_url: str | None = None,
        banner_url: str | None = None,
        splash_url: str | None = None
    ):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.index = 0

        # Bouton : lien d'invitation
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Lien d'invitation",
            url=invite_url
        ))

        # Bouton : icône du serveur
        if icon_url:
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Icône du serveur",
                url=icon_url
            ))

        # Bouton : bannière du serveur
        if banner_url:
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Bannière du serveur",
                url=banner_url
            ))

        # Bouton : splash (si existant)
        if splash_url:
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Splash du serveur",
                url=splash_url
            ))

        # Pagination si plus d'un embed
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
            view: InviteInfoView = self.view  # type: ignore
            view.index = (view.index + 1) % len(view.embeds)
            embed = view.embeds[view.index]
            # Alterner l'emoji entre → et ←
            self.emoji = (
                EMOJIS.get("BACK", "⬅️") if view.index else EMOJIS.get("ARROW", "➡️")
            )
            await interaction.response.edit_message(embed=embed, view=view)


class InviteInfo(commands.Cog):
    """Affiche les informations d'un serveur via un lien d'invitation Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="inviteinfo",
        description="Récupère les infos d'un serveur à partir d'un lien d'invitation."
    )
    @app_commands.describe(invite_link="Le lien d'invitation Discord (ex : discord.gg/abc123)")
    async def inviteinfo(
        self,
        interaction: discord.Interaction,
        invite_link: str
    ):
        await interaction.response.defer(ephemeral=False)

        # ── Nettoyage et extraction du code d'invite ──────────────────────────
        clean = invite_link.rstrip("/").split("?", 1)[0]
        match = re.search(
            r"(?:https?://)?(?:www\.)?"
            r"(?:discord(?:app)?\.com/invite|discord\.gg)"
            r"/([A-Za-z0-9-]+)",
            clean
        )
        if not match:
            await interaction.followup.send("❌ Lien d'invitation invalide.", ephemeral=True)
            return

        code = match.group(1)

        # ── Fetch de l'invite via l'API Discord ───────────────────────────────
        try:
            invite = await self.bot.fetch_invite(
                code,
                with_counts=True,
                with_expiration=True
            )
        except discord.NotFound:
            await interaction.followup.send("❌ Invitation non trouvée ou expirée.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Erreur lors de la récupération : {e}", ephemeral=True)
            return

        guild = invite.guild  # PartialInviteGuild

        # ── EMBED 1 : Infos générales du serveur ──────────────────────────────
        embed1 = discord.Embed(
            title=f"🏷️ {guild.name}",
            description=guild.description or "_Pas de description_",
            color=EMBED_COLOR
        )
        if guild.icon:
            embed1.set_thumbnail(url=guild.icon.url)
        embed1.add_field(name="🆔 ID du serveur", value=guild.id, inline=True)
        embed1.add_field(name="💬 Salon cible", value=invite.channel.name, inline=True)
        embed1.add_field(
            name="👑 Créé le",
            value=(
                guild.created_at.strftime("%d %B %Y")
                if hasattr(guild, "created_at") else "N/A"
            ),
            inline=True
        )
        embed1.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # ── EMBED 2 : Statistiques & invitation ───────────────────────────────
        embed2 = discord.Embed(
            title="📊 Statistiques d'invitation",
            color=EMBED_COLOR
        )
        embed2.add_field(
            name="👥 Membres approximatifs",
            value=invite.approximate_member_count or "N/A",
            inline=True
        )
        embed2.add_field(
            name="📶 En ligne approximativement",
            value=invite.approximate_presence_count or "N/A",
            inline=True
        )
        embed2.add_field(
            name="⏳ Expiration",
            value=(
                invite.expires_at.strftime("%d %B %Y à %H:%M")
                if invite.expires_at else "Jamais"
            ),
            inline=True
        )
        embed2.add_field(
            name="🚀 Utilisations",
            value=f"{invite.uses or 0}/{invite.max_uses or '∞'}",
            inline=True
        )
        embed2.add_field(
            name="🛡️ Temporary",
            value=str(invite.temporary),
            inline=True
        )
        embed2.add_field(
            name="🏷️ Features",
            value=", ".join(guild.features) if guild.features else "Aucune",
            inline=False
        )
        embed2.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # ── Préparation des URLs pour les boutons ────────────────────────────
        invite_url = f"https://discord.gg/{invite.code}"
        icon_url   = guild.icon.url   if guild.icon else None
        banner_url = getattr(guild, "banner", None)
        if banner_url:
            banner_url = banner_url.url
        splash_url = getattr(guild, "splash", None)
        if splash_url:
            splash_url = splash_url.url

        # ── Envoi avec pagination et boutons ────────────────────────────────
        view = InviteInfoView(
            embeds=[embed1, embed2],
            invite_url=invite_url,
            icon_url=icon_url,
            banner_url=banner_url,
            splash_url=splash_url
        )
        await interaction.followup.send(embed=embed1, view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteInfo(bot))
