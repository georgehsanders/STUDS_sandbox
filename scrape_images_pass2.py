#!/usr/bin/env python3
"""
Pass 2: Deep scrape of studs.com for SKU images missed in pass 1.
Strategies: collections crawl, image filename matching, search endpoint, variant cross-match.
"""

import csv
import os
import sys
import time
import json
from urllib.parse import urlparse, quote

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests")
    import requests

SKU_MASTER = "/Users/georgesanders/Documents/Code/STUDS/database/master/SKU_Master.csv"
IMAGE_DIR = "/Users/georgesanders/Documents/Code/STUDS/database/images/"
BASE = "https://studs.com"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})


def safe_get(url, timeout=30, retries=2):
    """GET with retry on 429 and basic error handling."""
    for attempt in range(retries):
        try:
            resp = SESSION.get(url, timeout=timeout)
            if resp.status_code == 429:
                wait = 3 if attempt == 0 else 5
                print(f"  429 rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"  ERROR fetching {url}: {e}")
            return None
    return None


def clean_url(src):
    """Normalize image URL: ensure https://, strip query params."""
    if not src:
        return None
    if src.startswith("//"):
        src = "https:" + src
    if "?" in src:
        src = src.split("?")[0]
    return src


def filename_from_url(url):
    """Extract filename from URL path."""
    if not url:
        return None
    return os.path.basename(urlparse(url).path)


def load_master_skus():
    """Load all SKUs from master CSV."""
    skus = []
    with open(SKU_MASTER, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sku = row["SKU"].strip().upper()
            if sku:
                skus.append(sku)
    return skus


def get_existing_sku_prefixes():
    """Get set of SKU prefixes that already have images."""
    prefixes = set()
    for fname in os.listdir(IMAGE_DIR):
        prefix = fname.split("_")[0].upper()
        prefixes.add(prefix)
    return prefixes


def paginate_products_json(url_template):
    """Paginate a products.json endpoint, return list of products."""
    products = []
    page = 1
    while True:
        url = url_template.format(page=page)
        resp = safe_get(url)
        if not resp:
            break
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            break
        batch = data.get("products", [])
        if not batch:
            break
        products.extend(batch)
        page += 1
        time.sleep(0.3)
    return products


def extract_sku_image_mappings(products, sku_image_dict, missing_skus_set):
    """
    From a list of products, extract SKU->image mappings using multiple strategies:
    - Variant SKU + featured_image
    - Variant SKU + fallback to product first image
    - Image filename matching against missing SKUs
    - Cross-variant fallback (all variants get product image)
    """
    new_found = 0

    for product in products:
        title = product.get("title", "")
        product_images = product.get("images", [])
        fallback_url = None
        if product_images:
            fallback_url = clean_url(product_images[0].get("src"))

        # Strategy 4: Map ALL variant SKUs to product's first image as fallback
        for variant in product.get("variants", []):
            sku = (variant.get("sku") or "").strip().upper()
            if not sku or sku in sku_image_dict:
                continue

            # Prefer variant's featured_image
            img_url = None
            featured = variant.get("featured_image")
            if featured and featured.get("src"):
                img_url = clean_url(featured["src"])
            else:
                img_url = fallback_url

            if img_url and sku in missing_skus_set:
                sku_image_dict[sku] = {
                    "title": title,
                    "image_url": img_url,
                    "image_filename": filename_from_url(img_url),
                    "source": "variant_match",
                }
                new_found += 1

        # Strategy 2: Image filename matching
        # Check ALL product images against unmatched SKUs
        for img in product_images:
            src = clean_url(img.get("src"))
            if not src:
                continue
            fname = filename_from_url(src).upper()
            for sku in list(missing_skus_set):
                if sku in sku_image_dict:
                    continue
                if fname.startswith(sku):
                    sku_image_dict[sku] = {
                        "title": title,
                        "image_url": src,
                        "image_filename": filename_from_url(src),
                        "source": "filename_match",
                    }
                    new_found += 1

    return new_found


def strategy_1_collections(sku_image_dict, missing_skus_set):
    """Fetch all collections, then fetch products from each."""
    print("\n" + "=" * 60)
    print("STRATEGY 1 — COLLECTION CRAWL")
    print("=" * 60)

    # Get all collection handles
    resp = safe_get(f"{BASE}/collections.json")
    if not resp:
        print("  Could not fetch collections.json")
        return 0

    collections = resp.json().get("collections", [])
    print(f"  Found {len(collections)} collections")

    all_products = {}  # dedupe by product ID
    for i, coll in enumerate(collections):
        handle = coll.get("handle", "")
        if not handle:
            continue
        print(f"  [{i+1}/{len(collections)}] Crawling collection: {handle}")
        url_tmpl = f"{BASE}/collections/{handle}/products.json?limit=250&page={{page}}"
        products = paginate_products_json(url_tmpl)
        for p in products:
            pid = p.get("id")
            if pid and pid not in all_products:
                all_products[pid] = p
        time.sleep(0.2)

    print(f"  Total unique products from collections: {len(all_products)}")
    found = extract_sku_image_mappings(list(all_products.values()), sku_image_dict, missing_skus_set)
    print(f"  New SKU matches from collections: {found}")
    return found


def strategy_2_and_4_global(sku_image_dict, missing_skus_set):
    """Re-fetch global products.json with filename matching + cross-variant (strategies 2 & 4)."""
    print("\n" + "=" * 60)
    print("STRATEGY 2 & 4 — GLOBAL PRODUCTS FILENAME + CROSS-VARIANT")
    print("=" * 60)

    url_tmpl = f"{BASE}/products.json?limit=250&page={{page}}"
    products = paginate_products_json(url_tmpl)
    print(f"  Fetched {len(products)} products from global endpoint")
    found = extract_sku_image_mappings(products, sku_image_dict, missing_skus_set)
    print(f"  New SKU matches from filename/cross-variant: {found}")
    return found


def strategy_3_search(sku_image_dict, missing_skus_set):
    """Use search/suggest endpoint for remaining unmatched SKUs in target prefixes."""
    print("\n" + "=" * 60)
    print("STRATEGY 3 — SEARCH ENDPOINT")
    print("=" * 60)

    target_prefixes = ("ST", "KT", "PC", "PB", "FCB", "KP", "PL", "FL",
                       "VM", "DA", "CH", "CN", "CI", "HU", "PS", "FB",
                       "FC", "EPS", "KF", "FBK", "HP", "FA", "BD", "AC",
                       "KC", "LABRET", "PST", "FT", "KB")
    candidates = sorted([s for s in missing_skus_set if s not in sku_image_dict
                         and any(s.startswith(p) for p in target_prefixes)])

    print(f"  Searching for {len(candidates)} unmatched SKUs...")
    found = 0
    searched_handles = set()

    for i, sku in enumerate(candidates):
        if sku in sku_image_dict:
            continue

        if (i + 1) % 50 == 0:
            print(f"    Progress: {i+1}/{len(candidates)} searched, {found} new matches")

        url = f"{BASE}/search/suggest.json?q={quote(sku)}&resources[type]=product&resources[limit]=3"
        resp = safe_get(url, retries=1)
        time.sleep(0.2)
        if not resp:
            continue

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            continue

        resources = data.get("resources", {}).get("results", {}).get("products", [])
        for result in resources:
            handle = result.get("handle")
            if not handle or handle in searched_handles:
                continue
            searched_handles.add(handle)

            # Fetch full product data
            prod_resp = safe_get(f"{BASE}/products/{handle}.json")
            time.sleep(0.2)
            if not prod_resp:
                continue
            try:
                product = prod_resp.json().get("product")
            except (json.JSONDecodeError, ValueError):
                continue
            if not product:
                continue

            new = extract_sku_image_mappings([product], sku_image_dict, missing_skus_set)
            found += new

    print(f"  New SKU matches from search: {found}")
    return found


def download_images(sku_image_dict, master_skus, existing_prefixes):
    """Download images for newly matched SKUs."""
    print("\n" + "=" * 60)
    print("DOWNLOADING NEW IMAGES")
    print("=" * 60)

    downloaded = 0
    errors = 0
    skipped_existing = 0

    for sku in master_skus:
        if sku in existing_prefixes:
            skipped_existing += 1
            continue

        entry = sku_image_dict.get(sku)
        if not entry or not entry.get("image_url"):
            continue

        orig_filename = entry["image_filename"]
        if orig_filename.upper().startswith(sku):
            save_filename = orig_filename
        else:
            save_filename = f"{sku}_{orig_filename}"

        filepath = os.path.join(IMAGE_DIR, save_filename)

        # Download
        resp = safe_get(entry["image_url"])
        if resp and resp.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"  Downloaded: {save_filename}")
            downloaded += 1
            existing_prefixes.add(sku)
        else:
            print(f"  ERROR: Failed to download for {sku}")
            errors += 1

        time.sleep(0.3)

    return downloaded, errors, skipped_existing


def main():
    os.makedirs(IMAGE_DIR, exist_ok=True)

    master_skus = load_master_skus()
    existing_prefixes = get_existing_sku_prefixes()
    missing_skus_set = set(s for s in master_skus if s not in existing_prefixes)

    print(f"Total master SKUs: {len(master_skus)}")
    print(f"Already have images: {len(master_skus) - len(missing_skus_set)}")
    print(f"Missing images: {len(missing_skus_set)}")

    sku_image_dict = {}  # Combined dict across all strategies

    # Strategy 2 & 4 first (re-uses global products.json, fast)
    strategy_2_and_4_global(sku_image_dict, missing_skus_set)
    remaining = len([s for s in missing_skus_set if s not in sku_image_dict])
    print(f"  Still unmatched after strategies 2&4: {remaining}")

    # Strategy 1: Collections crawl
    strategy_1_collections(sku_image_dict, missing_skus_set)
    remaining = len([s for s in missing_skus_set if s not in sku_image_dict])
    print(f"  Still unmatched after collections: {remaining}")

    # Strategy 3: Search endpoint for remaining
    strategy_3_search(sku_image_dict, missing_skus_set)
    remaining = len([s for s in missing_skus_set if s not in sku_image_dict])
    print(f"  Still unmatched after search: {remaining}")

    # Total new matches found
    total_new_matches = len(sku_image_dict)
    print(f"\n{'=' * 60}")
    print(f"TOTAL NEW MATCHES FOUND: {total_new_matches}")
    print(f"{'=' * 60}")

    # Download
    downloaded, errors, skipped = download_images(
        sku_image_dict, master_skus, existing_prefixes
    )

    # Final summary
    final_existing = get_existing_sku_prefixes()
    still_missing = [s for s in master_skus if s not in final_existing]

    print(f"\n{'=' * 60}")
    print("FINAL SUMMARY — PASS 2")
    print(f"{'=' * 60}")
    print(f"Total SKUs in master file:       {len(master_skus)}")
    print(f"Had images before pass 2:        {len(master_skus) - len(missing_skus_set)}")
    print(f"New matches found this pass:     {total_new_matches}")
    print(f"Downloaded successfully:         {downloaded}")
    print(f"Download errors:                 {errors}")
    print(f"Skipped (already had image):     {skipped}")
    print(f"Total with images now:           {len(master_skus) - len(still_missing)}")
    print(f"Still missing images:            {len(still_missing)}")

    # Breakdown of still missing by prefix
    if still_missing:
        from collections import Counter
        prefix_counts = Counter()
        for s in still_missing:
            p = ""
            for c in s:
                if c.isalpha():
                    p += c
                else:
                    break
            prefix_counts[p] += 1

        print(f"\nStill missing by prefix:")
        for p, count in prefix_counts.most_common(40):
            print(f"  {p}: {count}")

    # Also list some sample missing SKUs for debugging
    if still_missing:
        print(f"\nSample missing SKUs (first 20):")
        for s in sorted(still_missing)[:20]:
            print(f"  {s}")


if __name__ == "__main__":
    main()
