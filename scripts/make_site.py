#!/usr/bin/env python3
"""Wrap src/dashboard.html (written as an Artifact page body) into index.html for GitHub Pages, as an installable app.

The Artifact publisher adds the document skeleton itself; GitHub Pages needs a full document.
index.html loads data/dashboard.json and data/benchmark.json from the same site, like the published Artifact.
For GitHub Pages it also adds the web-app manifest, icons and a service worker (sw.js) so the dashboard installs
on Android and iPhone home screens and opens offline with the last data it saw.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "dashboard.html"
OUT = ROOT / "index.html"
MARK = "<!-- BODY -->"

APP = {
    "name": "Life Insurance Benchmark (India)",
    "short_name": "Life Benchmark",
    "description": "Every Indian life insurer benchmarked across 20 departments, with products, claims, ratings, ownership, strategy and news. Refreshed daily.",
    "start_url": "./#benchmark",
    "scope": "./",
    "display": "standalone",
    "orientation": "any",
    "background_color": "#f1f4f1",
    "theme_color": "#0b6a5a",
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
    "shortcuts": [
        {"name": "Scorecard", "url": "./#benchmark"},
        {"name": "Departments", "url": "./#dept-scale"},
        {"name": "News", "url": "./#news"},
    ],
}

HEAD_PWA = """<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0b6a5a">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Life Benchmark">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">"""

BODY_PWA = """<script>
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => { navigator.serviceWorker.register("sw.js").catch(() => {}); });
}
</script>"""

SW = """// Service worker: network first for the app and its data (so every visit gets the latest daily build),
// cached copy when offline; fonts cache first.
const VERSION = "lib-__VERSION__";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const put = res => { if (res && res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); } return res; };
  if (url.origin === self.location.origin) {
    e.respondWith(fetch(req).then(put).catch(() => caches.match(req, {ignoreSearch: true}).then(r => r || caches.match("index.html"))));
  } else if (/fonts\\.(googleapis|gstatic)\\.com$/.test(url.hostname)) {
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(put)));
  }
});
"""


def main():
    src = SRC.read_text(encoding="utf-8")
    head, body = src.split(MARK, 1) if MARK in src else ("", src)
    page = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
        "img{max-width:100%}</style>\n"
        f"{head.strip()}\n{HEAD_PWA}\n</head>\n<body>\n{body.strip()}\n{BODY_PWA}\n</body>\n</html>\n"
    )
    OUT.write_text(page, encoding="utf-8")
    (ROOT / "manifest.webmanifest").write_text(json.dumps(APP, indent=1), encoding="utf-8")
    stamp = hashlib.sha1((page + dt.date.today().isoformat()).encode()).hexdigest()[:10]
    (ROOT / "sw.js").write_text(SW.replace("__VERSION__", stamp), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(page)//1024} KB), manifest.webmanifest, sw.js ({stamp})")


if __name__ == "__main__":
    main()
