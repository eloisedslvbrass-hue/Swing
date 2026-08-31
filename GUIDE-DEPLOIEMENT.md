# Guide de déploiement — DiorArchives Feed
### Pour quelqu'un qui n'a jamais déployé de site. Suis les étapes dans l'ordre, sans en sauter.

Tu vas faire 4 choses, dans cet ordre :
1. Mettre le code du backend sur GitHub (comme une boîte de rangement en ligne)
2. Brancher cette boîte sur Render (qui va faire tourner le backend 24h/24)
3. Programmer un rappel automatique toutes les 10 minutes (cron-job.org)
4. Mettre le site (le HTML) en ligne sur Netlify

Compte à créer : GitHub, Render, cron-job.org, Netlify — tous gratuits, juste un email suffit.

---

## ÉTAPE 1 — Mettre le backend sur GitHub

1. Va sur **github.com** → "Sign up" → crée un compte gratuit.
2. Une fois connecté, clique sur le **+** en haut à droite → **"New repository"**.
3. Donne-lui un nom, par exemple `diorarchives-backend`. Laisse le reste par défaut.
   Clique **"Create repository"**.
4. Sur la page qui s'affiche, cherche le lien **"uploading an existing file"**
   (ou le bouton **"Add file" → "Upload files"**).
5. Glisse-dépose ces 3 fichiers que je t'ai fournis :
   - `app.py`
   - `requirements.txt`
   - (pas besoin des autres fichiers Python, `app.py` contient déjà tout)
6. En bas de page, clique **"Commit changes"** (le bouton vert).

✅ Ton code est maintenant en ligne sur GitHub (mais ne tourne pas encore).

---

## ÉTAPE 2 — Faire tourner le backend sur Render

1. Va sur **render.com** → crée un compte (tu peux te connecter directement
   avec ton compte GitHub, c'est plus simple).
2. Clique **"New +"** → **"Web Service"**.
3. Autorise Render à accéder à ton compte GitHub si demandé, puis sélectionne
   le dépôt `diorarchives-backend` que tu viens de créer.
4. Render va proposer des réglages. Vérifie/complète :
   - **Name** : ce que tu veux (ex: `diorarchives-api`)
   - **Runtime** : Python 3
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app`
   - **Instance Type** : **Free**
5. Clique **"Create Web Service"**. Render installe et démarre ton code
   (ça prend 2-3 minutes, tu vois défiler des logs).
6. Une fois que c'est prêt, en haut de la page tu verras une URL du style :
   `https://diorarchives-api.onrender.com`
   👉 **Copie cette URL, tu en as besoin pour la suite.**
7. Vérifie que ça marche : ouvre dans ton navigateur
   `https://diorarchives-api.onrender.com/api/listings`
   Tu dois voir apparaître du texte au format JSON (des accolades, des
   crochets). Si oui, c'est gagné. Ça peut prendre 30-60 secondes à charger
   la première fois (le site va chercher les annonces).

⚠️ Sur le plan gratuit, Render met le service en pause après 15 minutes
sans visite. L'étape 3 règle ce problème.

---

## ÉTAPE 3 — Garder le backend réveillé et à jour

1. Va sur **cron-job.org** → crée un compte gratuit.
2. Clique **"Create cronjob"**.
3. Dans **"URL"**, colle l'adresse de ton API suivie de `/api/listings` :
   `https://diorarchives-api.onrender.com/api/listings`
4. Dans **"Execution schedule"**, choisis **"Every 10 minutes"**.
5. Sauvegarde.

✅ Maintenant, toutes les 10 minutes, ce service va "sonner" ton backend :
ça le réveille s'il dormait, et ça déclenche une actualisation des annonces.

---

## ÉTAPE 4 — Mettre le site en ligne sur Netlify

1. D'abord, il faut dire au site où trouver ton backend :
   - Ouvre le fichier `index-live.html` avec un simple éditeur de texte
     (Bloc-notes sur Windows, TextEdit sur Mac — clic droit → "Ouvrir avec").
   - Cherche cette ligne (utilise Ctrl+F / Cmd+F pour la trouver) :
     ```
     const API_URL = "http://localhost:5000/api/listings";
     ```
   - Remplace `http://localhost:5000/api/listings` par TON URL Render,
     par exemple :
     ```
     const API_URL = "https://diorarchives-api.onrender.com/api/listings";
     ```
   - Enregistre le fichier.

2. Va sur **netlify.com** → crée un compte gratuit.
3. Une fois connecté, tu arrives sur ton tableau de bord. Cherche une zone
   qui dit **"Drag and drop your site output folder here"** (glisser-déposer).
4. Glisse simplement ton fichier `index-live.html` dedans.
5. Netlify le met en ligne en quelques secondes et te donne une adresse du style :
   `https://random-name-123.netlify.app`

✅ **C'est cette adresse que tu partages — c'est ton site, en ligne, pour de vrai.**

(Optionnel : dans les réglages du site sur Netlify, tu peux changer
`random-name-123` pour un nom plus parlant, ex: `diorarchives.netlify.app`,
et même brancher un vrai nom de domaine si tu en achètes un plus tard.)

---

## Pour vérifier que tout est connecté

1. Ouvre ton lien Netlify sur ton téléphone.
2. Le site doit se charger avec les annonces (au début ce seront peut-être
   les mêmes que les données de démo, le temps que le vrai scraping tourne).
3. Attends 10 minutes, recharge la page : si le scraping fonctionne, tu
   verras un petit toast "✨ X annonces à jour" et des annonces réelles
   de Grailed.

## Si quelque chose ne marche pas

Copie-moi le message d'erreur exact (dans les logs Render, onglet "Logs"
de ton service) et je t'aide à corriger. Les pannes les plus courantes :
- **"Impossible d'extraire les données"** dans les logs Render → Grailed a
  changé la structure de sa page, il faut ajuster `app.py` (je peux le faire
  avec toi si tu me montres le message).
- **Page blanche sur Netlify** → vérifie que tu as bien changé `API_URL`
  et réenregistré le fichier avant de le glisser sur Netlify.
- **Rien ne s'affiche du tout** → ouvre le lien de l'API directement dans
  le navigateur pour voir si elle répond (étape 2, point 7).
