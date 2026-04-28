"""
audit_cleanup.py — Brightpearl audit trail CSV processing for STUDS HQ.

All processing logic lives here.  app.py routes call process_file() and
generate_csv(); nothing else in the codebase imports this module.
"""

import csv
import io
import re

# ── Canonical Type of Movement values ─────────────────────────────────────────
# Edit this list to add or remove valid movement types.  The order here is the
# order shown in the review-modal dropdown.
CANONICAL_TYPES = [
    "Stock Check",
    "Stock Update",
    "Damaged - Contamination",
    "Damaged - Defective/Incompatible Pin",
    "Damaged - Quality Issue (Color/Size/Shape)",
    "Damaged - Bent/Broken",
    "Overselling",
    "Purchase",
    "Damaged - VM Tool/Display",
    "Damaged - Missing/Loose Stone",
    "TO Error",
    "Reallocated Inv – Damaged",   # en-dash (–)
    "Piercing Room Saline",
    "Lost & Found",
    "System Error - Return",
    "Damaged - Burnt",
    "De-Kit",
    "Damaged - Saline",
    "Theft",
    "Kit",
]

_CANONICAL_SET = set(CANONICAL_TYPES)

# ── Quality-related damage codes ───────────────────────────────────────────────
# Quality-related damage codes that describe what's wrong with the product
# itself, as opposed to environmental causes like contamination.  Used to break
# ties in combo defaults — when a combo pairs Contamination with a
# quality-related code, the quality-related code wins because it's more
# actionable for reporting.
QUALITY_RELATED_CODES = [
    "Damaged - Defective/Incompatible Pin",
    "Damaged - Bent/Broken",
    "Damaged - Quality Issue (Color/Size/Shape)",
    "Damaged - Missing/Loose Stone",
    "Damaged - Burnt",
]

# ── Keyword map for custom-reason suggestions ──────────────────────────────────
# Used to suggest a canonical Type of Movement when a studio enters a free-text
# reason instead of selecting from the canonical list.
#
# Each entry: (must_all_match, [substrings], canonical_suggestion)
#   must_all_match=True  → ALL substrings must appear (AND logic)
#   must_all_match=False → ANY substring is sufficient (OR logic)
#
# Ordered most-specific first — first match wins.  Edit freely as new custom
# phrasings appear in production data.
KEYWORD_MAP = [
    (True,  ["lost", "found"],
             "Lost & Found"),
    (False, ["piercing room", "piercing saline"],
             "Piercing Room Saline"),
    (False, ["missing stone", "loose stone"],
             "Damaged - Missing/Loose Stone"),
    (False, ["incompatible pin", "defective pin", "bent pin"],
             "Damaged - Defective/Incompatible Pin"),
    (False, ["quality issue", "wrong color", "wrong size", "wrong shape", "discolor"],
             "Damaged - Quality Issue (Color/Size/Shape)"),
    (False, ["vm tool", "visual merch", "display damage"],
             "Damaged - VM Tool/Display"),
    (False, ["system error"],
             "System Error - Return"),
    (False, ["to error", "transfer error"],
             "TO Error"),
    (False, ["dekit", "de-kit", "de kit"],
             "De-Kit"),
    (False, ["reallocate"],
             "Reallocated Inv – Damaged"),
    (False, ["contam"],
             "Damaged - Contamination"),
    (False, ["bent", "broken", "snap", "crack"],
             "Damaged - Bent/Broken"),
    (False, ["burn"],
             "Damaged - Burnt"),
    (False, ["theft", "stolen", "stole"],
             "Theft"),
    (False, ["oversold", "overselling"],
             "Overselling"),
    (False, ["lost", "misplaced"],
             "Lost & Found"),
    (False, ["found"],
             "Lost & Found"),
    (False, ["stock update"],
             "Stock Update"),
    (False, ["recount", "stock check", "reconcile"],
             "Stock Check"),
    (False, ["saline"],
             "Damaged - Saline"),
    (False, ["purchase", "bought"],
             "Purchase"),
    (False, ["kit"],
             "Kit"),
]

