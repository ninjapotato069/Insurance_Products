#!/usr/bin/env python3
"""Download public source files (PDF, Excel, HTML) for research.

Run by .github/workflows/fetch-sources.yml (workflow_dispatch). Reads URLS (space/newline separated) and TAG
from the environment, saves each file to _raw/<tag>/ with an index.json (status, type, size, sha256 and, for
HTML pages, every link on the page so the next fetch can follow them). The workflow commits _raw/ to the
`raw-sources` branch, keeping main small. Research sessions without web access fetch that branch and parse
the files locally.
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
MAX_BYTES = 45 * 1024 * 1024


def safe(s, n=80):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-.")
    return (s or "file")[:n]


def main():
    tag = safe(os.environ.get("TAG") or "misc", 40).lower()
    urls = [u for u in re.split(r"\s+", os.environ.get("URLS", "")) if u.startswith(("http://", "https://"))]
    out = Path("_raw") / tag
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9",
                      "Accept": "text/html,application/xhtml+xml,application/pdf,application/vnd.ms-excel,*/*;q=0.8"})
    index = []
    for i, url in enumerate(urls, 1):
        rec = {"n": i, "url": url}
        try:
            r = None
            for attempt in range(3):
                try:
                    r = s.get(url, timeout=90, stream=True, allow_redirects=True)
                    break
                except requests.RequestException as e:
                    rec["error"] = str(e)[:200]
                    time.sleep(3 * (attempt + 1))
            if r is None:
                index.append(rec)
                continue
            rec.update({"status": r.status_code, "final_url": r.url,
                        "content_type": r.headers.get("content-type", "")})
            data = b""
            for chunk in r.iter_content(65536):
                data += chunk
                if len(data) > MAX_BYTES:
                    rec["error"] = "too large, truncated"
                    break
            ct = rec["content_type"].lower()
            ext = Path(urlparse(r.url).path).suffix.lower()
            if "pdf" in ct:
                ext = ".pdf"
            elif "html" in ct:
                ext = ".html"
            elif "spreadsheetml" in ct:
                ext = ".xlsx"
            elif "ms-excel" in ct and ext not in (".xls", ".xlsx"):
                ext = ".xls"
            elif "json" in ct:
                ext = ".json"
            elif "xml" in ct and ext not in (".xml", ".rss"):
                ext = ".xml"
            if not ext or len(ext) > 6:
                ext = ".bin"
            name = f"{i:02d}_{safe(Path(urlparse(r.url).path).stem or urlparse(r.url).netloc)}{ext}"
            (out / name).write_bytes(data)
            rec.update({"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            if ext == ".html":
                soup = BeautifulSoup(data, "html.parser")
                rec["title"] = (soup.title.string or "").strip()[:200] if soup.title else ""
                links = []
                for a in soup.find_all("a", href=True):
                    href = urljoin(r.url, a["href"].strip())
                    if href.startswith("http"):
                        links.append([" ".join(a.get_text(" ", strip=True).split())[:160], href])
                rec["links"] = links[:3000]
        except Exception as e:  # keep going; the index records the failure
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
        index.append(rec)
        print(f"{i:02d} {rec.get('status')} {rec.get('bytes')} {url} {rec.get('error', '')}", flush=True)
        time.sleep(1)
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))
    Path("_raw/.last_tag").write_text(tag)
    ok = sum(1 for x in index if x.get("status") == 200)
    print(f"{ok}/{len(index)} fetched into _raw/{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
