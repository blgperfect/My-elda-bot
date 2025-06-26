import discord
from discord.ext import commands

from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    EMBED_IMAGE_URL,
    MESSAGES,
    EMOJIS,
    PLACEHOLDERS,
)

class ParamPreview(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="testparams")
    async def testparams(self, ctx):
        # ========================
        # Emojis affichés visuellement
        emoji_block = " ".join(EMOJIS.values())
        
        # ========================
        # Tous les messages d’erreurs/systèmes
        messages_text = "\n".join(
            f"`{key}` → {value}" for key, value in MESSAGES.items()
        )
        # Discord limite les champs à 1024 caractères max
        messages_chunks = [messages_text[i:i+1024] for i in range(0, len(messages_text), 1024)]

        # ========================
        # Tous les placeholders dynamiques
        placeholder_text = "\n".join(
            f"`{key}` → {value}" for key, value in PLACEHOLDERS.items()
        )
        placeholder_chunks = [placeholder_text[i:i+1024] for i in range(0, len(placeholder_text), 1024)]

        # ========================
        # Embed construction
        embed = discord.Embed(
            title=f"{EMOJIS['INFO']} Aperçu complet des paramètres",
            description=f"{EMOJIS['SUCCESS']} Tous les paramètres sont correctement chargés.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        embed.set_image(url=EMBED_IMAGE_URL)

        embed.add_field(name="🎭 Emojis disponibles", value=emoji_block[:1024], inline=False)

        for i, chunk in enumerate(messages_chunks):
            embed.add_field(
                name=f"🧾 Messages définis (partie {i + 1})",
                value=chunk,
                inline=False
            )

        for i, chunk in enumerate(placeholder_chunks):
            embed.add_field(
                name=f"🔁 Placeholders (partie {i + 1})",
                value=chunk,
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ParamPreview(bot))