# Warehouse names to exclude (case-insensitive exact match after strip).
_EXCLUDED_WAREHOUSES = {"whiplash ecom", "whiplash retail"}

# Mojibake replacements applied to every parsed Reason value before matching.
# Key: garbled sequence; Value: intended character.
_MOJIBAKE = {
    "‚Äì": "–",   # ‚Äì  →  – (en dash)
}


# ── Internal helpers ───────────────────────────────────────────────────────────

def _normalize(s):
    """Apply mojibake corrections and strip surrounding whitespace."""
    if s is None:
        return ""
    for bad, good in _MOJIBAKE.items():
        s = s.replace(bad, good)
    return s.strip()


def _parse_reference(ref):
    """
    Decide whether a row should survive filtering and extract metadata.

    Returns (keep, reason, username):
      keep     – bool
      reason   – str (normalized) or None when Reason: line is absent
      username – str (extracted) or 'Unknown'
    """
    if ref is None:
        return False, None, "Unknown"

    stripped = ref.strip()
    if not stripped:
        return False, None, "Unknown"

    upper = stripped.upper()
    if upper.startswith("SO#"):
        return False, None, "Unknown"
    if upper.startswith("PO#"):
        return False, None, "Unknown"
    if stripped.lower() == "stock alignment":
        return False, None, "Unknown"

    # Row survives — extract username
    username = "Unknown"
    m = re.search(r"User name:\s*(.+)", ref, re.IGNORECASE)
    if m:
        username = m.group(1).strip()

    # Extract reason
    r = re.search(r"Reason:\s*(.+)", ref, re.IGNORECASE)
    if not r:
        # Structured reference present but no Reason: line → flag for review
        return True, None, username

    reason = _normalize(r.group(1))
    return True, reason, username


def _classify_reason(reason):
    """
    Classify a normalized Reason value against the canonical list.

    Returns (movement_type, flag_type, flag_detail):
      movement_type – canonical str if auto-resolved, else None
      flag_type     – None | 'combo' | 'no_reason' | 'unknown'
      flag_detail   – dict with context used by the review modal
    """
    if reason is None:
        return None, "no_reason", {}

    if reason in _CANONICAL_SET:
        return reason, None, {}

    # Try every left-to-right split point; stop at the first valid (A, B) pair.
    # "Valid" = both halves are in the canonical set.
    best_a = best_b = None
    for i in range(1, len(reason)):
        a = reason[:i]
        b = reason[i:]
        if a in _CANONICAL_SET and b in _CANONICAL_SET:
            best_a, best_b = a, b
            break

    if best_a is not None:
        if best_a == best_b:
            # Self-duplicate (e.g. "TheftTheft") → auto-clean, no flag
            return best_a, None, {"auto_cleaned": True, "original": reason}
        else:
            # Two different known types → flag for two-button review
            return None, "combo", {
                "option_a": best_a,
                "option_b": best_b,
                "original": reason,
            }

    # Case 4.5: keyword pattern match → suggestion
    lower = reason.lower()
    for must_all_match, patterns, suggestion in KEYWORD_MAP:
        if must_all_match:
            if all(p in lower for p in patterns):
                return None, "suggestion", {"suggested": suggestion, "original": reason}
        else:
            if any(p in lower for p in patterns):
                return None, "suggestion", {"suggested": suggestion, "original": reason}

    # No match at all → flag for dropdown review
    return None, "unknown", {"original": reason}


# ── Public API ─────────────────────────────────────────────────────────────────

