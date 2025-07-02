Voici la version corrigée, structurée et enrichie d’emojis :

---

## 📜 Liste des commandes Slash

### 🔹 **/addemoji**

* **Description :** Ajoute un emoji depuis un autre serveur sur le vôtre !
  Petit tip : vous n’avez besoin que du code d’emoji, par exemple `<:pepeaccepte:1333188297476018229>`.
  Pas besoin de Nitro !
  Un bouton sous l’embed vous permettra ensuite de renommer l’emoji sans passer par les paramètres.
* **Usage :**

  ```
  /addemoji emoji:<votre_code_emoji>
  ```

---

### 🔹 **/avatar**

* **Description :** Affiche votre avatar principal, ou celui d’un serveur/membre si vous le précisez.
* **Usage :**

  ```
  /avatar
  /avatar member:<@membre>
  ```

---

### 🔹 **/ban**

* **Description :** Bannit un utilisateur du serveur avec motif.
  Le bannissement est automatiquement enregistré dans notre base de données pour vérification ultérieure.
* **Usage :**

  ```
  /ban user:<@membre_ou_ID> reason:<raison>
  ```

---

### 🔹 **/check**

* **Description :** Vérifie si un membre a déjà été banni ou kické sur un serveur utilisant le bot Elda.
* **Usage :**

  ```
  /check member:<@membre>
  ```

---

### 🔹 **/confession\_settings**

* **Description :** Gère la blacklist pour la commande de confessions : bloque, débloque ou liste les membres interdits.
* **Usage :**

  ```
  /confession_settings action:<block|unblock|list> user:<@membre>
  ```

---

### 🔹 **/giveaway**

* **Description :** Lance un giveaway avec modale interactive : titre, emoji de participation, bouton « Participer », etc.
  Vous pouvez relancer le tirage, annuler ou tirer avant la fin. 🎉
* **Usage :**

  ```
  /giveaway
  ```

---

### 🔹 **/imagesonly**

* **Description :** Configure un salon pour n’accepter que des fichiers images — idéal pour les channels #selfie ou commentaires. 📸
* **Usage :**

  ```
  /imagesonly
  ```

---

### 🔹 **/inviteinfo**

* **Description :** Récupère les informations d’un serveur à partir de son lien d’invitation Discord — parfait pour les partenariats. 🌐
* **Usage :**

  ```
  /inviteinfo invite_link:<lien_discord>
  ```

---

### 🔹 **/kick**

* **Description :** Expulse un membre du serveur et enregistre l’action dans la base de données.
* **Usage :**

  ```
  /kick member:<@membre> reason:<raison>
  ```

---

### 🔹 **/make\_embed**

* **Description :** Crée un embed personnalisé avec une configuration simple. ✨
* **Usage :**

  ```
  /make_embed channel:<#salon>
  ```

---

### 🔹 **/massrole**

* **Description :** Attribue ou retire massivement un rôle à tous les membres du serveur.
* **Usage :**

  ```
  /massrole add role:<@rôle>
  /massrole remove role:<@rôle>
  ```

---

### 🔹 **/member-stats**

* **Description :** Affiche vos statistiques au sein du serveur (depuis le jour où le bot a rejoint). 📈
* **Usage :**

  ```
  /member-stats
  ```

---

### 🔹 **/profile\_setup**

* **Description :** Lance la configuration du système de profils : chaque membre peut se décrire et recevoir des « likes » anonymes jusqu’à approbation. ❤️
* **Usage :**

  ```
  /profile_setup
  ```

---

### 🔹 **/profile**

* **Description :** Affiche votre profil configuré. Utile uniquement si l’administrateur a exécuté `/profile_setup`.
* **Usage :**

  ```
  /profile
  ```

---

### 🔹 **/roleconfig**

* **Description :** Définit quels rôles peuvent attribuer ou retirer d’autres rôles (sans donner la permission « Gérer les rôles »).
  Commandes associées : `/rolegive`, `/roleremove`.
* **Usage :**

  ```
  /roleconfig
  ```

---

### 🔹 **/rolesetup**

* **Description :** Met en place un joli système pour que vos membres s’attribuent eux-mêmes des rôles. Voir le tutoriel ! 🎨
* **Usage :**

  ```
  /rolesetup
  ```

---

### 🔹 **/server-stats**

* **Description :** Affiche les statistiques globales du serveur (membres, messages, etc.).
* **Usage :**

  ```
  /server-stats
  ```

---

### 🔹 **/serverinfo**

* **Description :** Affiche les informations détaillées du serveur (création, propriétaires, salons, etc.).
* **Usage :**

  ```
  /serverinfo
  ```

---

### 🔹 **/set\_confess**

* **Description :** Configure le salon et le bouton pour le système de confessions. Vous pouvez choisir un label ou un emoji. 🤫
* **Usage :**

  ```
  /set_confess channel:<#salon> button_label:<texte_ou_emoji>
  ```

---

### 🔹 **/set\_suggestion**

* **Description :** Configure le salon de suggestions : soumission, approbation ou refus. 💡
* **Usage :**

  ```
  /set_suggestion channel:<#salon>
  ```

---

### 🔹 **/snipe**

* **Description :** Affiche le dernier message supprimé dans le salon. 👀
* **Usage :**

  ```
  /snipe
  ```

---

### 🔹 **/soutien**

* **Description :** Permet aux membres de choisir un statut personnalisé (ex. « patate ») et d’obtenir automatiquement le rôle associé. 🥔
* **Usage :**

  ```
  /soutien
  ```

---

### 🔹 **/userinfo**

* **Description :** Affiche les informations d’un membre (join date, rôles, etc.).
* **Usage :**

  ```
  /userinfo user:<@membre>
  ```

---

*Toutes les explications ont été revues pour garantir clarté et cohérence !* 😎


suite =>

/custom-voc
Permet de configuré les salon custom vocaux & modifiable pour les membres.
