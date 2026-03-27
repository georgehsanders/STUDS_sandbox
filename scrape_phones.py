#!/usr/bin/env python3
"""
Scrape phone numbers for all STUDS store locations from studs.com/pages/studio-directory
and update store_profiles.db.
"""

import re
import sqlite3
import sys

try:
    import requests
except ImportError:
    import os; os.system(f"{sys.executable} -m pip install requests")
    import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    import os; os.system(f"{sys.executable} -m pip install beautifulsoup4")
    from bs4 import BeautifulSoup

DB_PATH = "/Users/georgesanders/Documents/Code/STUDS/database/store_profiles.db"
DIRECTORY_URL = "https://studs.com/pages/studio-directory"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
})

# Manual mapping: scraped studio name -> DB store_id
# DB names: "001 NY SoHo", "002 NY Williamsburg", etc.
NAME_MAP = {
    "nolita": "001",             # was SoHo, now Nolita (12 Prince St)
    "hudson yards": "004",
    "upper east side": "003",
    "flatiron": "005",
    "rockefeller center": None,  # newer store, not in DB yet
    "meatpacking": None,         # newer store, not in DB yet
    "georgetown": "013",
    "union market": None,        # newer store
    "wynwood": None,             # was Aventura? check address
    "hyde park village": None,   # was International Plaza? check
    "ponce city market": None,   # was Lenox Square? check
    "gold coast": "023",         # was Michigan Ave
    "plaza del lago": "024",     # was Oakbrook
    "magazine street": None,     # newer store
    "back bay": "009",           # Newbury Street
    "seaport": None,             # newer store
    "harvard square": None,      # newer store
    "chestnut hill": "010",      # was Burlington
    "venetian shoppes": "030",   # was Fashion Show
    "abbot kinney": "036",       # was Santa Monica
    "century city": "032",
    "fashion island": "033",
    "irvine spectrum": None,     # newer store
    "valley fair": "034",        # was Stanford
    "westfield roseville": None, # newer store
    "westfield topanga": "031",  # was Beverly Center
    "westfield utc": "035",      # was UTC San Diego
    "domain northside": "021",   # was Domain
    "south congress": None,      # newer store
    "west village": "020",       # was NorthPark
    "lovers lane": None,         # newer store
    "rice village": None,        # newer store (not same as Galleria)
    "heights mercantile": None,  # newer store
    "houston galleria": "022",   # Galleria
    "tysons corner": None,       # newer store
    "capitol hill": "037",       # was Bellevue Square
    "state street": None,        # newer store
    "king street": None,         # newer store
    "fifth and broadway": None,  # newer store
}


