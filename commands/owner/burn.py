# commands/owner/burn.py
import discord
from discord.ext import commands

class ServerWipe(commands.Cog):
    """Cog pour supprimer toutes les catégories et salons d'un serveur (owner only)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="wipe")
    @commands.is_owner()
    async def wipe(self, ctx: commands.Context):
        """
        🔥 Supprime TOUTES les catégories et salons du serveur.
        Nécessite d'être l'owner du bot.
        """
        guild = ctx.guild
        if not guild:
            return await ctx.send("Cette commande doit être exécutée dans un serveur.")

        # 1) Confirmation publique
        await ctx.send("🚨 Début de la suppression de **TOUS** les salons et catégories…")

        # 2) Récupère d'abord la liste puis supprime
        channels = list(guild.channels)  # copie pour itérer en toute sécurité
        for channel in channels:
            try:
                await channel.delete(reason=f"Server wipe demandé par {ctx.author}")
            except Exception as e:
                # On logge l'erreur mais on continue
                self.bot.logger.error(f"Échec suppression {channel.name} ({channel.id}): {e}")

        # 3) Envoi du résultat en DM pour éviter le 404 sur un salon supprimé
        summary = (
            f"✅ Wipe terminé sur le serveur **{guild.name}** (ID {guild.id}).\n"
            f"{len(channels)} salons/catégories supprimés."
        )
        try:
            await ctx.author.send(summary)
        except discord.Forbidden:
            # Si l'owner a désactivé les MP
            await ctx.send("✅ Wipe terminé, mais je n'ai pas pu DM l'owner pour le résumé.")

    @wipe.error
    async def wipe_error(self, ctx: commands.Context, error: commands.CommandError):
        """Gestion des erreurs pour la commande wipe."""
        if isinstance(error, commands.NotOwner):
            await ctx.reply(
                "❌ Vous n'êtes pas autorisé·e à utiliser cette commande.",
                mention_author=False
            )
        else:
            await ctx.reply(
                f"❌ Une erreur est survenue : {error}",
                mention_author=False
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerWipe(bot))
