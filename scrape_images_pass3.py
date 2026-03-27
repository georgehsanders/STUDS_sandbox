#!/usr/bin/env python3
"""
Pass 3 (v3): Fast CDN filename guessing + sibling matching.
Lean approach: few high-probability guesses, fast timeouts, no Google.
"""

import csv
import os
import re
import sys
import time
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests")
    import requests

SKU_MASTER = "/Users/georgesanders/Documents/Code/STUDS/database/master/SKU_Master.csv"
IMAGE_DIR = "/Users/georgesanders/Documents/Code/STUDS/database/images/"

CDN_BASES = [
    "https://cdn.shopify.com/s/files/1/0248/1166/7565/files/",
    "https://cdn.shopify.com/s/files/1/0248/1166/7565/products/",
]

SKIP_PREFIXES = {"SALINE", "FREEEARRING", "MYS", "MK", "FT", "PL", "LABRET"}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
})


def get_alpha_prefix(sku):
    p = ""
    for c in sku:
        if c.isalpha():
            p += c
        else:
            break
    return p


def check_url(url):
    """Fast HEAD check — 4s timeout."""
    try:
        resp = SESSION.head(url, timeout=4, allow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            if "image" in ct.lower():
                return url
    except:
        pass
    return None


def batch_check(urls, workers=8):
    """Check URLs concurrently, return first hit."""
    if not urls:
        return None
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(check_url, u): u for u in urls}
        for f in as_completed(futures):
            result = f.result()
            if result:
                # Cancel remaining
                for remaining in futures:
                    remaining.cancel()
                return result
    return None


def download_image(url, sku):
    """Download and save, return filename or None."""
    try:
        resp = SESSION.get(url, timeout=15)
        if resp.status_code != 200 or len(resp.content) < 100:
            return None
        c = resp.content
        if not (c[:2] == b'\xff\xd8' or c[:8] == b'\x89PNG\r\n\x1a\n'
                or (c[:4] == b'RIFF' and c[8:12] == b'WEBP')):
            return None
        fname = os.path.basename(urlparse(url).path).split('?')[0]
        if fname.upper().startswith(sku.upper()):
            save = fname
        else:
            save = f"{sku}_{fname}"
        path = os.path.join(IMAGE_DIR, save)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(c)
        return save
    except:
        return None


def build_sibling_urls(sku, existing_files):
    """Check if a color sibling has an image — try swapping the color code in the filename."""
    urls = []
    swaps = {
        'G': ['S'], 'S': ['G'], 'BK': ['G', 'S'], 'RG': ['G', 'S'],
        'GCL': ['SCL'], 'SCL': ['GCL'],
        'GGR': ['SGR', 'GCL'], 'SGR': ['GGR', 'SCL'],
        'GBK': ['SBK', 'GCL'], 'SBK': ['GBK', 'SCL'],
        'GT': ['ST'], 'ST': ['GT'],
        'GTPL': ['STPL'], 'STPL': ['GTPL'],
        'GOBK': ['GOCL'], 'GOCL': ['GOBK'],
    }

    for suffix, alts in swaps.items():
        if not sku.endswith(suffix):
            continue
        base = sku[:-len(suffix)]
        for alt in alts:
            sibling = base + alt
            # Find sibling in existing files
            for ef in existing_files:
                ef_sku = ef.split('_')[0].upper()
                if ef_sku == sibling:
                    # Build URL by replacing sibling SKU with our SKU in filename
                    for cdn_base in CDN_BASES:
                        new_fname = ef.replace(ef_sku, sku, 1)
                        urls.append(cdn_base + new_fname)
                        # Also try with original case
                        new_fname2 = ef.replace(ef_sku.lower(), sku, 1)
                        if new_fname2 != new_fname:
                            urls.append(cdn_base + new_fname2)
    return urls


