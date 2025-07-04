1. Présentation générale

Un unique panneau de tickets par serveur, stocké en MongoDB.
Max. 5 catégories de tickets (ex. Partenariat, Support, Admin…).
Permissions : seules les personnes ayant le rôle ADMIN peuvent configurer ou réinitialiser.
Aucun historique des tickets définitivement supprimés n’est conservé en base.
2. Commandes principales

Commande	Description
/pannel create	Crée le panneau unique (si inexistant).
/pannel send	Envoie ou met à jour le panneau interactif dans le canal configuré.
/pannel reset	Réinitialise tout le système à zéro : désactive le panneau, supprime catégories & textes.
/pannel edit	Affiche tous les textes (panneau + catégories) et permet de corriger typos ou formulations.
Note : tout ce qui s’affiche à l’utilisateur (panneau, messages initiaux, logs…) est un embed.
3. Configuration du panneau

Panneau unique
Affiche jusqu’à 5 boutons.
Chaque bouton correspond à une catégorie de ticket.
Définition des catégories (max. 5)
Libellé du bouton (ex. “Support”, “Partenariat”).
Salon de destination (catégorie Discord)
Rôles assignés qui gèrent cette catégorie.(peux avoir plus que un)
Interface de sélection : menu déroulant avec recherche, interdit d’utiliser des modales pour choisir rôle, salon ou catégorie.
Texte et personnalisation
Embed de description du panneau (modifiable via /pannel edit).
Embed initial pour chaque ticket : texte libre + option de mentionner automatiquement les rôles assignés.
Affichage des textes actuels avant toute modification pour corriger simplement une coquille.
texte par défaut du bot modifiable
4. Numérotation et pinning

Les tickets sont numérotés séquentiellement de 1 à l’infini.
À l’ouverture de chaque ticket, l’embed initial est épinglé automatiquement dans le salon.



5. Workflow des tickets

5.1. Ouverture
L’utilisateur clique sur le bouton de sa catégorie.
Création automatique d’un salon privé nommé :
<numéro>-<pseudo-membre>
5.2. Claim & suivi
Claim
Bouton réservé aux rôles assignés.
Les rôles de hiérarchie supérieure peuvent reprendre un claim déjà pris.
À la première prise en charge, le nom du salon passe à :
<numéro>-<pseudo-membre>-<pseudo-claimer>
5.3. Fermeture
Close
Le staff clique sur Close.
Faire configuré une categgorie pour les ticket clos(lors de la programation).
Le salon est renommé en :
fermer-<pseudo-membre>
Les boutons sont désactivés jusqu’à eventuelle réouverture.
Reopen
Rouvre le ticket fermé, renomme le salon en <numéro>-<pseudo-membre> et réactive les boutons.
Delete
Archive un transcript complet dans le salon de transcripts (embed ou fichier).
Supprime définitivement le salon (numérotation suivante continue).
5.4. Membre parti
Si un membre qui a un ticket ouvert quitte le serveur, un embed est posté dans son salon :
« <@membre> a quitté le serveur. Voulez-vous fermer ce ticket ? Cliquez sur Close pour confirmer. »
Le ticket n’est pas fermé automatiquement ; le staff doit cliquer sur Close.
6. Logs & transcripts

Salon de logs
Envoi systématique (embed) pour chaque action : ouverture, claim, close, reopen, delete.
Contient : date/heure, numéro du ticket, catégorie, utilisateur ou staff auteur de l’action.
Salon de transcript
Avant chaque Delete, le contenu complet du ticket est posté ici (embed paginé ou fichier texte).