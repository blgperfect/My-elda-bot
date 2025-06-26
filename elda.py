import discord
from discord.ext import commands
import motor.motor_asyncio
import os
import asyncio
from dotenv import load_dotenv
from pathlib import Path

from config.params import EMOJIS
from config.config_manager import ConfigManager  # ✅ Import corrigé

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

async def get_prefix(bot, message):
    if not message.guild:
        return "!"  # Préfixe par défaut en DM
    config = await bot.config_manager.load_config(guild_id=message.guild.id)
    return config.get("prefix", "!")

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# MongoDB & Config
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]
config_manager = ConfigManager(MONGO_URI, DATABASE_NAME)

bot.db = db
bot.config_manager = config_manager
bot.config = None  # Config globale éventuelle

async def load_command_extensions():
    count = 0
    commands_path = Path("./commands")
    if commands_path.exists():
        for py_file in commands_path.rglob("*.py"):
            module_name = py_file.with_suffix("").as_posix().replace("/", ".")
            try:
                if module_name in bot.extensions:
                    await bot.reload_extension(module_name)
                else:
                    await bot.load_extension(module_name)
                count += 1
            except Exception as e:
                print(f"❌ Erreur chargement commande {module_name} : {e}")
    print(f"📦 {count} commandes enregistrées.")

async def load_task_extensions():
    count = 0
    task_path = Path("./task")
    if task_path.exists():
        for py_file in task_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            module_name = py_file.with_suffix("").as_posix().replace("/", ".")
            try:
                if module_name in bot.extensions:
                    await bot.reload_extension(module_name)
                else:
                    await bot.load_extension(module_name)
                count += 1
            except Exception as e:
                print(f"❌ Erreur chargement cog {module_name} : {e}")
    print(f"🔹 {count} cogs chargés.")

@bot.event
async def on_ready():
    command_count = sum(1 for _ in bot.walk_commands())
    print(f"📦 {command_count} commandes enregistrées.")
    print(f"🤖 {bot.user.name} est connecté ! {EMOJIS['HEART']}")
    await bot.change_presence(activity=discord.Game(name="Je mange du paprika"))

    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commandes slash synchronisées.")
    except Exception as e:
        print(f"❌ Erreur synchronisation commandes slash : {e}")

async def main():
    async with bot:
        await load_task_extensions()
        await load_command_extensions()
        print("🚀 Démarrage du bot...")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
