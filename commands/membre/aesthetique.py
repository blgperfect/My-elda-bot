import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select

# Dictionnaire de styles avec mappages Unicode (ajoutez d'autres mappings selon instafonts.io)
FONT_MAPS = {
    # Bubble styles
    "Bubble Filled": str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ"
        "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ"
    ),
    "Bubble Outline": str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩"
        "🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩"
    ),
    # Square
    "Square": str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉"
        "🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩"
    ),
    # Cursive
    "Cursive": str.maketrans(
        "abcdefghijklmnopqrstuvwxyz",
        "𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃"
    ),
    # Serif (Bold)
    "Serif Bold": str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙"
        "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
    ),
    # Monospace (inclut chiffres)
    "Monospace": str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉"
        "𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣"
        "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
    ),
    # Small Caps
    "Small Caps": str.maketrans(
        "abcdefghijklmnopqrstuvwxyz",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
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
        choices = {name: text.translate(mapping) for name, mapping in FONT_MAPS.items()}

        # Crée un menu déroulant où chaque option affiche le texte stylé (tronqué si trop long)
        options = []
        for name, styled in choices.items():
            label = styled if len(styled) <= 50 else styled[:47] + "..."
            options.append(discord.SelectOption(label=label, value=name, description=name))

        select = Select(placeholder="Choisissez un style...", options=options)

        async def select_callback(select_inter: discord.Interaction):
            style = select.values[0]
            transformed = choices.get(style)
            # Envoie un message persistant pour faciliter le copier-coller
            await select_inter.response.send_message(
                f"**{style}**\n{transformed}",
                ephemeral=False
            )

        select.callback = select_callback
        view = View()
        view.add_item(select)

        # Envoie le menu dans le canal (non éphémère)
        await interaction.response.send_message(
            "Sélectionnez un style pour votre texte :",
            view=view,
            ephemeral=False
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Aesthetic(bot))