def parse_studios_from_page():
    """Parse all studio entries from the studio directory page."""
    print("Fetching studio directory...")
    resp = SESSION.get(DIRECTORY_URL, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # The page has store entries with names, addresses, and phone numbers
    # Let's get all the text content and parse it structurally
    # Look for studio entries - each has a name, address, and optional phone
    studios = []

    # Get the main content area
    text = soup.get_text("\n", strip=True)

    # Phone pattern
    phone_re = re.compile(r'\(?\d{3}\)?[\s\xa0.-]+\d{3}[\s.-]+\d{4}')

    # Parse by finding phone numbers and working backwards to find the studio name
    # Better approach: find all <a> tags with tel: links and their surrounding context
    for a_tag in soup.find_all("a", href=True):
        if not a_tag["href"].startswith("tel:"):
            continue
        phone_raw = a_tag.get_text(strip=True)
        if not phone_raw:
            phone_raw = a_tag["href"].replace("tel:", "")

        digits = re.sub(r'\D', '', phone_raw)
        if len(digits) == 11 and digits[0] == '1':
            digits = digits[1:]
        if len(digits) != 10:
            continue

        phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

        # Walk up to find the studio name - look for parent container
        parent = a_tag.parent
        for _ in range(5):
            if parent is None:
                break
            parent_text = parent.get_text("\n", strip=True)
            if len(parent_text) > 50:
                break
            parent = parent.parent

        # The studio name is typically a bold/heading element before the address
        # Try to find it from the container text
        if parent:
            container_text = parent.get_text("\n", strip=True)
            lines = [l.strip() for l in container_text.split("\n") if l.strip()]
            # First non-empty line is usually the studio name
            name = lines[0] if lines else "Unknown"
            # Clean up - remove state grouping headers
            studios.append({"name": name, "phone": phone, "raw_lines": lines})

    # Also parse from text for studios without tel: links
    # Use regex on full text to find studio blocks
    return studios


def match_by_name_fuzzy(studio_name, db_stores):
    """Fuzzy match a studio name against DB store names."""
    name_lower = studio_name.lower().strip()

    # Check manual map first
    for key, store_id in NAME_MAP.items():
        if key in name_lower or name_lower in key:
            return store_id

    # Try matching against DB names
    best = None
    best_score = 0
    for store_id, db_name in db_stores:
        # Extract location from "001 NY SoHo" -> "soho"
        parts = db_name.split(" ", 2)
        location = parts[2].lower() if len(parts) >= 3 else db_name.lower()
        loc_words = set(re.findall(r'[a-z]+', location))
        name_words = set(re.findall(r'[a-z]+', name_lower))
        common = loc_words & name_words
        score = sum(len(w) for w in common)
        if score > best_score:
            best_score = score
            best = store_id

    return best if best_score >= 4 else None


def main():
    # Load DB stores
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT store_id, name FROM stores ORDER BY store_id")
    db_stores = cur.fetchall()
    print(f"Loaded {len(db_stores)} stores from database\n")

    # Parse studios from page
    studios = parse_studios_from_page()
    print(f"Found {len(studios)} studios with phone numbers\n")

    # Also do a simpler text-based parse as backup
    resp = SESSION.get(DIRECTORY_URL, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    full_text = soup.get_text(" ", strip=True)

    # Find all phone occurrences with preceding text
    phone_pattern = re.compile(r'([A-Z][A-Z\s&\']+?)(\d[\d\s()\-.\xa0]{9,15}\d)')
    all_phones = {}

    # Parse the structured text more carefully
    # The page text follows pattern: STATE HEADER, then STUDIO NAME, ADDRESS, PHONE
    lines = soup.get_text("\n", strip=True).split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # First pass: rejoin split phone numbers like "(424)\n252-5015"
    joined_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line is a partial phone like "(424)" and next line completes it
        if re.match(r'^\(\d{3}\)$', line.strip()) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r'^\d{3}[\s.-]?\d{4}$', next_line):
                joined_lines.append(f"{line} {next_line}")
                i += 2
                continue
        joined_lines.append(line)
        i += 1
    lines = joined_lines

    # Second pass: find studio name -> phone associations
    # Walk through lines: ALL CAPS lines that aren't addresses are studio names
    # The phone follows after the address
    current_studio = None
    state_headers = {"california", "district of columbia", "florida", "georgia",
                     "illinois", "louisiana", "massachusetts", "nevada", "new york",
                     "south carolina", "tennessee", "texas", "virginia", "washington",
                     "wisconsin"}

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Skip state headers
        if line_stripped.lower() in state_headers:
            continue

        # Detect studio names: ALL CAPS, not an address, not a phone
        if (line_stripped.isupper() and
            len(line_stripped) > 3 and
            not re.match(r'^\d', line_stripped) and
            not re.search(r'\d{3}', line_stripped) and
            not any(w in line_stripped.lower() for w in ['suite', 'blvd', 'street', 'ave', 'drive', 'road', 'unit'])):
            current_studio = line_stripped

        # Detect phone numbers
        digits = re.sub(r'\D', '', line_stripped)
        if len(digits) == 10 and re.search(r'\d{3}.*\d{3}.*\d{4}', line_stripped):
            phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            if current_studio:
                name_key = current_studio.lower().strip()
                if name_key not in all_phones:
                    all_phones[name_key] = phone

    print(f"Text-parsed {len(all_phones)} studio-phone pairs\n")

    # Match and update
    print(f"{'Studio Name':<30} {'Phone':<18} {'Matched DB Store':<35} {'Status'}")
    print("-" * 105)

    updated = 0
    no_match = 0

    for studio_name, phone in sorted(all_phones.items()):
        store_id = match_by_name_fuzzy(studio_name, db_stores)
        if store_id:
            db_name = next(n for sid, n in db_stores if sid == store_id)
            cur.execute("UPDATE stores SET phone = ? WHERE store_id = ?", (phone, store_id))
            print(f"{studio_name:<30} {phone:<18} {db_name:<35} UPDATED")
            updated += 1
        else:
            print(f"{studio_name:<30} {phone:<18} {'—':<35} no DB match")
            no_match += 1

    conn.commit()
    conn.close()

    # Verify
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT store_id, name, phone FROM stores WHERE phone != '' ORDER BY store_id")
    print(f"\n{'='*70}")
    print("DATABASE VERIFICATION — Stores with phone numbers:")
    print(f"{'='*70}")
    rows = cur.fetchall()
    for sid, name, phone in rows:
        print(f"  {sid} | {name:<35} | {phone}")
    print(f"\n  {len(rows)} of 40 stores now have phone numbers")

    cur.execute("SELECT store_id, name FROM stores WHERE phone = '' ORDER BY store_id")
    empty = cur.fetchall()
    if empty:
        print(f"\n  Stores still without phone numbers:")
        for sid, name in empty:
            print(f"    {sid} | {name}")
    conn.close()

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Studios found on website:  {len(all_phones)}")
    print(f"Matched & updated in DB:   {updated}")
    print(f"No DB match (new stores):  {no_match}")


if __name__ == "__main__":
    main()
