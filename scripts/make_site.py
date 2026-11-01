#!/usr/bin/env python3
"""Wrap src/dashboard.html (written as an Artifact page body) into index.html for GitHub Pages.

The Artifact publisher adds the document skeleton itself; GitHub Pages needs a full document.
index.html loads data/dashboard.json from the same site, exactly like the published Artifact.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "dashboard.html"
OUT = ROOT / "index.html"
MARK = "<!-- BODY -->"


def main():
    src = SRC.read_text(encoding="utf-8")
    head, body = src.split(MARK, 1) if MARK in src else ("", src)
    page = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
        "img{max-width:100%}</style>\n"
        f"{head.strip()}\n</head>\n<body>\n{body.strip()}\n</body>\n</html>\n"
    )
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(page)//1024} KB)")


if __name__ == "__main__":
    main()
