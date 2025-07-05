import discord
from discord import app_commands
from discord.ext import commands
from config.params import EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL

class Lookup(commands.Cog):
    """Commande slash /lookup qui récupère un user par ID et affiche son profil."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="lookup",
        description="Affiche les infos d'un utilisateur Discord via son ID."
    )
    @app_commands.describe(user_id="L'ID Discord de l'utilisateur à rechercher")
    async def lookup(
        self,
        interaction: discord.Interaction,
        user_id: str
    ):
        await interaction.response.defer(thinking=True)

        # 1. Validation de l'ID
        if not user_id.isdigit():
            await interaction.followup.send("❌ L'ID fourni n'est pas valide.")
            return

        uid = int(user_id)

        # 2. Récupération du User global
        try:
            user_obj = await self.bot.fetch_user(uid)
        except discord.NotFound:
            await interaction.followup.send("❌ Aucun utilisateur trouvé avec cet ID.")
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Erreur lors de la requête : {e}")
            return

        # 3. Récupérer le Member si présent dans la guild
        member_obj = None
        if interaction.guild:
            member_obj = interaction.guild.get_member(uid)

        # 4. Construction de l'embed
        embed = discord.Embed(
            title=f"🔍 Profil de `{user_obj}`",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=user_obj.display_avatar.url)

        # Bannière (si existante)
        try:
            banner = user_obj.banner
            if banner:
                embed.set_image(url=banner.url)
        except Exception:
            pass

        # Champs globaux
        embed.add_field(name="🆔 ID", value=str(user_obj.id), inline=True)
        embed.add_field(
            name="📅 Créé le",
            value=user_obj.created_at.strftime("%d %B %Y"),
            inline=True
        )

        # Champs serveur (si membre)
        if member_obj:
            if member_obj.joined_at:
                embed.add_field(
                    name="🚪 Rejoint le",
                    value=member_obj.joined_at.strftime("%d %B %Y"),
                    inline=True
                )
            roles = [r.mention for r in member_obj.roles if r.name != "@everyone"]
            embed.add_field(
                name="🎖️ Rôles",
                value=", ".join(roles) if roles else "Aucun",
                inline=False
            )

        # Footer et bouton vers le profil web
        profile_url = f"https://discord.com/users/{user_obj.id}"
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Voir sur Discord",
            url=profile_url
        ))

        # 5. Envoi du message
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(Lookup(bot))
