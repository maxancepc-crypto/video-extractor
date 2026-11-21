# Video Extractor

Adrese url https://gallant-heart-production-a8e9e552.up.railway.app/

Prototype simple d’extraction de vidéos à partir d’une URL (YouTube, TikTok, Instagram, etc.).

## ⚠️ Avertissement légal

Ce projet est fourni **uniquement à des fins éducatives**.

- Le téléchargement de contenus protégés par le droit d’auteur **sans autorisation est illégal**.
- Les conditions d’utilisation de YouTube, TikTok, Instagram, etc. interdisent généralement ce type d’extraction.
- Vous êtes **entièrement responsable** de l’usage que vous faites de cet outil.
- Ne l’hébergez pas publiquement si vous n’êtes pas prêt à gérer les risques juridiques (DMCA, etc.).

## Prérequis

- Python 3.10 ou supérieur
- `pip`

## Installation

```bash
# 1. Cloner / télécharger le projet
cd video-extractor

# 2. Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate        # Linux / macOS
# ou
venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

Ouvre ensuite ton navigateur sur :  
→ **http://127.0.0.1:5000**

## Fonctionnement

1. L’utilisateur colle une URL
2. Le backend utilise **yt-dlp** pour télécharger la meilleure qualité disponible
3. La vidéo est stockée temporairement (supprimée automatiquement après 1 heure)
4. Un lien de téléchargement est proposé à l’utilisateur

## Déploiement (optionnel)

Tu peux déployer facilement sur :
- [Railway](https://railway.app)
- [Render](https://render.com)
- [Fly.io](https://fly.io)
- Un VPS classique (avec gunicorn)

Exemple avec gunicorn :
```bash
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

## Limitations

- Pas de gestion des playlists
- Pas de choix de qualité (prend le meilleur format mp4)
- Les fichiers sont stockés temporairement sur le serveur
- Certaines plateformes peuvent bloquer les extractions massives

## Améliorations possibles

- Choix de la qualité / format
- Support des playlists
- Authentification
- File d’attente (Celery + Redis)
- Interface plus avancée
- Limite de taille / durée

---

Créé à titre éducatif.
