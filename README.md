# Field Tools Guide (static blog)

Static affiliate blog for the "software for home-service pros" niche. Posts are written in `../seomachine`, then copied here and published to GitHub Pages.

## Layout
- `content/posts/*.md`: articles in seomachine draft format (`---` meta block + Markdown)
- `content/{about,affiliate-disclosure,privacy}.md`: static pages
- `config.json`: site name, base URL, affiliate links (`{{AFF_*}}` placeholders in posts)
- `templates/base.html`, `static/style.css`: design
- `build.py`: builds `_site/` (HTML, sitemap.xml, robots.txt, Article + FAQ schema)
- `.github/workflows/deploy.yml`: builds and deploys on every push to `main`

## Publish a new article
1. Write it in seomachine (`/research` → `/write` → `compliance-checker` → `/scrub` → `/optimize`)
2. `cp ../seomachine/drafts/<file>.md content/posts/<slug>.md`
3. Add any new affiliate placeholders to `config.json`
4. `git add -A && git commit -m "Add <slug>" && git push`

Internal links to posts that aren't published yet are rendered as plain text, and they become real links automatically once the target post exists.

## Ads (Google AdSense)
Ads are off by default. Once AdSense approves the site, set in `config.json`:
```json
"ads": { "enabled": true, "adsense_client": "ca-pub-XXXXXXXXXXXXXXXX", "slot": "1234567890" }
```
The build then adds the AdSense script, three ad slots per article (after the 2nd section, before the FAQ, at the end) and `ads.txt`. AdSense reads `ads.txt` only at the domain root, so ads need a custom domain, not `username.github.io/repo`.

## Local preview
```bash
SITE_BASE_URL=http://localhost:8765 ../seomachine/.venv/bin/python build.py && ../seomachine/.venv/bin/python -m http.server 8765 --directory _site
```

## First-time GitHub setup
1. Create an empty public repo on GitHub (e.g. `fieldtoolsguide`)
2. In `config.json`, set `base_url` to `https://<username>.github.io/<repo>` (or your custom domain)
3. Push this folder to the repo's `main` branch
4. Repo → Settings → Pages → Source: **GitHub Actions**
5. With a custom domain: add a `static/CNAME` file containing the domain, set `base_url` to `https://<domain>`, and point the domain's DNS to GitHub Pages
6. Submit `<base_url>/sitemap.xml` in Google Search Console
