from flask import Flask, request, jsonify, send_from_directory, render_template
import yt_dlp
import os
import uuid
import threading
import time
from pathlib import Path

app = Flask(__name__)

# Dossier où les vidéos téléchargées seront stockées temporairement
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Nettoyage automatique des fichiers de plus de 1 heure
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for file in DOWNLOAD_DIR.iterdir():
                if file.is_file() and (now - file.stat().st_mtime) > 3600:
                    file.unlink()
        except Exception:
            pass
        time.sleep(600)  # Vérifie toutes les 10 minutes

# Lancer le nettoyage en arrière-plan
threading.Thread(target=cleanup_old_files, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL manquante"}), 400

    # Options yt-dlp
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Parfois le nom de fichier change après merge
            if not os.path.exists(filename):
                # Cherche le fichier le plus récent dans le dossier
                files = list(DOWNLOAD_DIR.glob("*"))
                if not files:
                    return jsonify({"error": "Échec du téléchargement"}), 500
                filename = max(files, key=lambda f: f.stat().st_mtime)

            file_id = Path(filename).name

            return jsonify({
                "success": True,
                "title": info.get("title", "Vidéo"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "download_url": f"/download/{file_id}",
                "filename": file_id
            })

    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'extraction : {str(e)}"}), 500


@app.route("/download/<filename>")
def download(filename):
    # Sécurité basique : on ne sert que les fichiers du dossier downloads
    safe_path = DOWNLOAD_DIR / filename
    if not safe_path.exists() or not safe_path.is_file():
        return "Fichier introuvable ou expiré", 404

    return send_from_directory(
        DOWNLOAD_DIR,
        filename,
        as_attachment=True,
        download_name=filename
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Serveur démarré sur le port {port}")
    app.run(debug=False, host="0.0.0.0", port=port)
