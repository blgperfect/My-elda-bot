# config/mongo.py
# je juge ce code complété
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI     = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db           = mongo_client[DATABASE_NAME]

# Collection pour la config “soutien”
soutien_collection = db["soutien"]
images_only_collection = db["images_only"]
role_config_collection = db["role_config"]
blacklist_collection    = db["blacklist"]
confession_collection = db["confession_data"]
role_panel_collection = db["role_panels"]
giveaways_collection = db["giveaways"]