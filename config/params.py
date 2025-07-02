#complété

# === Lien top.gg
TOPGG = "https://top.gg/bot/1351415146639134832?s=08ff278d98260"
SUPPORT_INVITE = "https://discord.gg/b6PbxtUWNk"
TUTO_YTB = "https://youtube.com/@eldabot?si=3qciRBpP9A5Wx-6E"
BOT_INVITE = "https://discord.com/oauth2/authorize?client_id=1387873062841745479"

# === Apparence des embeds ===
EMBED_COLOR = 0xE3BAE8
EMBED_FOOTER_TEXT = "©𝐸𝓁𝒹𝒶 𝐵𝑜𝓉"
EMBED_FOOTER_ICON_URL = "https://cdn.discordapp.com/attachments/1102406059722801184/1387882570263433236/IMG_8167.png"
EMBED_IMAGE_URL = "https://cdn.discordapp.com/attachments/1102406059722801184/1387886546300043264/0C5431CA-4920-413C-BBC7-0F18DA8C3D15.png"

# === Propriétaire du bot & permissions par défaut ===
BOT_OWNER_ID = 808313178739048489
DEFAULT_PERMISSION = "ban_members"

# === Placeholders dynamiques ===
PLACEHOLDERS = {
    "{member}": "Mention de l’utilisateur (<@id>)",
    "{member.id}": "ID de l’utilisateur",
    "{server}": "Nom du serveur (guild.name)",
    "{server.id}": "ID du serveur",
    "{server.member_count}": "Nombre de membres",
    "{server.owner}": "Propriétaire du serveur",
    "{server.owner_id}": "ID du propriétaire",
    "{server.created_at}": "Date de création",
    "{invite.code}": "Code de l’invitation",
    "{invite.url}": "Lien complet",
    "{invite.uses}": "Nombre d’utilisations",
    "{invite.max_uses}": "Limite max d’utilisation",
    "{invite.inviter}": "Tag du créateur de l’invite",
    "{invite.inviter.id}": "ID du créateur de l’invite",
    "{invite.channel}": "Salon associé à l’invitation"
}

# === Messages d'erreur, système & confirmation ===
MESSAGES = {
    # Permissions
    "PERMISSION_ERROR": "🚫 Vous n'avez pas la permission d'utiliser cette commande.",
    "BOT_PERMISSION_ERROR": "⚠️ Je n'ai pas les permissions nécessaires pour exécuter cette action.",
    "PRIVATE_ONLY": "❌ Cette commande ne peut être utilisée que dans les messages privés.",
    "GUILD_ONLY": "❌ Cette commande ne peut être utilisée que dans un serveur Discord.",

    # Erreurs d'utilisation
    "COMMAND_NOT_FOUND": "❓ Commande inconnue. Utilisez `/help` pour la liste des commandes disponibles.",
    "MISSING_ARGUMENT": "⚠️ Il manque un ou plusieurs arguments obligatoires.",
    "INVALID_ARGUMENT": "❌ Argument invalide. Vérifiez la syntaxe et essayez à nouveau.",
    "TOO_MANY_ARGUMENTS": "⚠️ Trop d'arguments fournis.",
    "COMMAND_COOLDOWN": "🕒 Cette commande est en cooldown. Veuillez patienter avant de réessayer.",

    # Erreurs système
    "INTERNAL_ERROR": "💥 Une erreur interne est survenue. Veuillez réessayer plus tard ou contacter un administrateur.",
    "API_ERROR": "⚠️ Impossible de contacter l'API. Veuillez réessayer plus tard.",
    "DATABASE_ERROR": "📛 Erreur de base de données. Contactez un administrateur.",
    "UNKNOWN_ERROR": "🤷 Une erreur inconnue est survenue. Veuillez réessayer.",

    # Réussite
    "ACTION_SUCCESS": "✅ Action effectuée avec succès.",
    "MESSAGE_SENT": "📨 Message envoyé avec succès.",
    "COMMAND_EXECUTED": "🎉 Commande exécutée avec succès.",
    "USER_WARNED": "⚠️ L'utilisateur a été averti.",
    "ROLE_ASSIGNED": "🔖 Rôle attribué avec succès.",

    # En traitement
    "LOADING": "⏳ Traitement en cours, veuillez patienter...",
    "FETCHING_DATA": "📡 Récupération des données en cours...",

    # Cas spécifiques
    "USER_NOT_FOUND": "🙁 Utilisateur introuvable. Vérifiez l'identifiant ou la mention.",
    "CHANNEL_NOT_FOUND": "🔍 Salon introuvable.",
    "ROLE_NOT_FOUND": "🔍 Rôle introuvable.",
    "CANNOT_DM_USER": "📪 Impossible d’envoyer un message privé à cet utilisateur.",
    "ALREADY_HAS_ROLE": "ℹ️ L'utilisateur possède déjà ce rôle.",
    "NOT_OWNER": "🔐 Seul le propriétaire du bot peut exécuter cette commande."
}

# === Emojis standards (réutilisables dans les embeds, logs, etc.) ===
EMOJIS = {
    "SUCCESS": "✅",
    "CHECK": "✔️",
    "PARTY": "🎉",
    "MAIL_SENT": "📨",
    "ERROR": "❌",
    "CROSS": "✖️",
    "NO_ENTRY": "🚫",
    "WARNING": "⚠️",
    "STOP": "🛑",
    "BROKEN": "💥",
    "LOCK": "🔒",
    "UNLOCK": "🔓",
    "SHIELD": "🛡️",
    "LOADING": "⏳",
    "HOURGLASS": "⌛",
    "SPINNING": "🔄",
    "FETCHING": "📡",
    "ONLINE": "🟢",
    "OFFLINE": "🔴",
    "IDLE": "🌙",
    "INFO": "ℹ️",
    "BELL": "🔔",
    "QUESTION": "❓",
    "INBOX": "📥",
    "USER": "👤",
    "MENTION": "🗣️",
    "TARGET": "🎯",
    "BAN": "🔨",
    "KICK": "👢",
    "WARNING_SIGN": "🚨",
    "REPORT": "📝",
    "STAR": "⭐",
    "ARROW": "➡️",
    "BACK": "⬅️",
    "UP": "⬆️",
    "DOWN": "⬇️",
    "LINK": "🔗"
}
