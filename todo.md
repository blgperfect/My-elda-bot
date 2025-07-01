Bon donc J'aimerais une commande qui sappelle : /custom-voc
permisson : administrateur /caché la commande a ceux qui non pas cette permission
menu embed [regarder params pour les infos a prendre : on utulise exemple : from config.params import (
    EMBED_COLOR,
    EMBED_FOOTER_TEXT,
    EMBED_FOOTER_ICON_URL,
    MESSAGES,
)]

limitation du code : une seule configuration possible , si le membre fait /custom-voc et qu'il a deja une config on desactive le bouton creer on lui laisse seulement supprimé
et on ne peux pas supprimé ce qui nexiste pas encore !
L'embed aurais un menu de selection rattacher a lui pour configurer (faut allez en ordre) : 1. La catégorie pour le salon vocale. 2. Le salon vocale pour créer les salon vocaux custom.(avec explications pour clareté) embed qui se change dynamiquement selon les choix. 
+ 2 bouton , terminé = confirmé les choix + enregistrer dans la db (on enregistre la categorie id et salon id (si jamais il decide de changer les noms) la categorie est l'endroit ou seront créer les futur salon vocaux custom et le salon ou les membre doivent rejoindre pour créer le leurs.)
bouton suppression = supprimer les configs , ON NE SUPPRIME PAS LES SALON. on supprime uniquement la db donc plus rien se passe si quelqu'un rejoint un salon qui avais ete configurer


que ce paase t-il ensuite ? 
eh bien quand un membre rejoint le salon vocale definit on créer un nouveau salon et on le renomme : salon de [nom du membre]
on envoie un menu avec choix (bouton ou selection non expirable) pour configuré sont salon (ce menu est strictement et uniquement pour lapersonne a qui appartien ce salon)
choix du menu : changer la limitation (nb d emembre dans le salon voc) renommer le salon , mettre un status au salon vocaux, 
si la personne quitte le salon , on ne supprime pas sont salon personnelle si il y a encore des gens
on supprime uniquement le salon quand la derniere personne a y etre quitte

le membre ne peux pas gerer les changement (limitation membre et le reste autrement que par le bot et son menu. Nous utulisons automatiquement les permissions & role configurer de la categorie parents)
c'est clair ? 

je veux un menu sophistiquer claire et beau!

