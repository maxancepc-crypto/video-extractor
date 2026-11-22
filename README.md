# Video Extractor

Adrese url   (https://video-extractor-scfk.onrender.com/)
Prototype simple d’extraction de vidéos à partir d’une URL (YouTube, TikTok, Instagram, etc.).

## ⚠️ Avertissement légal

Ce projet est fourni **uniquement à des fins éducatives**.

- Le téléchargement de contenus protégés par le droit d’auteur **sans autorisation est illégal**.
- Les conditions d’utilisation de YouTube, TikTok, Instagram, etc. interdisent généralement ce type d’extraction.
- Vous êtes **entièrement responsable** de l’usage que vous faites de cet outil.
- Ne l’hébergez pas publiquement si vous n’êtes pas prêt à gérer les risques juridiques (DMCA, etc.).






## Fonctionnement

1. L’utilisateur colle une URL
2. Le backend utilise **yt-dlp** pour télécharger la meilleure qualité disponible
3. La vidéo est stockée temporairement (supprimée automatiquement après 1 heure)
4. Un lien de téléchargement est proposé à l’utilisateur




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
