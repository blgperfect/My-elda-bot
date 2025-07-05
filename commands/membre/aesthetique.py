import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select

# Dictionnaire de styles avec mappages Unicode
FONT_MAPS = {
    "Bubble": str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ"
        "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ",
    ),
    "Square": str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉"
        "🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩",
    ),
    "Cursive": str.maketrans(
        "abcdefghijklmnopqrstuvwxyz",
        "𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃",
    ),
}

class Aesthetic(commands.Cog):
    """Cog pour transformer du texte en différents styles esthétiques."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="aesthetic", description="Convertis un texte en différents styles esthétiques.")
    @app_commands.describe(text="Le texte à transformer")
    async def aesthetic(self, interaction: discord.Interaction, text: str):
        # Prépare les transformations
        self.choices = {name: text.translate(map_) for name, map_ in FONT_MAPS.items()}

        # Crée un menu déroulant
        options = [
            discord.SelectOption(label=name, value=name)
            for name in self.choices.keys()
        ]
        select = Select(placeholder="Choisissez un style...", options=options)

        async def select_callback(select_inter: discord.Interaction):
            style = select.values[0]
            transformed = self.choices.get(style)
            await select_inter.response.edit_message(content=f"**{style}**: {transformed}", view=None)

        select.callback = select_callback
        view = View()
        view.add_item(select)

        await interaction.response.send_message("Sélectionnez un style pour votre texte :", view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Aesthetic(bot))