def build_cdn_guesses(sku, desc):
    """Build a focused list of CDN URL guesses."""
    urls = []

    # Clean description into filename-friendly forms
    d = re.sub(r'\s*\([^)]*\)', '', desc).strip()
    camel = re.sub(r'[^a-zA-Z0-9]', '', d)
    under = re.sub(r'[^a-zA-Z0-9]+', '_', d).strip('_')
    hyphen = re.sub(r'[^a-zA-Z0-9]+', '-', d).strip('-')
    desc_variants = list(set([camel, under, hyphen]))

    seasons = ["Evergreen", "EVERGREEN", "FALL24", "HOLIDAY24", "Spring25",
               "Summer24", "SPR24", "PVL24", "PVL2022", "Spring2022",
               "PreFall2021", "SUM23", "Evergreen23", "March"]
    angles = ["SingleFront", "Single_Front_1", "SingleAngle", "Single_Angle_1",
              "Single-Front", "Single-Angle"]

    for base in CDN_BASES:
        # Simplest: just SKU.jpg / SKU.png
        urls.append(base + f"{sku}.jpg")
        urls.append(base + f"{sku}.png")

        for dv in desc_variants:
            # SKU_Desc.jpg
            urls.append(base + f"{sku}_{dv}.jpg")
            for season in seasons:
                # SKU_Desc_Season_Angle.jpg
                for angle in angles:
                    urls.append(base + f"{sku}_{dv}_{season}_{angle}.jpg")
                    urls.append(base + f"{sku}_{dv}_{season}_{angle}_1.jpg")

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def load_master_skus():
    rows = []
    with open(SKU_MASTER, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sku = row["SKU"].strip().upper()
            desc = row["DESCRIPTION"].strip()
            if sku:
                rows.append((sku, desc))
    return rows


def get_existing():
    files = os.listdir(IMAGE_DIR)
    prefixes = set(f.split("_")[0].upper() for f in files)
    return prefixes, files


def main():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    sys.stdout.reconfigure(line_buffering=True)  # Force line-buffered output

    all_skus = load_master_skus()
    existing_prefixes, existing_files = get_existing()

    missing = [(s, d) for s, d in all_skus
               if s not in existing_prefixes and get_alpha_prefix(s) not in SKIP_PREFIXES]

    print(f"Total master SKUs: {len(all_skus)}")
    print(f"Already have images: {len(all_skus) - len(missing)}")
    print(f"Missing (to attempt): {len(missing)}")
    print(flush=True)

    downloaded = 0
    not_found = 0

    for i, (sku, desc) in enumerate(missing):
        # Refresh existing files periodically for sibling matching
        if i % 50 == 0 and i > 0:
            existing_prefixes, existing_files = get_existing()

        print(f"[{i+1}/{len(missing)}] {sku} — {desc}", end="", flush=True)

        # Skip if image appeared (from sibling download or prior run)
        if sku in existing_prefixes:
            print(" (already covered)")
            continue

        # Phase 1: Sibling match (fastest, highest hit rate)
        sibling_urls = build_sibling_urls(sku, existing_files)
        if sibling_urls:
            hit = batch_check(sibling_urls[:20], workers=6)
            if hit:
                saved = download_image(hit, sku)
                if saved:
                    print(f" → sibling: {saved}", flush=True)
                    downloaded += 1
                    existing_prefixes.add(sku)
                    existing_files.append(saved)
                    continue

        # Phase 2: CDN guesses — do in batches of 20
        guesses = build_cdn_guesses(sku, desc)
        # Try simple ones first (just SKU.jpg), then full patterns
        for start in range(0, min(len(guesses), 100), 20):
            batch = guesses[start:start+20]
            hit = batch_check(batch, workers=8)
            if hit:
                saved = download_image(hit, sku)
                if saved:
                    print(f" → CDN: {saved}", flush=True)
                    downloaded += 1
                    existing_prefixes.add(sku)
                    existing_files.append(saved)
                    break
        else:
            print(" → not found", flush=True)
            not_found += 1

    # Summary
    final_prefixes, _ = get_existing()
    still_missing = [s for s, _ in all_skus if s not in final_prefixes]

    print(flush=True)
    print("=" * 60)
    print("FINAL SUMMARY — PASS 3")
    print("=" * 60)
    print(f"SKUs attempted:          {len(missing)}")
    print(f"Downloaded:              {downloaded}")
    print(f"Not found:               {not_found}")
    print(f"Total with images now:   {len(all_skus) - len(still_missing)}")
    print(f"Still missing:           {len(still_missing)}")

    if still_missing:
        from collections import Counter
        prefix_counts = Counter(get_alpha_prefix(s) for s in still_missing)
        print(f"\nStill missing by prefix:")
        for p, count in prefix_counts.most_common(30):
            print(f"  {p}: {count}")
    print(flush=True)


if __name__ == "__main__":
    main()
