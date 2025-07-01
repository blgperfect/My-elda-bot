import discord
from discord.ext import commands
from discord.ui import Button, View

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    EMBED_IMAGE_URL,
    TOPGG,
    SUPPORT_INVITE,
    TUTO_YTB
)

class GuildJoinListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Envoi un message de bienvenue personnalisé avec embed et boutons."""
        # Construction de l’embed
        embed = discord.Embed(
            title="Salut à tous ! 🎉",
            description=(
                f"Merci de m’avoir accueillie sur votre serveur **{guild.name}** !\n\n"
                "👋 **Je m’appelle Elda** (en clin d’œil à Elda Moonwraith 🌙✨), un petit nom tout doux pour une expérience toute mignonne.\n\n"
                "──────────────\n"
                "📚 **Présentation**\n"
                "• Conçue par **xxmissr**, ma mission est d’apporter une touche kawaii à votre serveur grâce à une interface unique.\n"
                "• Je ne suis pas (encore) un bot de modération complète : je ne peux pas assurer la protection totale de votre serveur, mais j’apprends vite !\n\n"
                "──────────────\n"
                "🤖 **À quoi je sers ?**\n"
                "• **Modération légère** : quelques outils pratiques pour garder votre serveur sympa.\n"
                "• **Profils & stats** : crée ton profil, consulte tes statistiques, et bien plus encore !\n"
                "• **Confessions secrètes** : partage tes pensées en toute discrétion.\n\n"
                "──────────────\n"
                "💡 **Pour commencer**\n"
                "• Tape `/help` pour découvrir toutes mes commandes.\n"
                "• Clique sur 📺 **Tuto** pour accéder à ma chaîne YouTube.\n"
                "• Un souci ? Cliquez sur 🎫 **Support** et je vous aiderai.\n"
                "• Envie de me soutenir ? Cliquez sur 🗳️ **Vote** !\n\n"
                "Merci et amusez-vous bien ! 🌟"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.set_image(url=EMBED_IMAGE_URL)

        # Création des boutons
        view = View()
        view.add_item(Button(label="Tuto", url=TUTO_YTB, emoji="📺"))
        view.add_item(Button(label="Support", url=SUPPORT_INVITE, emoji="🎫"))
        view.add_item(Button(label="Vote", url=TOPGG, emoji="🗳️"))

        # Envoi dans le serveur
        channel = None
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            channel = guild.system_channel
        else:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break

        if channel:
            try:
                await channel.send(embed=embed, view=view)
            except Exception:
                # silent fail si plus de perms
                pass

        # Envoi en DM au propriétaire du serveur
        owner = guild.owner
        if owner:
            try:
                await owner.send(embed=embed, view=view)
            except Exception:
                # l'utilisateur a peut-être désactivé les DMs
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(GuildJoinListener(bot))
