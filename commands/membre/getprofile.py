import discord
from discord import File
from discord.ext import commands
from discord import app_commands

from config.mongo import profile_collection
from commands.admin.configurations.profile import render_profile_to_image

class ProfileCommandCog(commands.Cog):
    """Cog dédié à la commande slash /profile pour afficher un profil."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="profile",
        description="Affiche votre profil ou celui d'un autre membre."
    )
    @app_commands.describe(
        member="Le membre dont vous voulez voir le profil (optionnel)"
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        # Détermine la cible (auteur ou membre passé en option)
        target = member or interaction.user
        guild = interaction.guild

        # Recherche du document en base
        doc = await profile_collection.find_one({
            "guild_id": guild.id,
            "user_id": target.id
        })
        if not doc:
            # Message d'erreur si pas de profil
            return await interaction.response.send_message(
                f"❌ Aucun profil trouvé pour {target.display_name}.",
                ephemeral=True
            )

        # On défère la réponse pour éviter le timeout durant le rendu
        await interaction.response.defer(ephemeral=False)

        # Préparation des données pour le rendu
        data = {
            "avatar_url": target.display_avatar.url,
            "nickname": doc.get("nickname", "inconnu"),
            "age": doc.get("age", "inconnu"),
            "gender": doc.get("gender", "inconnu"),
            "pronoun": doc.get("pronoun", "inconnu"),
            "birthday": doc.get("birthday", "inconnu"),
            "description": doc.get("description", "aucune")
        }

        # Génère l'image du profil
        buf = await render_profile_to_image(data)

        # Envoie l'image dans la réponse différée
        await interaction.followup.send(
            file=File(buf, filename="profile.png"),
            ephemeral=False
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCommandCog(bot))
