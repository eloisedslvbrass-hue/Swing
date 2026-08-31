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

BRANDS = ["Dior", "Balmain", "Saint Laurent"]
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


def parse_product(raw: dict, brand: str):
    try:
        title = get_field(raw, "title", "name")
        if not title:
            return None

        price = get_field(raw, "price", "buynow_price", default=0)
        price_str = f"€{price}" if price else "N/A"

        photos = get_field(raw, "photos", "images", default=[])
        image_urls = []
        for p in photos:
            if isinstance(p, dict):
                image_urls.append(p.get("url") or p.get("large_url") or p.get("original_url", ""))
            elif isinstance(p, str):
                image_urls.append(p)
        image_urls = [u for u in image_urls if u]

        seller = raw.get("seller") or {}
        username = get_field(seller, "username", "id", default="vendeur_inconnu") if isinstance(seller, dict) else "vendeur_inconnu"

        listing_id = get_field(raw, "id", "objectID", "listing_id", default="")
        slug = get_field(raw, "slug", "url", default="")
        if slug and not slug.startswith("http"):
            listing_url = f"https://www.grailed.com/listings/{listing_id}-{slug}" if listing_id else f"https://www.grailed.com/listings/{slug}"
        else:
            listing_url = slug or (f"https://www.grailed.com/listings/{listing_id}" if listing_id else "")

        return {
            "id": str(listing_id) or title[:40],
            "image": image_urls[0] if image_urls else "",
            "images": image_urls,
            "username": username,
            "badge": f"Photo · {datetime.now().strftime('%-d-%-m')}",
            "title": title,
            "description": get_field(raw, "description", default="")[:140],
            "likes": get_field(raw, "favoriters_count", "hearted_count", default=0) or 0,
            "comments": 0,
            "shares": 0,
            "marketplace": "Grailed",
            "price": price_str,
            "condition": get_field(raw, "condition", default="Non précisé"),
            "size": get_field(raw, "size", default="N/A"),
            "brand_detected": brand,
            "link": listing_url,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        print(f"[parse_product] Erreur sur une annonce : {e}")
        return None


def fetch_brand(brand: str):
    print(f"→ Récupération des annonces : {brand}")
    try:
        products = client.find_products(
            sold=False,
            on_sale=True,
            designers=[brand],
            hits_per_page=40,
            verbose=False,
        )
    except Exception as e:
        print(f"  ✗ Erreur lors de l'appel à Grailed pour {brand} : {e}")
        return []

    if not products:
        print(f"  ⚠️ Aucun résultat pour {brand}.")
        return []

    # Debug : affiche la structure du tout premier résultat dans les logs,
    # pour pouvoir ajuster get_field() si des champs manquent.
    print(f"  (exemple de champs reçus : {list(products[0].keys())})")

    parsed = [parse_product(p, brand) for p in products]
    parsed = [p for p in parsed if p]
    print(f"  ✓ {len(parsed)} annonces récupérées pour {brand}")
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
