#!/usr/bin/env python3
import html
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

JOURNAL = "International Journal of Wildland Fire"
ISSN = "1448-5516"
OUTPUT = Path("docs/ijwf.xml")
DAYS_BACK = 120
ROWS = 100


def crossref_items():
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).date().isoformat()
    params = {
        "filter": f"from-pub-date:{since}",
        "sort": "published",
        "order": "desc",
        "rows": ROWS,
    }
    url = f"https://api.crossref.org/journals/{ISSN}/works?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "IJWF-RSS/1.0 (mailto:gvacchiano@gmail.com)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data["message"]["items"]


def date_parts(item):
    for key in ("published-online", "published-print", "issued"):
        parts = item.get(key, {}).get("date-parts")
        if parts and parts[0]:
            p = parts[0]
            y = p[0]
            m = p[1] if len(p) > 1 else 1
            d = p[2] if len(p) > 2 else 1
            return datetime(y, m, d, tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def author_text(item):
    names = []
    for a in item.get("author", []):
        name = " ".join(x for x in [a.get("given", ""), a.get("family", "")] if x).strip()
        if name:
            names.append(name)
    return ", ".join(names)


def title_text(item):
    t = item.get("title") or []
    return t[0].strip() if t else "(untitled)"


def main():
    items = crossref_items()
    clean = []
    seen = set()
    for item in items:
        containers = item.get("container-title") or []
        if containers and JOURNAL.lower() not in containers[0].lower():
            continue
        doi = (item.get("DOI") or "").lower()
        if not doi or doi in seen:
            continue
        seen.add(doi)
        clean.append(item)

    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = f"{JOURNAL} — latest articles"
    SubElement(channel, "link").text = "https://connectsci.au/wf"
    SubElement(channel, "description").text = "Feed generated from Crossref metadata for the International Journal of Wildland Fire."
    SubElement(channel, "language").text = "en"
    SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))

    for item in clean:
        doi = item["DOI"]
        url = item.get("URL") or f"https://doi.org/{doi}"
        pubdate = date_parts(item)
        title = title_text(item)
        authors = author_text(item)

        it = SubElement(channel, "item")
        SubElement(it, "title").text = title
        SubElement(it, "link").text = url
        SubElement(it, "guid", {"isPermaLink": "false"}).text = f"doi:{doi}"
        SubElement(it, "pubDate").text = format_datetime(pubdate)
        desc_bits = []
        if authors:
            desc_bits.append(f"<strong>Authors:</strong> {html.escape(authors)}")
        desc_bits.append(f"<strong>DOI:</strong> <a href='https://doi.org/{html.escape(doi)}'>{html.escape(doi)}</a>")
        SubElement(it, "description").text = "<br/>".join(desc_bits)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tree = ElementTree(rss)
    try:
        from xml.etree.ElementTree import indent
        indent(tree, space="  ")
    except ImportError:
        pass
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {len(clean)} items to {OUTPUT}")


if __name__ == "__main__":
    main()
