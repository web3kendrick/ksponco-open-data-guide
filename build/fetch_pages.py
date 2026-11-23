"""Fetch the 30 data.go.kr dataset pages (HTML only) into raw/pages/<date>/.

Usage: python build/fetch_pages.py 2026-11-23
Only the public dataset description pages are requested. Data files are never
downloaded by this script (download them by hand from each page).
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python build/fetch_pages.py YYYY-MM-DD")
    day = sys.argv[1]
    cfg = json.load(open(os.path.join(ROOT, "build", "datasets.json"), encoding="utf-8"))
    out = os.path.join(ROOT, "raw", "pages", day)
    os.makedirs(out, exist_ok=True)
    ids = [i for g in cfg["groups"] for i in g["ids"]]
    for n, i in enumerate(ids, 1):
        dst = os.path.join(out, i + ".html")
        if os.path.exists(dst) and os.path.getsize(dst) > 20000:
            print(n, i, "kept")
            continue
        url = cfg["portal_url"].format(id=i)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read()
        if b"application/ld+json" not in body:
            sys.exit("%s: page has no dataset metadata block (blocked or changed), stopped" % i)
        with open(dst, "wb") as f:
            f.write(body)
        print(n, i, len(body))
        time.sleep(1.5)


if __name__ == "__main__":
    main()
