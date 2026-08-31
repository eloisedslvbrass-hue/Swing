#!/usr/bin/env python3
"""
app.py — DiorArchives Feed backend (tout-en-un)
------------------------------------------------
Combine le scraper Grailed et l'API dans un seul service, pensé pour un
hébergement gratuit (Render, Railway...) qui met le service en veille
après inactivité.

Fonctionnement :
- Quand quelqu'un appelle /api/listings, on vérifie l'âge de listings.json.
- S'il a plus de 10 minutes (ou n'existe pas), on relance le scraping
  avant de répondre. Sinon on renvoie directement le cache.
- Un service externe et gratuit (cron-job.org) appellera cette route
  toutes les 10 minutes : ça rafraîchit les données ET empêche le
  service de s'endormir. Voir GUIDE-DEPLOIEMENT.md.

Dépendances : requirements.txt fourni à côté.
"""

import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BRANDS = ["Dior", "Balmain", "Saint Laurent"]
OUTPUT_FILE = Path(__file__).parent / "listings.json"
REFRESH_EVERY_SECONDS = 600  # 10 minutes
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DiorArchivesFeed/1.0; +contact@example.com)"
}
BASE_SEARCH_URL = "https://www.grailed.com/shop/{query}"


# ---------------- Scraping ----------------

def make_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def fetch_search_page(brand: str) -> str:
    query = brand.replace(" ", "-")
    url = BASE_SEARCH_URL.format(query=query)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def extract_next_data(html: str):
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None
    try:
        return json.loads(tag.string)
    except (json.JSONDecodeError, TypeError):
        return None


def parse_listing(raw: dict, brand: str):
    try:
        title = raw.get("title") or raw.get("name")
        if not title:
            return None
        price = raw.get("price")
        price_str = f"€{price}" if price else "N/A"
        photos = raw.get("photos") or raw.get("images") or []
        image_urls = [p.get("url") if isinstance(p, dict) else p for p in photos]
        image_urls = [u for u in image_urls if u]
        seller = raw.get("seller", {}) or {}
        username = seller.get("username") or "vendeur_inconnu"
        listing_url = raw.get("url") or raw.get("permalink") or ""
        if listing_url and not listing_url.startswith("http"):
            listing_url = f"https://www.grailed.com{listing_url}"
        item_id = make_id(listing_url or title)
        return {
            "id": item_id,
            "image": image_urls[0] if image_urls else "",
            "images": image_urls,
            "username": username,
            "badge": f"Photo · {datetime.now().strftime('%-d-%-m')}",
            "title": title,
            "description": raw.get("description", "")[:140],
            "likes": raw.get("favoriters_count", 0) or 0,
            "comments": 0,
            "shares": 0,
            "marketplace": "Grailed",
            "price": price_str,
            "condition": raw.get("condition", "Non précisé"),
            "size": raw.get("size", "N/A"),
            "brand_detected": brand,
            "link": listing_url,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        print(f"[parse_listing] Erreur sur une annonce : {e}")
        return None


def scrape_brand(brand: str):
    print(f"→ Récupération des annonces : {brand}")
    try:
        html = fetch_search_page(brand)
    except requests.RequestException as e:
        print(f"  ✗ Erreur réseau pour {brand} : {e}")
        return []
    data = extract_next_data(html)
    if not data:
        print(f"  ⚠️ Structure inattendue pour {brand} (site probablement modifié).")
        return []
    try:
        raw_listings = data.get("props", {}).get("pageProps", {}).get("listings", [])
    except AttributeError:
        raw_listings = []
    parsed = [parse_listing(item, brand) for item in raw_listings]
    return [p for p in parsed if p]


def load_existing():
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def run_scrape():
    existing = load_existing()
    existing_items = {item["id"]: item for item in existing.get("items", [])}
    all_new = []
    for brand in BRANDS:
        all_new.extend(scrape_brand(brand))
        time.sleep(2)
    for item in all_new:
        existing_items[item["id"]] = item
    merged = sorted(existing_items.values(), key=lambda x: x.get("scraped_at", ""), reverse=True)
    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "count": len(merged),
        "items": merged[:200]
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"✓ Scraping terminé : {len(all_new)} annonces traitées, {output['count']} au total")
    return output


def get_fresh_listings():
    if OUTPUT_FILE.exists():
        age = time.time() - OUTPUT_FILE.stat().st_mtime
        if age < REFRESH_EVERY_SECONDS:
            return json.loads(OUTPUT_FILE.read_text())
    return run_scrape()


# ---------------- API ----------------

@app.route("/api/listings")
def get_listings():
    data = get_fresh_listings()
    return jsonify(data)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
