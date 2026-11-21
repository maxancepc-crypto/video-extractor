import html as htmllib
import ipaddress
import os
import re
import socket
import unicodedata
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
VIDEO_EXT = (".mp4", ".webm", ".mov", ".m4v", ".mkv", ".ogv")
BLOCKED_SITES = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com")
MAX_REDIRECTS = 3
MAX_PAGE_BYTES = 2_000_000
MAX_CANDIDATES = 6


# ---------- Sécurité réseau ----------

def check_url(url):
    """Refuse les URL invalides, les sites non pris en charge et les adresses internes."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("URL invalide.")
    host = p.hostname.lower()
    if any(host == d or host.endswith("." + d) for d in BLOCKED_SITES):
        raise ValueError("Ce site n'est pas pris en charge (il interdit les téléchargements depuis un serveur).")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror:
        raise ValueError("Adresse introuvable.")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("Adresse non autorisée.")


def open_remote(url, referer=None):
    """Ouvre l'URL en suivant les redirections à la main (en vérifiant chaque étape)."""
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        r = requests.get(url, headers=headers, stream=True, timeout=15, allow_redirects=False)
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


def probe(url, referer=None):
    """Retourne (url_finale, taille) si l'URL est un fichier vidéo accessible, sinon None."""
    try:
        r, final = open_remote(url, referer)
    except (ValueError, requests.RequestException):
        return None
    try:
        if r.status_code < 400 and is_video(r, final):
            size = r.headers.get("Content-Length")
            return final, int(size) if size and size.isdigit() else None
    finally:
        r.close()
    return None


# ---------- Noms de fichiers ----------

def ascii_name(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._ -]", "_", text).strip(" ._")


def ext_of(url):
    path = urlparse(url).path.lower()
    for e in VIDEO_EXT:
        if path.endswith(e):
            return e
    return ".mp4"


def make_name(title, video_url):
    base = ascii_name(title)[:80] or "video"
    ext = ext_of(video_url)
    return base if base.lower().endswith(ext) else base + ext


def filename_from(url):
    return make_name(os.path.basename(unquote(urlparse(url).path)) or "video", url)


# ---------- Analyse d'une page web ----------

class PageParser(HTMLParser):
    META_KEYS = ("og:video:secure_url", "og:video:url", "og:video", "twitter:player:stream")

    def __init__(self):
        super().__init__()
        self.meta_videos = []
        self.tag_videos = []
        self.og_title = ""
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            content = a.get("content") or ""
            if key in self.META_KEYS and content:
                self.meta_videos.append(content)
            elif key == "og:title" and content and not self.og_title:
                self.og_title = content
        elif tag in ("video", "source") and a.get("src"):
            self.tag_videos.append(a["src"])
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


RAW_MP4 = re.compile(r"""https?:\\?/\\?/[^"'\s<>\\]*?(?:\\/[^"'\s<>]*?)*\.(?:mp4|webm|mov|m4v)[^"'\s<>]*""", re.I)


def find_candidates(page_html, base_url):
    parser = PageParser()
    try:
        parser.feed(page_html)
    except Exception:
        pass
    raw = parser.meta_videos + parser.tag_videos
    raw += [m.group(0).replace("\\/", "/") for m in RAW_MP4.finditer(page_html)]
    seen, out = set(), []
    for c in raw:
        full = urljoin(base_url, htmllib.unescape(c.strip()))
        if full.startswith(("http://", "https://")) and full not in seen:
            seen.add(full)
            out.append(full)
    title = (parser.og_title or parser.title or "").strip()
    return out[:MAX_CANDIDATES], title


def read_text(resp):
    chunks, total = [], 0
    for chunk in resp.iter_content(65536):
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_PAGE_BYTES:
            break
    return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")


# ---------- Secours : yt-dlp ----------

def ytdlp_direct(url):
    """Cherche un fichier vidéo direct via yt-dlp. Retourne (url, titre, taille) ou None."""
    try:
        import yt_dlp
    except ImportError:
        return None
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "format": "best[ext=mp4][protocol=https]/best[ext=mp4][protocol=http]/best[protocol=https]/best[protocol=http]",
        "allowed_extractors": ["default", "-generic"],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None
    vurl = (info or {}).get("url")
    if not vurl or info.get("requested_formats"):
        return None
    found = probe(vurl, referer=url)
    if not found:
        return None
    return found[0], info.get("title") or "video", found[1]


# ---------- Routes ----------

def ok(video_url, title, size, referer=None):
    dl = "/download?url=" + quote(video_url, safe="") + "&name=" + quote(title, safe="")
    if referer:
        dl += "&ref=" + quote(referer, safe="")
    return jsonify(title=title, size=size, preview_url=video_url, download_url=dl)


@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")


@app.route("/extract", methods=["POST"])
def extract():
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not url:
        return jsonify(error="Colle une URL."), 400
    try:
        r, final = open_remote(url)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except requests.RequestException:
        return jsonify(error="Impossible de joindre ce lien (il a peut-être expiré)."), 400

    try:
        if r.status_code >= 400:
            return jsonify(error=f"Le serveur a répondu avec l'erreur {r.status_code}."), 400
        if is_video(r, final):
            size = r.headers.get("Content-Length")
            return ok(final, filename_from(final), int(size) if size and size.isdigit() else None)
        if "html" not in r.headers.get("Content-Type", "").lower():
            return jsonify(error="Ce lien n'est ni une page web ni un fichier vidéo."), 400
        page = read_text(r)
    except requests.RequestException:
        return jsonify(error="Erreur pendant la lecture de la page."), 400
    finally:
        r.close()

    # 1) Vidéo trouvée dans le code de la page
    candidates, title = find_candidates(page, final)
    for cand in candidates:
        found = probe(cand, referer=final)
        if found:
            name = make_name(title or "video", found[0])
            return ok(found[0], name, found[1], referer=final)

    # 2) Secours : yt-dlp
    res = ytdlp_direct(final)
    if res:
        vurl, vtitle, size = res
        return ok(vurl, make_name(vtitle, vurl), size, referer=final)

    return jsonify(error="Aucune vidéo téléchargeable trouvée sur cette page "
                         "(elle peut être protégée, en streaming ou réservée aux comptes connectés)."), 400


@app.route("/download")
def download():
    url = request.args.get("url", "").strip()
    ref = request.args.get("ref", "").strip() or None
    try:
        r, final = open_remote(url, referer=ref)
    except (ValueError, requests.RequestException):
        return "Lien invalide ou expiré.", 400
    if r.status_code >= 400 or not is_video(r, final):
        r.close()
        return "Fichier indisponible.", 400

    name = make_name(request.args.get("name", "") or filename_from(final), final)
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    if r.headers.get("Content-Length"):
        headers["Content-Length"] = r.headers["Content-Length"]
    return Response(
        stream_with_context(r.iter_content(chunk_size=64 * 1024)),
        content_type=r.headers.get("Content-Type", "video/mp4"),
        headers=headers,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
