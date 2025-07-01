okay tu vois on a été capable de faire de belle chose avec html pour le member stats noN? 

maintenant j'Aimerais poussé vraiment plus loin

tout d'abord
**profile affichage  text par defaut** (inconnu est ce qui seras marquer entre les parenthese si lutulisateur n'a pas fourni dinformation)

surnom : (inconnu)
age : (inconnu)
genre : (inconnu)
pronom : (inconnu)
date anniversaire ? (inconnu)
description (max de caractere genre je sais pas le max possible dans un image?) (marquer aucune si non configurer.)


***affichage voulu***
message a titre d'Exemple uniquement,
mais je verrais sa comme sa : avatar du membre danns un coin en carré, information du profile affichage inscrit en grand (visible mais pas trop géant non plus)
+ je ne veux voir aucun nom dutulisateur nul part 


**fonctionnement** > 
/profile setup permission admin seulement. 
embed , utulisé les informations dans paramns pour les embeds. 
menu embed jolie
l'embed affiche un truc du genre : 
Bonjour et bienvenue dans la configuration de profile meet & friendly d'elda!
Pour savoir comment sa fonctionne avant tout ? appuyez sur le bouton Informations! (tu le met en gras ses important.)
ici information qui se change dynamiquement(selecteur salon + recherche)
salon pour la création de profile ?
salon pour les femme ?
salon pour les homme ? 
salon pour les autre genre ?




** reaction au choix**
bouton information 
Bienvenue dans le systeme de profile d'elda !
Comment sa fonctionne ? Vous devrez choisir un salon pour la creation de profile ! oui mais sa sert a quoi? et bien sa envoie un embed avec quelque bouton qui permette en sois de créer sont profile sur le server , et ainsi engagé une certaine sociabilité au sein des membre de votre server uniquements.
d'Accord et les autre salon? sa permet a vos membre de savoir ou rechercher dependant des interet de vos membre!
sous chaque profiles un bouton custom de votre choix ou par defaut seras affiché en cliquand dessu , un message seras envoyer en dm a la personne pour expliquer l'interet de la personne qui la liker ! si la personne aimé approuve les informations entre ses 2 membre seront partager si elle refuse , et bien rien ne seras partager!


bouton configurer > menu de selection pour choisir les salon de creation , femme , homme , autre genre. une fois fait on appuie sur terminé et la le bot dit : Une petite seconde tu savais que tu peux choisir ton emoji custom ? envoie moi le ici sinon celui par defaut ses : 💖 
la le membre l'envoie sont emojji custom (les emoji comme sa <:pikapika:1388448429486768140> doivent etre prise en compte et affiché )  et une fois sa fait si on skip bah ses fini si on met notre emoji ses finit.

le bot ennvoie dans le salon relié a salon creation profile , un embed
ou c'est marquer dans ce style

salut a toi chere membre du server (nom du serv ici) 
tu souhaite créer ton profile ? ses par ici appuie sur le boouton créer ton profile!
tu  souhaite modifier ton profile ? appuie sur modifier !
tu souhaite arreter et ne plus etre deranger ? appuie sur supprimer!

bouton creer profile = modale qui souvre et qui pose les question  des information que je tai marquer ici **profile affichage  text par defaut** (inconnu est ce qui seras marquer entre les parenthese si lutulisateur n'a pas fourni dinformation) psss : pour la section du genre a la fin de modale quand il a terminé tu dit derniere question? selectionne ton genre ici : choix de selection femme homme autre
si femme = le salon enregistrer pour femme si homme homme etc okay? 

bouton modifier = tu ouvre un embed avec les donné que le membre avais deja ecrite (reprise de mongodb)
et la il peux les modifier et sa supdate!

bouton supprimer = supprime ton profil des donné de mongo db ne recoit plus aucun message





une fois un profile fait on l'Envoie directement dans le salon approprier (on le sais grace au choix du genre)

chaque profile est renvoyer automatiquement a chaque 24heure.
donc creation = attendre 24 heure et tu est renvoyer ,pour evité le spam.
chaque profile a un bouton sous son image (je l'ai expliquer plus haut) 

si tu clique sur ce bouton = un message est envoyer en dm a l'utulisateur que tu a aimer (celui a qui appartien le profile! et dit )bonjour toi! je t'envoie ce message du (nom du server ou il a été aimé ) ce profile ta aimée (on lui envoie le profile (limage) de la personne qui la aimer ) et on dit appuie sur le bouton accepter pour recevoir ses informations et qu'elle recoivent les tienne (si il le fait tu leur envoie a tout les 2 le nom dutulisateur de l'autre,) refuser ? on passe a autre chose ! ( refuser= envoyer un message a la personne qui a aimé et dire désoler ce profile(envoyer l'image) que tu a aimé n'etais pas interesser !)



important  : tout les bouton sont NON EXPIRABLE , DURER A VIE ET CE MEME SI LE BOT OFFLINE ET REVIENT OFFLINE IL SONT ENCORE APPUYABLE.
DONNÉ ENREGISTRER DANS UNE SEUL COLLECTTION MONGODB
PREVOIR TOUTE LES ERREURS.

A TU NE PEUX PAS CRÉER UN PROFILE SI TU EN A DEJA UN 
B TU NE PEUX PAS SUPPRIMER UN PROFILE SI TU EN A PAS
C TU NE PEUX PAS MODIFIER UN PROFILE SI TU NEN A PAS
