import ipaddress
import os
import re
import socket
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

app = Flask(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VideoExtractor/1.0)"}
VIDEO_EXT = (".mp4", ".webm", ".mov", ".m4v", ".mkv", ".ogv")
BLOCKED_SITES = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com")
MAX_REDIRECTS = 3


def check_url(url):
    """Refuse les URL invalides, les sites non pris en charge et les adresses internes."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("URL invalide.")
    host = p.hostname.lower()
    if any(host == d or host.endswith("." + d) for d in BLOCKED_SITES):
        raise ValueError("Ce site n'est pas pris en charge. Utilise un lien direct vers un fichier vidéo.")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror:
        raise ValueError("Adresse introuvable.")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("Adresse non autorisée.")


def open_remote(url):
    """Ouvre l'URL en suivant les redirections à la main (en vérifiant chaque étape)."""
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        r = requests.get(url, headers=HEADERS, stream=True, timeout=15, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, r.headers.get("Location", ""))
            r.close()
            continue
        return r, url
    raise ValueError("Trop de redirections.")


def is_video(resp, url):
    ctype = resp.headers.get("Content-Type", "").lower()
    path = urlparse(url).path.lower()
    return ctype.startswith("video/") or path.endswith(VIDEO_EXT)


def filename_from(url):
    name = os.path.basename(unquote(urlparse(url).path)) or "video.mp4"
    name = re.sub(r'[^\w.\- ]', "_", name)
    if not name.lower().endswith(VIDEO_EXT):
        name += ".mp4"
    return name


@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")


@app.route("/extract", methods=["POST"])
def extract():
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not url:
        return jsonify(error="Colle une URL."), 400
    try:
        r, final_url = open_remote(url)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except requests.RequestException:
        return jsonify(error="Impossible de joindre ce lien (il a peut-être expiré)."), 400

    try:
        if r.status_code >= 400:
            return jsonify(error=f"Le serveur a répondu avec l'erreur {r.status_code}."), 400
        if not is_video(r, final_url):
            return jsonify(error="Ce lien ne pointe pas vers un fichier vidéo."), 400
        size = r.headers.get("Content-Length")
        return jsonify(
            title=filename_from(final_url),
            size=int(size) if size and size.isdigit() else None,
            preview_url=final_url,
            download_url="/download?url=" + quote(final_url, safe=""),
        )
    finally:
        r.close()


@app.route("/download")
def download():
    url = request.args.get("url", "").strip()
    try:
        r, final_url = open_remote(url)
    except (ValueError, requests.RequestException):
        return "Lien invalide ou expiré.", 400
    if r.status_code >= 400 or not is_video(r, final_url):
        r.close()
        return "Fichier indisponible.", 400

    headers = {"Content-Disposition": f'attachment; filename="{filename_from(final_url)}"'}
    if r.headers.get("Content-Length"):
        headers["Content-Length"] = r.headers["Content-Length"]
    return Response(
        stream_with_context(r.iter_content(chunk_size=64 * 1024)),
        content_type=r.headers.get("Content-Type", "video/mp4"),
        headers=headers,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
