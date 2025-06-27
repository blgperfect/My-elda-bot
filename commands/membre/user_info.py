# commands/userinfo.py
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

        # Bouton suivant / précédent si plusieurs pages
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
            view: UserInfoView = self.view  # type: ignore
            view.index = (view.index + 1) % len(view.embeds)
            embed = view.embeds[view.index]

            # Change l’emoji pour indiquer retour
            if view.index == 0:
                self.emoji = EMOJIS.get("ARROW", "➡️")
            else:
                self.emoji = EMOJIS.get("BACK", "⬅️")

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
        target = member or interaction.user

        # Récupère bannière (profil principal)
        try:
            user_obj = await self.bot.fetch_user(target.id)
            banner = user_obj.banner.url if user_obj.banner else None
        except Exception:
            banner = None

        # Prépare les champs de la page 1
        embed1 = discord.Embed(
            title=f"Information de {target.mention}",
            color=EMBED_COLOR
        )
        embed1.set_thumbnail(url=target.display_avatar.url)
        if banner:
            embed1.set_image(url=banner)
        embed1.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)

        # Display name & date de création du compte
        embed1.add_field(
            name="Display Name",
            value=target.display_name,
            inline=True
        )
        embed1.add_field(
            name="Date de création",
            value=target.created_at.strftime("%d %B %Y"),
            inline=True
        )

        # Date de join & status
        status = str(target.status).capitalize() if target.status and target.status != discord.Status.offline else "—"
        embed1.add_field(
            name="Rejoint le serveur",
            value=target.joined_at.strftime("%d %B %Y"),
            inline=True
        )
        embed1.add_field(
            name="Statut",
            value=status,
            inline=True
        )

        # Badges
        badges = [flag.name for flag in target.public_flags.all()]
        if badges:
            badge_list = " ".join(f"`{b}`" for b in badges)
        else:
            badge_list = "Cette personne n'a pas de badge"
        embed1.add_field(
            name="Badge(s)",
            value=badge_list,
            inline=False
        )

        # Prépare la page 2 : dernier message & dernier rôle
        # Dernier message (scan rapide dans les channels où le bot peut lire)
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

        # Dernier rôle ajouté (audit logs)
        last_role = None
        async for entry in interaction.guild.audit_logs(limit=100, action=discord.AuditLogAction.member_role_update):
            if entry.target.id == target.id:
                for change in entry.changes:
                    if change.key == "roles":
                        old = set(change.before)
                        new = set(change.after)
                        added = new - old
                        if added:
                            last_role = interaction.guild.get_role(added.pop())
                break

        embed2 = discord.Embed(
            title="Historique de l'utilisateur",
            color=EMBED_COLOR
        )
        embed2.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        if last_msg:
            embed2.add_field(
                name="Dernier message",
                value=(
                    f"> {last_msg.content}\n"
                    f"*Le {last_msg.created_at.strftime('%d %B %Y à %H:%M')}*"
                ),
                inline=False
            )
        else:
            embed2.add_field(
                name="Dernier message",
                value="Impossible de récupérer le dernier message.",
                inline=False
            )

        embed2.add_field(
            name="Dernier rôle reçu",
            value=last_role.name if last_role else "Aucun",
            inline=False
        )

        # URL du profil Discord
        profile_url = f"https://discord.com/users/{target.id}"
        view = UserInfoView([embed1, embed2], profile_url)

        await interaction.response.send_message(embed=embed1, view=view)
        # Récupère ensuite le message pour la gestion du timeout
        view.message = await interaction.original_response()

async def setup(bot: commands.Bot):
    await bot.add_cog(UserInfo(bot))
