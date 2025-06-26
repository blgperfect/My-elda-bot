import os
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from rich.console import Console

# ─── Configuration de base ────────────────────────────────────────────────────
load_dotenv()
DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN")
MONGO_URI      = os.getenv("MONGO_URI")
DATABASE_NAME  = os.getenv("DATABASE_NAME")
OWNER_ID       = int(os.getenv("BOT_OWNER_ID", 0))
STATUS_MESSAGE = "Bonjour chez melo"

# ─── Logger “joli” ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("elda")

# Ne conserver que les logs ERROR+ pour discord.py et ses sous-modules
for name in ("discord", "discord.client", "discord.gateway", "discord.ext.commands.bot"):
    logging.getLogger(name).setLevel(logging.ERROR)

console = Console()

# ─── Intents & Bot ──────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    owner_id=OWNER_ID,
    help_command=None,
)

# ─── Connexion à MongoDB ────────────────────────────────────────────────────
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]

# ─── Chargement dynamique des extensions ───────────────────────────────────
BASE_DIR = Path(__file__).parent
_loaded_ext = []
_failed_ext = []

def load_extensions_from(folder: Path, package: str):
    for file in folder.glob("*.py"):
        if file.name.startswith("_"):
            continue
        module = f"{package}.{file.stem}"
        try:
            bot.load_extension(module)
            _loaded_ext.append(module)
        except Exception as e:
            logger.exception(f"Failed to load extension {module}: {e}")
            _failed_ext.append(module)

# Charger commands/ et tasks/
load_extensions_from(BASE_DIR / "commands", "commands")
load_extensions_from(BASE_DIR / "tasks",    "tasks")

# ─── Événement ready ─────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    # Messages de connexion épurés
    console.print(f"✅ Bot connecté en tant que {bot.user}")
    await bot.change_presence(activity=discord.Game(STATUS_MESSAGE))
    console.print(f"✨ Statut défini sur « {STATUS_MESSAGE} »")

    # Résumé du chargement
    console.print(f"🔧 {_loaded_ext.__len__()} extensions chargées.")
    if _failed_ext:
        console.print(f"⚠️ {_failed_ext.__len__()} extension(s) ont échoué à charger : {', '.join(_failed_ext)}")
    console.print(f"📜 {len(bot.commands)} commande(s) disponibles.")

# ─── Point d’entrée ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