def process_file(file_bytes, original_filename):
    """
    Parse and filter a raw Brightpearl audit trail CSV.

    Returns a dict with keys:
      original_filename – str
      summary           – {total_input, filtered_out, auto_cleaned,
                           flagged_count, surviving}
      flagged           – list of row-summary dicts for the review modal
      rows              – list of full surviving row dicts (stored server-side)

    On parse failure returns {'error': str}.
    """
    try:
        text = file_bytes.decode("utf-8-sig", errors="replace")
    except Exception:
        text = file_bytes.decode("latin-1", errors="replace")

    reader = csv.reader(io.StringIO(text))

    try:
        _header = next(reader)
    except StopIteration:
        return {"error": "The uploaded file is empty."}

    # Column positions: A=0 … J=9  (spec columns)
    C_PRODUCT_ID  = 0
    C_SKU         = 1
    C_PRODUCT_NAME = 2
    C_OPTIONS     = 3
    C_QUANTITY    = 4
    C_PRICE       = 5
    C_REFERENCE   = 6
    C_WAREHOUSE   = 7
    C_DATE        = 8
    C_MOVEMENT_ID = 9

    surviving = []
    flagged   = []
    total_input      = 0
    filtered_out     = 0
    auto_cleaned_count = 0

    for raw in reader:
        total_input += 1

        # Ensure row has at least 10 columns
        while len(raw) < 10:
            raw.append("")

        # ── Warehouse filter ──────────────────────────────────────────────────
        warehouse = raw[C_WAREHOUSE].strip()
        if warehouse.lower() in _EXCLUDED_WAREHOUSES:
            filtered_out += 1
            continue

        # ── Reference filter + metadata extraction ────────────────────────────
        ref = raw[C_REFERENCE]
        keep, reason, username = _parse_reference(ref)
        if not keep:
            filtered_out += 1
            continue

        # ── Reason classification ─────────────────────────────────────────────
        row_index = len(surviving)
        movement_type, flag_type, flag_detail = _classify_reason(reason)
        is_flagged = flag_type is not None
        if flag_detail.get("auto_cleaned"):
            auto_cleaned_count += 1

        row = {
            "row_index":       row_index,
            "product_id":      raw[C_PRODUCT_ID],
            "sku":             raw[C_SKU],
            "product_name":    raw[C_PRODUCT_NAME],
            "options":         raw[C_OPTIONS],
            "quantity":        raw[C_QUANTITY],
            "price":           raw[C_PRICE],
            "reference":       ref,
            "warehouse":       warehouse,
            "date":            raw[C_DATE],
            "movement_id":     raw[C_MOVEMENT_ID],
            "type_of_movement": movement_type,
            "flagged":         is_flagged,
            "username":        username,
            "flag_type":       flag_type,
            "flag_detail":     flag_detail,
        }
        surviving.append(row)

        if is_flagged:
            flagged.append({
                "row_index":    row_index,
                "date":         raw[C_DATE],
                "sku":          raw[C_SKU],
                "product_name": raw[C_PRODUCT_NAME],
                "quantity":     raw[C_QUANTITY],
                "warehouse":    warehouse,
                "username":     username,
                "flag_type":    flag_type,
                "flag_detail":  flag_detail,
            })

    return {
        "original_filename": original_filename,
        "summary": {
            "total_input":   total_input,
            "filtered_out":  filtered_out,
            "auto_cleaned":  auto_cleaned_count,
            "flagged_count": len(flagged),
            "surviving":     len(surviving),
        },
        "flagged": flagged,
        "rows":    surviving,
    }


def generate_csv(rows, confirmed_types):
    """
    Produce the cleaned CSV as UTF-8-BOM bytes.

    rows            – list of surviving row dicts from process_file()
    confirmed_types – dict mapping row_index (str or int) → movement_type
                      for all rows that were flagged for user review
    """
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Product ID", "SKU", "Product Name", "Options",
        "Quantity", "Price", "Reference", "Warehouse",
        "Date", "Movement ID", "Type of Movement",
    ])

    for row in rows:
        if row.get("flagged"):
            idx = row["row_index"]
            movement_type = (
                confirmed_types.get(str(idx))
                or confirmed_types.get(idx)
            )
        else:
            movement_type = row.get("type_of_movement")

        if not movement_type:
            continue  # unresolved row — skip (should not happen after review)

        writer.writerow([
            row.get("product_id",   ""),
            row.get("sku",          ""),
            row.get("product_name", ""),
            row.get("options",      ""),
            row.get("quantity",     ""),
            row.get("price",        ""),
            row.get("reference",    ""),
            row.get("warehouse",    ""),
            row.get("date",         ""),
            row.get("movement_id",  ""),
            movement_type,
        ])

    return out.getvalue().encode("utf-8-sig")
