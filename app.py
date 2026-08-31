#!/usr/bin/env python3
"""
app.py — DiorArchives Feed backend (v2, via grailed_api)
-----------------------------------------------------------
La v1 essayait de lire le HTML brut des pages Grailed, mais leurs annonces
se chargent en JavaScript après coup (page vide au départ, "Loading the Feed").
Cette version utilise la bibliothèque `grailed_api`, qui interroge directement
le moteur de recherche interne (Algolia) que le site web utilise lui-même pour
afficher les résultats — c'est la même donnée, récupérée de façon fiable.

Dépendances : requirements.txt fourni à côté.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, jsonify
from flask_cors import CORS
from grailed_api import GrailedAPIClient

app = Flask(__name__)
CORS(app)
client = GrailedAPIClient()

BRANDS = [
    {"designer": "Dior", "query": "Hedi Slimane"},
    {"designer": "Balmain", "query": ""},
    {"designer": "Saint Laurent Paris", "query": ""},
]
OUTPUT_FILE = Path(__file__).parent / "listings.json"
REFRESH_EVERY_SECONDS = 600  # 10 minutes


# ---------------- Récupération des données ----------------

def get_field(product: dict, *candidates, default=""):
    """Essaie plusieurs noms de champ possibles (la structure exacte
    renvoyée par Algolia n'est pas garantie identique à 100% dans le temps)."""
    for c in candidates:
        if c in product and product[c]:
            return product[c]
    return default


CONDITION_LABELS = {
    "is_new": "Neuf",
    "is_gently_used": "Peu porté",
    "is_used": "Occasion",
    "is_very_worn": "Très porté",
}


def parse_product(raw: dict, brand: str):
    try:
        title = get_field(raw, "title", "name")
        if not title:
            return None

        price = get_field(raw, "price", "buynow_price", default=0)
        price_str = f"€{price}" if price else "N/A"

        # La photo principale est dans cover_photo: {"url": "..."}
        cover = raw.get("cover_photo")
        image_url = ""
        if isinstance(cover, dict):
            image_url = cover.get("url", "")
        elif isinstance(cover, str):
            image_url = cover
        image_urls = [image_url] if image_url else []

        # Le vendeur est dans user: {"username": "...", ...}
        user = raw.get("user") or {}
        username = user.get("username", "vendeur_inconnu") if isinstance(user, dict) else "vendeur_inconnu"

        listing_id = get_field(raw, "id", "objectID", "listing_id", default="")
        slug = get_field(raw, "slug", "url", default="")
        if slug and not slug.startswith("http"):
            listing_url = f"https://www.grailed.com/listings/{listing_id}-{slug}" if listing_id else f"https://www.grailed.com/listings/{slug}"
        else:
            listing_url = slug or (f"https://www.grailed.com/listings/{listing_id}" if listing_id else "")

        raw_condition = get_field(raw, "condition", default="")
        condition = CONDITION_LABELS.get(raw_condition, raw_condition or "Non précisé")

        return {
            "id": str(listing_id) or title[:40],
            "image": image_urls[0] if image_urls else "",
            "images": image_urls,
            "username": username,
            "badge": f"Photo · {datetime.now().strftime('%-d-%-m')}",
            "title": title,
            "description": get_field(raw, "description", default="")[:140],
            "likes": get_field(raw, "favoriters_count", "hearted_count", "heat_f", default=0) or 0,
            "comments": 0,
            "shares": 0,
            "marketplace": "Grailed",
            "price": price_str,
            "condition": condition,
            "size": get_field(raw, "size", default="N/A"),
            "brand_detected": brand,
            "link": listing_url,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        print(f"[parse_product] Erreur sur une annonce : {e}")
        return None


def fetch_brand(brand_cfg: dict):
    designer = brand_cfg["designer"]
    query = brand_cfg.get("query", "")
    label = f"{designer} ({query})" if query else designer
    print(f"→ Récupération des annonces : {label}")
    try:
        products = client.find_products(
            sold=False,
            on_sale=True,
            designers=[designer],
            query_search=query,
            hits_per_page=40,
            verbose=False,
        )
    except Exception as e:
        print(f"  ✗ Erreur lors de l'appel à Grailed pour {label} : {e}")
        return []

    if not products:
        print(f"  ⚠️ Aucun résultat pour {label}.")
        return []

    print(f"  (exemple de champs reçus : {list(products[0].keys())})")

    parsed = [parse_product(p, designer) for p in products]
    parsed = [p for p in parsed if p]
    print(f"  ✓ {len(parsed)} annonces récupérées pour {label}")
    return parsed


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
        all_new.extend(fetch_brand(brand))
        time.sleep(1)

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
