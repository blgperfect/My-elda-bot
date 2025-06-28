# commands/events/guild_join.py

import discord
from discord.ext import commands

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    EMBED_IMAGE_URL
)

class GuildJoinListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Construire l'embed de bienvenue
        embed = discord.Embed(
            title=f"Merci de m'avoir ajouté sur {guild.name} !",
            description=(
                "Je m'appelle **Elda**, je tiens mon nom de ma bonne amie **Elda Moonwraith**, "
                "mais j'ai été conçu par **xxmissr**.\n\n"
                "Tout d'abord, sachez que pour plusieurs de mes commandes, "
                "je nécessite d'être positionné **le plus haut possible** dans vos rôles !\n\n"
                "Nous vous conseillons de créer un salon nommé **#sanction**, "
                "pour utiliser nos commandes (give, kick, ban), afin qu'elles puissent s'y afficher. "
                "Nous avons privilégié cette méthode plutôt que de générer des logs.\n\n"
                "💡 **Petit conseil** : pour la commande `/addemoji`, vous n'avez pas besoin de Nitro ! "
                "Copiez simplement le message contenant l'emoji et collez-le !"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.set_image(url=EMBED_IMAGE_URL)

        # 1️⃣ Envoi dans le serveur
        # On essaie d'abord le system_channel, sinon le premier salon textuel disponible
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
                await channel.send(embed=embed)
            except Exception:
                # silent fail si jamais on n'a plus les perms
                pass

        # 2️⃣ Envoi en DM au propriétaire du serveur
        owner = guild.owner
        if owner:
            try:
                await owner.send(embed=embed)
            except Exception:
                # l'utilisateur a peut-être désactivé les DMs
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(GuildJoinListener(bot))
