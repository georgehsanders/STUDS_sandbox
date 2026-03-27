#!/usr/bin/env python3
"""
Scrape product images from studs.com (Shopify) and match to internal SKUs.
"""

import csv
import os
import sys
import time
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests

BASE_URL = "https://studs.com/products.json"
SKU_MASTER = "/Users/georgesanders/Documents/Code/STUDS/database/master/SKU_Master.csv"
IMAGE_DIR = "/Users/georgesanders/Documents/Code/STUDS/database/images/"
TEST_SKUS = ["CI002G", "CI002S", "FC012G", "FI002GT", "HP004G", "HP010G",
             "PS134KOP", "PS154KCL", "PS170KCL", "PS177SGR"]


def fetch_all_products():
    """Paginate through all pages of products.json."""
    all_products = []
    page = 1
    while True:
        url = f"{BASE_URL}?limit=250&page={page}"
        print(f"Fetching page {page}...")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        products = data.get("products", [])
        if not products:
            break
        all_products.extend(products)
        print(f"  Got {len(products)} products (total: {len(all_products)})")
        page += 1
        time.sleep(0.5)
    return all_products


def clean_image_url(src):
    """Convert //studs.com/cdn/... to https:// and strip ?v= query param."""
    if not src:
        return None
    if src.startswith("//"):
        src = "https:" + src
    # Strip query params
    if "?" in src:
        src = src.split("?")[0]
    return src


def build_sku_lookup(products):
    """Build dict: uppercase SKU -> {title, image_url, image_filename}."""
    lookup = {}
    for product in products:
        product_title = product.get("title", "")
        # Fallback image from product level
        fallback_url = None
        product_images = product.get("images", [])
        if product_images:
            fallback_url = clean_image_url(product_images[0].get("src"))

        for variant in product.get("variants", []):
            sku = (variant.get("sku") or "").strip().upper()
            if not sku:
                continue

            # Get image URL: prefer variant featured_image, fall back to product image
            img_url = None
            featured = variant.get("featured_image")
            if featured and featured.get("src"):
                img_url = clean_image_url(featured["src"])
            else:
                img_url = fallback_url

            if img_url:
                # Extract filename from URL path
                parsed = urlparse(img_url)
                filename = os.path.basename(parsed.path)
            else:
                filename = None

            lookup[sku] = {
                "title": product_title,
                "image_url": img_url,
                "image_filename": filename,
            }
    return lookup


def load_master_skus():
    """Load SKUs from master CSV."""
    skus = []
    with open(SKU_MASTER, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row["SKU"].strip().upper()
            if sku:
                skus.append(sku)
    return skus


def download_image(url, filepath):
    """Download an image with basic retry on 429."""
    for attempt in range(2):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 429:
                print("  Rate limited, waiting 2s...")
                time.sleep(2)
                continue
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return True
        except requests.RequestException as e:
            if attempt == 0 and "429" in str(e):
                time.sleep(2)
                continue
            print(f"  ERROR downloading: {e}")
            return False
    return False


def main():
    os.makedirs(IMAGE_DIR, exist_ok=True)

    # Step 1: Fetch all products
    print("=" * 60)
    print("FETCHING ALL PRODUCTS FROM STUDS.COM")
    print("=" * 60)
    products = fetch_all_products()
    print(f"\nTotal products fetched: {len(products)}")

    # Step 2: Build lookup
    lookup = build_sku_lookup(products)
    print(f"Total unique SKUs found on studs.com: {len(lookup)}")

    # Step 3: Load master SKUs
    master_skus = load_master_skus()
    print(f"Total SKUs in master file: {len(master_skus)}")

    # Step 4: Phase 1 — Verification
    print("\n" + "=" * 60)
    print("PHASE 1 — VERIFICATION PASS")
    print("=" * 60)
    print(f"{'SKU':<15} {'STATUS':<12} {'TITLE':<40} IMAGE URL")
    print("-" * 120)

    for sku in TEST_SKUS:
        entry = lookup.get(sku)
        if entry and entry["image_url"]:
            print(f"{sku:<15} {'MATCH':<12} {entry['title'][:40]:<40} {entry['image_url']}")
        elif entry:
            print(f"{sku:<15} {'NO IMAGE':<12} {entry['title'][:40]:<40} —")
        else:
            print(f"{sku:<15} {'NOT FOUND':<12} {'—':<40} —")

    print("\n=== PHASE 1 COMPLETE — verify matches above before proceeding ===\n")
    if "--auto" not in sys.argv:
        answer = input("Proceed with full download? (yes/no): ").strip().lower()
        if answer not in ("yes", "y"):
            print("Aborted.")
            return

    # Step 5: Phase 2 — Full download
    print("\n" + "=" * 60)
    print("PHASE 2 — DOWNLOADING IMAGES")
    print("=" * 60)

    # Build set of existing image prefixes (case-insensitive)
    existing_files = os.listdir(IMAGE_DIR)
    existing_prefixes = set()
    for fname in existing_files:
        # Extract SKU prefix (everything before the first underscore)
        prefix = fname.split("_")[0].upper()
        existing_prefixes.add(prefix)

    downloaded = 0
    skipped = 0
    not_found = 0
    errors = 0
    matched = 0

    for sku in master_skus:
        entry = lookup.get(sku)
        if not entry or not entry["image_url"]:
            not_found += 1
            continue

        matched += 1

        # Check if already exists
        if sku.upper() in existing_prefixes:
            print(f"Skipped (exists): {sku}")
            skipped += 1
            continue

        # Build filename
        orig_filename = entry["image_filename"]
        if orig_filename.upper().startswith(sku):
            save_filename = orig_filename
        else:
            save_filename = f"{sku}_{orig_filename}"

        filepath = os.path.join(IMAGE_DIR, save_filename)

        if download_image(entry["image_url"], filepath):
            print(f"Downloaded: {save_filename}")
            downloaded += 1
            # Add to existing prefixes so dupes in master list don't re-download
            existing_prefixes.add(sku.upper())
        else:
            errors += 1

        time.sleep(0.3)

    # Step 6: Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total SKUs in master file:    {len(master_skus)}")
    print(f"Total matched on studs.com:   {matched}")
    print(f"Total downloaded:             {downloaded}")
    print(f"Total skipped (already exist):{skipped}")
    print(f"Total download errors:        {errors}")
    print(f"Total not found on studs.com: {not_found}")


if __name__ == "__main__":
    main()
