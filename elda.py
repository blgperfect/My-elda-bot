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
for name in ("discord", "discord.client", "discord.gateway", "discord.ext.commands.bot"):
    logging.getLogger(name).setLevel(logging.ERROR)

console = Console()


class EldaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            owner_id=OWNER_ID,
            help_command=None,
        )

        self.loaded_ext: list[str] = []
        self.failed_ext: list[str] = []

    async def setup_hook(self):
        """Charge récursivement les extensions et synchronise les slash commands."""
        base = Path(__file__).parent

        for pkg in ("commands", "tasks"):
            folder = base / pkg
            for file in folder.rglob("*.py"):
                # on ignore les __init__.py et les fichiers commençant par _
                if file.name.startswith("_") or file.name == "__init__.py":
                    continue

                # ex: commands/admin/mod.py -> commands.admin.mod
                rel = file.relative_to(base).with_suffix("")  # ex: commands/admin/mod
                module = ".".join(rel.parts)

                try:
                    await self.load_extension(module)
                    self.loaded_ext.append(module)
                except Exception as e:
                    logger.exception(f"Failed to load extension {module}: {e}")
                    self.failed_ext.append(module)

        # Synchronise toutes les commandes slash
        await self.tree.sync()

    async def on_ready(self):
        # Affichage épuré
        console.print(f"✅ Bot connecté en tant que {self.user}")
        await self.change_presence(activity=discord.Game(STATUS_MESSAGE))
        console.print(f"✨ Statut défini sur « {STATUS_MESSAGE} »")

        # Résumé du chargement
        console.print(f"🔧 {len(self.loaded_ext)} extension(s) chargée(s).")
        if self.failed_ext:
            console.print(
                f"⚠️ {len(self.failed_ext)} échec(x) de chargement : "
                + ", ".join(self.failed_ext)
            )
        console.print(
            f"📜 {len(self.commands)} text command(s), "
            f"{len(self.tree.get_commands())} slash command(s)."
        )


# ─── Connexion à MongoDB ────────────────────────────────────────────────────
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]

# ─── Démarrage du Bot ───────────────────────────────────────────────────────
if __name__ == "__main__":
    bot = EldaBot()
    bot.run(DISCORD_TOKEN)
