Tu es un développeur expert en bots Discord, utilisant Python 3.11+, la librairie discord.py et une base MongoDB pour la persistance. Génère pour moi un module complet (fichiers .py) qui implémente trois commandes slash :

1. **/role config**  
   - Accessible uniquement aux membres ayant la permission « Administrator ».  
   - Invisible aux autres membres.  
   - Lorsqu’on exécute la commande, affiche un embed (utilise le template d’embed défini dans params.py) avec un message professionnel, par exemple :  
     > « Bienvenue dans la configuration des accès aux commandes /role give et /role remove.  
     Merci de sélectionner ci-dessous les rôles de votre serveur qui auront le droit d’utiliser /role give et /role remove en plus des administrateurs.  
     Cliquez sur ✅ lorsque vous avez terminé votre sélection. »  
   - Propose un **menu de sélection de rôles** (ou des boutons, selon ce que supporte ta version de discord.py) listant tous les rôles du serveur.  
   - Conserve en base MongoDB (par serveur) la liste des rôles autorisés, et fait en sorte que, si on relance /role config dans un an, on retrouve la sélection précédente et on puisse y ajouter ou en retirer.

2. **/role give** et **/role remove**  
   - Visibles uniquement pour les administrateurs **et** les membres dont un rôle a été sélectionné via /role config.  
   - Permettent respectivement de donner ou retirer un rôle à un autre membre, sauf si ce membre cible a un rôle *strictement supérieur* dans la hiérarchie Discord.  
   - Gèrent proprement les erreurs et renvoient toujours un message embed (en utilisant params.py) en cas de « permission insuffisante » ou « cible inéligible ».

**Contraintes techniques**  
- Utilise MongoDB (via motor ou pymongo) pour stocker la configuration par guild.  
- Sépare proprement le code dans des cogs ou modules.  
- Tous les retours, succès comme erreurs, doivent être en embed et utiliser les paramètres pré-configurés dans params.py (couleurs, footer, etc.).  
- Documente brièvement chaque commande (docstrings, commentaires) et affiche un message d’erreur clair si la base de données n’est pas accessible.

Fournis-moi le code complet prêt à l’emploi, sans explications superflues, uniquement les fichiers .py nécessaires.  
