#!/usr/bin/env python3
"""Build the static blog from content/posts/*.md into _site/.

Posts use the seomachine draft format: a `---` block of `Key: Value` lines
(Meta Title, Meta Description, URL Slug, Last Updated, ...) followed by Markdown.
Affiliate placeholders like {{AFF_JOBBER}} are filled from config.json.
"""
import html
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
CONFIG = json.loads((ROOT / "config.json").read_text())
BASE = os.environ.get("SITE_BASE_URL", CONFIG["base_url"]).rstrip("/")  # override for local preview
BASE_PATH = re.sub(r"^https?://[^/]+", "", BASE)  # "/REPO" on a project site, "" on a custom domain


def parse_post(path):
    raw = path.read_text()
    meta, body = {}, raw
    if raw.startswith("---"):
        _, front, body = raw.split("---", 2)
        for line in front.strip().splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                meta[key.strip()] = value.strip()
    slug = meta.get("URL Slug", path.stem).strip("/").split("/")[-1]
    h1 = re.search(r"^# (.+)$", body, re.M)
    return {
        "slug": slug,
        "title": meta.get("Meta Title", h1.group(1) if h1 else slug),
        "h1": h1.group(1) if h1 else slug,
        "description": meta.get("Meta Description", ""),
        "updated": meta.get("Last Updated", date.today().isoformat()),
        "author": meta.get("Author", "") if "[" not in meta.get("Author", "[") else CONFIG["author"],
        "body": body,
    }


def url(path):
    return f"{BASE_PATH}/{path.strip('/')}/" if path.strip("/") else f"{BASE_PATH}/"


def render_body(post, published_slugs):
    body = re.sub(r"^# .+$", "", post["body"], count=1, flags=re.M)

    def fill_affiliate(m):
        return CONFIG["affiliate_links"].get(m.group(1), "#")

    body = re.sub(r"\{\{(AFF_[A-Z0-9_]+)\}\}", fill_affiliate, body)

    # Internal links to posts that aren't published yet become plain text, so we never ship 404s.
    def internal_link(m):
        text, target = m.group(1), m.group(2)
        slug = target.strip("/")
        if slug in published_slugs:
            return f"[{text}]({url(slug)})"
        print(f"  note: '{post['slug']}' links to unpublished /{slug}/, rendered as text")
        return text

    body = re.sub(r"\[([^\]]+)\]\((/[^)]*)\)", internal_link, body)
    # Python-Markdown needs a blank quoted line before a list inside a blockquote.
    body = re.sub(r"^(> (?!- ).+)\n(> - )", r"\1\n>\n\2", body, flags=re.M)
    out = markdown.markdown(body, extensions=["tables", "toc", "sane_lists"])
    affiliate_hosts = {re.sub(r"^https?://(www\.)?", "", u).split("/")[0] for u in CONFIG["affiliate_links"].values()}

    def mark_external(m):
        href = m.group(1)
        host = re.sub(r"^https?://(www\.)?", "", href).split("/")[0]
        rel = "sponsored nofollow noopener" if host in affiliate_hosts else "noopener"
        return f'<a href="{href}" rel="{rel}" target="_blank">'

    out = re.sub(r'<a href="(https?://[^"]+)">', mark_external, out)
    return enhance(out)


def ad_slot():
    ads = CONFIG.get("ads", {})
    if not ads.get("enabled") or not ads.get("adsense_client"):
        return ""
    return (f'<div class="ad-slot"><ins class="adsbygoogle" style="display:block" '
            f'data-ad-client="{ads["adsense_client"]}" data-ad-slot="{ads.get("slot", "")}" '
            f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            f'<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script></div>')


def ads_head():
    ads = CONFIG.get("ads", {})
    if not ads.get("enabled") or not ads.get("adsense_client"):
        return ""
    return (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            f'?client={ads["adsense_client"]}" crossorigin="anonymous"></script>')


def enhance(out):
    """Reading aids: styled disclosure, scrollable tables, CTA buttons, table of contents, ad slots."""
    out = re.sub(r"<blockquote>\n<p><strong>Disclosure:", '<blockquote class="disclosure">\n<p><strong>Disclosure:', out, count=1)
    out = out.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    # Links whose text ends with an arrow are calls to action.
    out = re.sub(r'<a ([^>]*)>([^<]*→)</a>', r'<a class="btn" \1>\2</a>', out)

    headings = re.findall(r'<h2 id="([^"]+)">(.+?)</h2>', out)
    if len(headings) >= 3:
        items = "".join(f'<li><a href="#{hid}">{re.sub("<[^>]+>", "", text)}</a></li>' for hid, text in headings)
        toc = f'<details class="toc" open><summary>In this guide</summary><ol>{items}</ol></details>'
        takeaways = re.search(r"<blockquote>\n<p><strong>Key Takeaways</strong>.*?</blockquote>", out, re.S)
        if takeaways:
            out = out[:takeaways.end()] + toc + out[takeaways.end():]
        else:
            out = out.replace(f'<h2 id="{headings[0][0]}">', toc + f'<h2 id="{headings[0][0]}">', 1)

    ad = ad_slot()
    if ad:
        if len(headings) >= 3:
            out = out.replace(f'<h2 id="{headings[2][0]}">', ad + f'<h2 id="{headings[2][0]}">', 1)
        if any(hid == "faq" for hid, _ in headings):
            out = out.replace('<h2 id="faq">', ad + '<h2 id="faq">', 1)
        out += ad
    return out


