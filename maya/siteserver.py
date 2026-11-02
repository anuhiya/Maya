"""A tiny local web server for the fictional regulator site (A2, P8).

It serves only what the site index lists: the index page, one page per bulletin, the TXT and PDF files and
index.json. Held-back versions are never served. Localhost only, started once per process.
"""
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from maya import site

_servers: dict[str, tuple[ThreadingHTTPServer, str]] = {}
_lock = threading.Lock()
TYPES = {".txt": "text/plain; charset=utf-8", ".pdf": "application/pdf", ".json": "application/json"}


def _bulletin_page(cfg, entry):
    site_dir = site._paths(cfg)[0]
    text = (site_dir / entry["file"]).read_text(encoding="utf-8")
    pdf = f' <a href="../{html.escape(entry["pdf"])}">PDF</a>' if entry.get("pdf") else ""
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(entry['title'])}</title><style>{site.PAGE_STYLE}</style></head><body>\n"
            "<div class=\"banner\">Synthetic site. Place names are real; wage rates, rules and dates are illustrative, not the actual law.</div>\n"
            f"<p><a href=\"../\">All bulletins</a></p><h1>{html.escape(entry['title'])}</h1>\n"
            f"<p>Issued {html.escape(entry['issued'])}. <a href=\"../{html.escape(entry['file'])}\">TXT</a>{pdf}</p>\n"
            f"<pre>{html.escape(text)}</pre></body></html>\n").encode("utf-8")


def _handler(cfg):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the app's terminal quiet
            pass

        def _send(self, code, body, kind="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            site_dir, _, index_file, _ = site._paths(cfg)
            path = unquote(urlparse(self.path).path)
            try:
                entries = json.loads(index_file.read_text(encoding="utf-8"))["documents"]
            except (OSError, ValueError):
                return self._send(503, b"The site index is not available.", "text/plain")
            if path in ("/", "/index.html"):
                return self._send(200, site.index_page(cfg).encode("utf-8"))
            if path == "/index.json":
                return self._send(200, index_file.read_bytes(), TYPES[".json"])
            if path.startswith("/bulletin/"):
                entry = next((e for e in entries if site.bulletin_slug(e) == path.split("/", 2)[2]), None)
                return self._send(200, _bulletin_page(cfg, entry)) if entry else self._send(404, b"Not found", "text/plain")
            names = {n for e in entries for n in (e["file"], e.get("pdf")) if n}
            name = path.lstrip("/")
            if name in names and (site_dir / name).is_file():
                return self._send(200, (site_dir / name).read_bytes(), TYPES.get(Path(name).suffix, "application/octet-stream"))
            return self._send(404, b"Not found", "text/plain")

    return Handler


def ensure_running(cfg) -> str:
    """Start the server for this config's site folder if it is not running; return its base URL."""
    key = str(site._paths(cfg)[0])
    with _lock:
        if key in _servers:
            return _servers[key][1]
        settings = cfg["site"].get("server") or {}
        host, port = settings.get("host", "127.0.0.1"), int(settings.get("port", 0))
        try:
            server = ThreadingHTTPServer((host, port), _handler(cfg))
        except OSError:  # the port is taken: use any free one
            server = ThreadingHTTPServer((host, 0), _handler(cfg))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://{host}:{server.server_address[1]}"
        _servers[key] = (server, url)
        return url


def stop_all() -> None:
    with _lock:
        for server, _ in _servers.values():
            server.shutdown()
            server.server_close()
        _servers.clear()
