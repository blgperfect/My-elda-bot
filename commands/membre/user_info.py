import discord
from discord import app_commands
from discord.ext import commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL, EMOJIS


class UserInfoView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], profile_url: str):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.index = 0

        # Bouton lien vers le profil Discord
        self.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Profil du membre",
            url=profile_url
        ))

        # Pagination si plusieurs pages
        if len(embeds) > 1:
            self.add_item(self.NextButton())

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                emoji=EMOJIS.get("ARROW", "➡️")
            )

        async def callback(self, interaction: discord.Interaction):
            view: UserInfoView = self.view  # type: ignore
            view.index = (view.index + 1) % len(view.embeds)
            embed = view.embeds[view.index]
            # Alterne l'emoji pour la pagination
            self.emoji = (
                EMOJIS.get("BACK", "⬅️") if view.index else EMOJIS.get("ARROW", "➡️")
            )
            await interaction.response.edit_message(embed=embed, view=view)


class UserInfo(commands.Cog):
    """Commande slash /userinfo pour afficher les informations d'un membre."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="userinfo",
        description="Affiche les informations d'un membre."
    )
    @app_commands.describe(member="Le membre dont vous voulez afficher les infos")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None
    ):
        # Ack rapide pour éviter le timeout Discord
        await interaction.response.defer(thinking=True)

        target = member or interaction.user

        # ── Bannière (profil principal) ───────────────────────────────────────
        banner_url: str | None = None
        try:
            user_obj = await self.bot.fetch_user(target.id)
            banner_url = user_obj.banner.url if user_obj.banner else None
        except Exception:
            pass

        # ── Statut personnalisé (Custom Activity) ─────────────────────────────
        custom_status: str | None = None
        for act in target.activities:
            if getattr(act, "type", None) == discord.ActivityType.custom:
                custom_status = act.name
                break

        # ── EMBED 1 : Informations principales ─────────────────────────────────
        embed1 = discord.Embed(
            title=f"🔍 Informations de {target}",
            color=EMBED_COLOR
        )
        embed1.set_thumbnail(url=target.display_avatar.url)
        if banner_url:
            embed1.set_image(url=banner_url)
        embed1.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        embed1.add_field(
            name="👤 Display Name",
            value=target.display_name,
            inline=True
        )
        embed1.add_field(
            name="📅 Création du compte",
            value=target.created_at.strftime("%d %B %Y"),
            inline=True
        )
        embed1.add_field(
            name="🚪 Rejoint le serveur",
            value=target.joined_at.strftime("%d %B %Y"),
            inline=True
        )
        if custom_status:
            embed1.add_field(
                name="⭐ Statut perso",
                value=custom_status,
                inline=False
            )

        # ── EMBED 2 : Historique (dernier message) ──────────────────────────────
        last_msg = None
        for chan in interaction.guild.text_channels:
            if chan.permissions_for(interaction.guild.me).read_message_history:
                try:
                    async for msg in chan.history(limit=100):
                        if msg.author.id == target.id:
                            last_msg = msg
                            break
                except Exception:
                    continue
            if last_msg:
                break

        embed2 = discord.Embed(
            title="📜 Dernier message",
            color=EMBED_COLOR
        )
        embed2.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        if last_msg and last_msg.content:
            embed2.add_field(
                name="Contenu",
                value=(
                    f"> {last_msg.content}\n"
                    f"*Le {last_msg.created_at.strftime('%d %B %Y à %H:%M')}*"
                ),
                inline=False
            )
        else:
            embed2.add_field(
                name="Contenu",
                value="Aucun message récupéré ou lecture interdite.",
                inline=False
            )

        # ── Envoi via followup après defer ──────────────────────────────────────
        profile_url = f"https://discord.com/users/{target.id}"
        view = UserInfoView([embed1, embed2], profile_url)
        message = await interaction.followup.send(embed=embed1, view=view)
        view.message = message


async def setup(bot: commands.Bot):
    await bot.add_cog(UserInfo(bot))