def faq_schema(post):
    section = re.search(r"^## FAQ\s*$(.+?)(?=^## |\Z)", post["body"], re.M | re.S)
    if not section:
        return None
    items = re.findall(r"^### (.+?)\n+(.+?)(?=\n### |\Z)", section.group(1), re.M | re.S)
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q.strip(),
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\s+", " ", a).strip()}}
            for q, a in items
        ],
    }


def page(title, description, canonical, content, schema=None):
    template = (ROOT / "templates" / "base.html").read_text()
    schema_tags = "".join(
        f'<script type="application/ld+json">{json.dumps(s)}</script>' for s in (schema or []) if s
    )
    return (template
            .replace("{{title}}", html.escape(title))
            .replace("{{description}}", html.escape(description))
            .replace("{{canonical}}", canonical)
            .replace("{{schema}}", schema_tags)
            .replace("{{ads_head}}", ads_head())
            .replace("{{site_name}}", html.escape(CONFIG["site_name"]))
            .replace("{{tagline}}", html.escape(CONFIG["tagline"]))
            .replace("{{lang}}", CONFIG["language"])
            .replace("{{base}}", BASE_PATH)
            .replace("{{year}}", str(date.today().year))
            .replace("{{content}}", content))


def write(rel, text):
    target = OUT / rel / "index.html" if rel else OUT / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    posts = sorted((parse_post(p) for p in (ROOT / "content" / "posts").glob("*.md")),
                   key=lambda p: p["updated"], reverse=True)
    slugs = {p["slug"] for p in posts}

    for post in posts:
        canonical = f"{BASE}/{post['slug']}/"
        article = {
            "@context": "https://schema.org", "@type": "Article",
            "headline": post["h1"], "description": post["description"],
            "dateModified": post["updated"], "author": {"@type": "Organization", "name": post["author"]},
            "publisher": {"@type": "Organization", "name": CONFIG["site_name"]},
            "mainEntityOfPage": canonical,
        }
        content = (f'<article><h1>{html.escape(post["h1"])}</h1>'
                   f'<p class="meta"><span>By {html.escape(post["author"])}</span><span>Updated {post["updated"]}</span>'
                   f'<span>{max(1, round(len(post["body"].split()) / 230))} min read</span></p>'
                   f'{render_body(post, slugs)}</article>')
        write(post["slug"], page(post["title"], post["description"], canonical, content,
                                 [article, faq_schema(post)]))

    cards = "".join(
        f'<li><a href="{url(p["slug"])}"><h2>{html.escape(p["h1"])}</h2></a>'
        f'<p>{html.escape(p["description"])}</p><p class="meta">Updated {p["updated"]}</p></li>'
        for p in posts)
    home = f'<section class="hero"><h1>{html.escape(CONFIG["tagline"])}</h1><p>Pricing breakdowns, comparisons and setup guides for cleaners, lawn care pros, handymen, HVAC and plumbing shops.</p></section><ul class="posts">{cards}</ul>'
    write("", page(f'{CONFIG["site_name"]}: {CONFIG["tagline"]}', CONFIG["tagline"], f"{BASE}/", home))

    for name in ("about", "affiliate-disclosure", "privacy"):
        md = (ROOT / "content" / f"{name}.md").read_text().replace("{{site_name}}", CONFIG["site_name"])
        title = re.search(r"^# (.+)$", md, re.M).group(1)
        write(name, page(f'{title} | {CONFIG["site_name"]}', title, f"{BASE}/{name}/",
                         f"<article>{markdown.markdown(md)}</article>"))

    (OUT / "404.html").write_text(page("Page not found", "Page not found", f"{BASE}/404.html",
                                       f'<article><h1>Page not found</h1><p><a href="{url("")}">Back to the homepage</a></p></article>'))
    pages = [""] + [p["slug"] for p in posts] + ["about", "affiliate-disclosure", "privacy"]
    sitemap = "".join(f"<url><loc>{BASE}/{p + '/' if p else ''}</loc></url>" for p in pages)
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap}</urlset>')
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    ads = CONFIG.get("ads", {})
    if ads.get("enabled") and ads.get("adsense_client"):
        # AdSense only reads ads.txt at the domain root, so this needs a custom domain.
        pub = ads["adsense_client"].replace("ca-", "")
        (OUT / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
    print(f"Built {len(posts)} post(s) into {OUT}")


if __name__ == "__main__":
    main()
