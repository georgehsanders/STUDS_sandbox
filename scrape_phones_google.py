#!/usr/bin/env python3
"""
Update store_profiles.db with phone numbers found via Google search.
Many of the 22 missing stores have closed or relocated — only update
stores where a verified phone number was found.
"""

import sqlite3
import re

DB_PATH = "/Users/georgesanders/Documents/Code/STUDS/database/store_profiles.db"

# Phone numbers found via web search, verified against Yelp/Yellow Pages/studs.com
# Format: store_id -> (phone, source, notes)
FOUND_PHONES = {
    # CONFIRMED FOUND
    "002": ("(646) 760-6675", "ShowMeLocal/Cylex", "CLOSED — 324 Wythe Ave, Brooklyn. Phone from directory listings."),
    "034": ("(408) 335-4776", "Yelp/studs.com", "Valley Fair, Santa Clara. Correct phone from Yelp listing."),

    # STORES NOT FOUND ON GOOGLE — likely closed/relocated with no trace:
    # "006": Garden State Plaza — no STUDS listing found at this mall
    # "007": Short Hills — no STUDS listing found
    # "008": CT Westfield — no STUDS listing found in CT
    # "011": King of Prussia — no STUDS listing found
    # "012": Rittenhouse — no STUDS listing found
    # "014": Aventura — no STUDS listing found (nearest is Wynwood)
    # "015": Dadeland — no STUDS listing found (nearest is Wynwood)
    # "016": Sawgrass — no STUDS listing found
    # "017": International Plaza — no STUDS listing, replaced by Hyde Park Village
    # "018": Lenox Square — no STUDS listing, replaced by Ponce City Market
    # "019": Avalon — no STUDS listing found
    # "024": Oakbrook — no STUDS listing at Oakbrook (Plaza del Lago is new, no phone yet)
    # "025": Mall of America — STUDS announced for summer 2026, not yet open
    # "026": Cherry Creek — no STUDS listing found
    # "027": Park Meadows — no STUDS listing found
    # "028": Scottsdale Fashion — mall directory doesn't list STUDS
    # "029": Biltmore — no STUDS listing found
    # "038": University Village — no STUDS listing (nearest is Capitol Hill)
    # "039": Pioneer Place — no STUDS listing found in Portland
    # "040": Ala Moana — no STUDS listing found in Hawaii
}


def normalize_phone(phone):
    """Normalize to (XXX) XXX-XXXX format."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Show current state
    cur.execute("SELECT store_id, name, phone FROM stores WHERE phone IS NULL OR phone = '' ORDER BY store_id")
    missing = cur.fetchall()
    print(f"Stores currently missing phone numbers: {len(missing)}")
    for sid, name, phone in missing:
        print(f"  {sid} | {name}")

    print(f"\nPhone numbers found via Google search: {len(FOUND_PHONES)}")
    print()

    # Update found phones
    updated = 0
    for store_id, (phone_raw, source, notes) in FOUND_PHONES.items():
        phone = normalize_phone(phone_raw)
        if not phone:
            print(f"  SKIP {store_id}: invalid phone '{phone_raw}'")
            continue

        cur.execute("SELECT name FROM stores WHERE store_id = ?", (store_id,))
        row = cur.fetchone()
        if not row:
            print(f"  SKIP {store_id}: not found in database")
            continue

        cur.execute("UPDATE stores SET phone = ? WHERE store_id = ?", (phone, store_id))
        print(f"  UPDATED {store_id} | {row[0]:<35} | {phone} | {source}")
        if notes:
            print(f"           Note: {notes}")
        updated += 1

    conn.commit()

    # Final verification
    print(f"\n{'='*70}")
    print("FINAL DATABASE STATE")
    print(f"{'='*70}")

    cur.execute("SELECT store_id, name, phone FROM stores ORDER BY store_id")
    all_stores = cur.fetchall()
    has_phone = 0
    no_phone = 0
    for sid, name, phone in all_stores:
        status = phone if phone else "— no phone —"
        print(f"  {sid} | {name:<35} | {status}")
        if phone:
            has_phone += 1
        else:
            no_phone += 1

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total stores:              {len(all_stores)}")
    print(f"With phone numbers:        {has_phone}")
    print(f"Still missing:             {no_phone}")
    print(f"Updated this pass:         {updated}")
    print(f"\nStores still missing phones are confirmed closed/relocated")
    print(f"with no active STUDS listing found via Google search.")

    conn.close()


if __name__ == "__main__":
    main()
