import discord
from discord.ext import commands
from datetime import datetime

from config.params import BOT_OWNER_ID, EMBED_COLOR, EMBED_FOOTER_TEXT, EMBED_FOOTER_ICON_URL
from config.mongo import ideas_collection

class Ideas(commands.Cog):
    """
    Cog pour gérer les idées personnelles et suggérées (accessible uniquement à l'owner).
    Commandes :
      - !add [@user] texte : enregistre une idée (optionnellement suggérée par un membre)
      - !list : liste paginée des idées
      - !del <num> : supprime l'idée numéro <num>
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_check(self, ctx: commands.Context) -> bool:
        # Accessible uniquement par l'owner
        return ctx.author.id == BOT_OWNER_ID

    @commands.command(name="add")
    async def add_idea(self, ctx: commands.Context, *, content: str):
        """!add [@user] texte : enregistre une idée (optionnellement suggérée)."""
        # Détection de la première mention si présente
        if ctx.message.mentions:
            member = ctx.message.mentions[0]
            suggested_by = member.id
            # Nettoyage du texte de l'idée en retirant la mention
            mention_str = f"<@{member.id}>"
            mention_str_alt = f"<@!{member.id}>"
            idea_text = content.replace(mention_str, "").replace(mention_str_alt, "").strip()
        else:
            suggested_by = None
            idea_text = content.strip()

        if not idea_text:
            return await ctx.send("❌ Tu dois fournir un texte pour l'idée.")

        # Insertion dans MongoDB
        doc = {
            "owner_id": BOT_OWNER_ID,
            "idea": idea_text,
            "suggested_by": suggested_by,
            "created_at": datetime.utcnow()
        }
        await ideas_collection.insert_one(doc)

        # Confirmation
        if suggested_by:
            await ctx.send(f"✅ Idée suggérée par {member.mention} enregistrée !")
        else:
            await ctx.send("✅ Idée personnelle enregistrée !")

    @commands.command(name="list")
    async def list_ideas(self, ctx: commands.Context):
        """!list : affiche la liste paginée des idées."""
        # Récupère toutes les idées de l'owner, triées par date
        cursor = ideas_collection.find({"owner_id": BOT_OWNER_ID}).sort("created_at", 1)
        docs = await cursor.to_list(length=None)
        if not docs:
            return await ctx.send("❌ Aucune idée enregistrée.")

        # Génération dynamique des pages selon la taille du texte
        pages = []
        current = ""
        for idx, doc in enumerate(docs, start=1):
            prefix = f"**{idx}.** "
            if doc.get("suggested_by"):
                prefix += f"suggéré par <@{doc['suggested_by']}> : "
            line = prefix + doc["idea"] + "\n\n"
            # Limite à ~1900 caractères pour l'embed
            if len(current) + len(line) > 1900:
                pages.append(current)
                current = line
            else:
                current += line
        pages.append(current)

        # Création de la vue avec boutons précédent/suivant
        view = discord.ui.View(timeout=None)
        view.pages = pages
        view.current = 0

        btn_prev = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.primary, custom_id="prev")
        btn_next = discord.ui.Button(label="➡️", style=discord.ButtonStyle.primary, custom_id="next")
        view.add_item(btn_prev)
        view.add_item(btn_next)

        async def button_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Ce n'est pas pour toi !", ephemeral=True)
            # Navigation cyclique
            if interaction.data.get("custom_id") == "next":
                view.current = (view.current + 1) % len(view.pages)
            else:
                view.current = (view.current - 1) % len(view.pages)
            embed = discord.Embed(description=view.pages[view.current], color=EMBED_COLOR)
            embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
            await interaction.response.edit_message(embed=embed, view=view)

        # Assignation du même callback aux deux boutons
        btn_prev.callback = button_callback
        btn_next.callback = button_callback

        # Envoi du premier embed
        embed = discord.Embed(description=pages[0], color=EMBED_COLOR)
        embed.set_footer(text=EMBED_FOOTER_TEXT, icon_url=EMBED_FOOTER_ICON_URL)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="del")
    async def delete_idea(self, ctx: commands.Context, index: int):
        """!del <num> : supprime l'idée numéro <num>."""
        # Récupère la liste à jour
        docs = await ideas_collection.find({"owner_id": BOT_OWNER_ID}).sort("created_at", 1).to_list(length=None)
        if index < 1 or index > len(docs):
            return await ctx.send("❌ Numéro invalide.")

        # Suppression du document cible
        target = docs[index - 1]
        await ideas_collection.delete_one({"_id": target["_id"]})
        await ctx.send(f"🗑️ Idée n°{index} supprimée.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Ideas(bot))
