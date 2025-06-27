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
        # ─── Intents ──────────────────────────────────────────────────────────
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True   # ← Activation de l’Intent presences

        # Création du bot avec statut personnalisé
        super().__init__(
            command_prefix="!",
            intents=intents,
            owner_id=OWNER_ID,
            help_command=None,
            activity=discord.CustomActivity(STATUS_MESSAGE),
        )

        self.loaded_ext: list[str] = []
        self.failed_ext: list[str] = []

    async def setup_hook(self):
        """Charge récursivement les extensions et synchronise les slash commands."""
        base = Path(__file__).parent

        for pkg in ("commands", "task"):
            folder = base / pkg
            for file in folder.rglob("*.py"):
                if file.name.startswith("_") or file.name == "__init__.py":
                    continue

                rel = file.relative_to(base).with_suffix("")
                module = ".".join(rel.parts)

                try:
                    await self.load_extension(module)
                    self.loaded_ext.append(module)
                except Exception as e:
                    logger.exception(f"Failed to load extension {module}: {e}")
                    self.failed_ext.append(module)

        # Synchronisation des commandes slash
        await self.tree.sync()

    async def on_ready(self):
        # Affichage de connexion
        console.print(f"✅ Bot connecté en tant que {self.user}")
        console.print(f"✨ Statut personnalisé : « {STATUS_MESSAGE} »")

        # Séparation des modules commands vs task
        cmds = [m for m in self.loaded_ext if m.startswith("commands.")]
        task = [m for m in self.loaded_ext if m.startswith("task.")]

        console.print(f"🛠️ {len(task)} module(s) de tâches chargé(s).")
        console.print(f"⚙️ {len(cmds)} module(s) de commandes chargé(s).")
        if self.failed_ext:
            console.print(
                f"⚠️ {len(self.failed_ext)} échec(x) de chargement : "
                + ", ".join(self.failed_ext)
            )

        # Comptage des commandes utilisateur
        console.print(
            f"📜 {len(self.commands)} text command(s), "
            f"{len(self.tree.get_commands())} slash command(s)."
        )


# ─── Connexion à MongoDB ───────────────────────────────────────────────────
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]

# ─── Point d’entrée ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot = EldaBot()
    bot.run(DISCORD_TOKEN)
