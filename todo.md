Salut voici mes code principaux avec exemple de soutien.py pour la structure !
pour les permission de la commande slash tu fait sa @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)


pour les embed (cat tout message seras en embed)
from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
    EMOJIS,
)
tu reprend pour mongo db sa dans le code = 
from config.mongo import soutien_collection

tu importe io et utulise sa pour la transcription from pymongo import ReturnDocument


objectif systeme de ticket

commande /ticket-config
usage : /ticket-config salon (ou envoyer le panneau) transcription(ou envoyé les transcription) category(ou ouvrir les ticket) role(pour laisser a l'admin séelectionné qui a acces au ticket)


message envoyé dans le salon ou envoyé le panneau = (en embed) Pour créer un ticket et contacté l'administration appuyez sur (ici met un emoji mignon) et en bas bah le bouton avec lemoji.

suivi des ticket par server : le 1 er exemple 001 nom de la personne le 99 eme serais 099 nom de la personne et le 376 serais exemple 376 nom de la personne.


message qui apparais dans le ticket quand quelqu'un a ouvert.(en embed) = Merci d'avoir contacté le staff. Pour tout probleme merci de mentionné les utulisateur concerné ainsi que preuve a lappuie , pour un partenariat merci de t'assuré d'Avoir lu nos conditions. Pour postuler merci de mentionné le poste que tu veux postuler pour (bref rend sa claire et originale et séparé par sous titre et emoji) + mentions hors embed (en haut de l'embed) = les roles sélection préalablement par l'Admin.

bouton sous l'embed = claim ,pour claim le ticket(rien ne change simplement tu envoie dans le salon que @ a claim ce ticket) SEULE LES ROLE SELECTIONNÉ PEUVENT CLAIM OU CEUX QUI ON LA PERM ADMINISTRATEUR LE MEMBRE QUI A OUVERT LE TICKET NE PEUX PAS.
bouton close = clos le ticket (le membre qui a ouvert le ticket n'A plus acces au ticket, les autre peuvent encore tout faire)
reopen = le membre a qui appartien le ticket peux a nouveau ravoir less permissions
delete = supprime le ticket et l'envoie dans le salon transcription (double verification) 

permission par ticket 
everyone = ne peux pas voir.
la personne qui a ouvert le ticket = peux voir lire ecrire voir ancien message
role séelectionne qui on acces au ticket = peux voir lire ecrire voir ancien message


salon transcription : en meme temp qu'une transcription est recu on envoie un message en embed qui nomme la personne qui avais ouvert le ticket avec son id a coté , la personne qui a claim le ticket. cest tout

mongodb = on ne garde pas en memoire les ticket qui on été fermer mais on sassure du suivi des numero sa > (suivi des ticket par server : le 1 er exemple 001 nom de la personne le 99 eme serais 099 nom de la personne et le 376 serais exemple 376 nom de la personne.
)
d'Autre question avant de me faire le code ? si oui demande les maintenants.