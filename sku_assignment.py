"""
sku_assignment.py — SKU Assignment Algorithm

Computes the weekly SKU list for stock check assignment.
Used by the /hq/sku-assignment/* routes in app.py.
"""

import csv
import json
import os
import sys
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Tunable constants — adjust here to change algorithm behavior
# ---------------------------------------------------------------------------
ASSIGNMENT_WEIGHT_SALES = 0.60         # share of score from sales rank
ASSIGNMENT_WEIGHT_TIME = 0.40          # share of score from time-since-last-count
ASSIGNMENT_TARGET_LIST_SIZE = 20       # how many SKUs picked per week
ASSIGNMENT_NEW_SKU_DELAY_WEEKS = 4     # weeks after first_seen before SKU enters rotation

# ---------------------------------------------------------------------------
# Path helpers — import from app to avoid duplication
# ---------------------------------------------------------------------------
# We lazy-import from app at call time to avoid circular imports at module load.

def _get_db():
    from app import get_db
    return get_db()

def _get_input_dir():
    from app import INPUT_DIR
    return INPUT_DIR

def _get_archive():
    from app import archive_file_if_exists
    return archive_file_if_exists

def _load_master_skus():
    from app import load_master_skus
    return load_master_skus()

def _load_sku_status():
    from app import load_sku_status
    return load_sku_status()

def _load_top_sellers():
    from app import load_top_sellers
    return load_top_sellers()

# ---------------------------------------------------------------------------
# sku_first_seen maintenance
# ---------------------------------------------------------------------------

def refresh_sku_first_seen():
    """
    Walk the current master SKU list and INSERT OR IGNORE any SKU not yet
    in sku_first_seen. Idempotent — safe to call repeatedly.
    Returns the number of new rows inserted.
    """
    master = _load_master_skus()
    if not master:
        return 0
    conn = _get_db()
    inserted = 0
    try:
        for sku in master:
            cursor = conn.execute(
                'INSERT OR IGNORE INTO sku_first_seen (sku) VALUES (?)', (sku.upper(),)
            )
            inserted += cursor.rowcount
        conn.commit()
    except Exception as e:
        print(f'[refresh_sku_first_seen] error: {e}', file=sys.stderr)
    finally:
        conn.close()
    return inserted

# ---------------------------------------------------------------------------
# Last-counted lookup
# ---------------------------------------------------------------------------

def get_last_counted_per_sku():
    """
    Returns {sku_upper: datetime_or_None} for every SKU in the master list.
    Queries stock_check_skus JOIN stock_checks to find MAX(completed_at) per SKU.
    SKUs never counted get None.
    """
    master = _load_master_skus()
    result = {sku.upper(): None for sku in master}
    conn = _get_db()
    try:
        rows = conn.execute(
            '''SELECT scs.sku, MAX(sc.completed_at) AS last_completed_at
               FROM stock_check_skus scs
               JOIN stock_checks sc ON scs.stock_check_id = sc.id
               WHERE sc.status = 'completed' AND sc.completed_at IS NOT NULL
               GROUP BY scs.sku'''
        ).fetchall()
        for row in rows:
            sku = row['sku'].upper() if row['sku'] else None
            if sku and row['last_completed_at']:
                try:
                    dt = datetime.fromisoformat(str(row['last_completed_at']))
                    result[sku] = dt
                except ValueError:
                    pass
    except Exception as e:
        print(f'[get_last_counted_per_sku] error: {e}', file=sys.stderr)
    finally:
        conn.close()
    return result

# ---------------------------------------------------------------------------
# First-seen lookup
# ---------------------------------------------------------------------------

def get_first_seen_per_sku():
    """Returns {sku_upper: datetime} for all rows in sku_first_seen."""
    result = {}
    conn = _get_db()
    try:
        rows = conn.execute('SELECT sku, first_seen_at FROM sku_first_seen').fetchall()
        for row in rows:
            try:
                dt = datetime.fromisoformat(str(row['first_seen_at']))
                result[row['sku'].upper()] = dt
            except (ValueError, TypeError):
                pass
    except Exception as e:
        print(f'[get_first_seen_per_sku] error: {e}', file=sys.stderr)
    finally:
        conn.close()
    return result

# ---------------------------------------------------------------------------
# Main algorithm
# ---------------------------------------------------------------------------

def generate_assignment(target_week_identifier, weight_overrides=None):
    """
    Compute the weekly SKU assignment.

    Args:
        target_week_identifier: string like "05-04-26"
        weight_overrides: optional dict with keys 'sales' and/or 'time'

    Returns a dict (see docstring below for shape).
    """
    w_sales = ASSIGNMENT_WEIGHT_SALES
    w_time = ASSIGNMENT_WEIGHT_TIME
    if weight_overrides:
        w_sales = weight_overrides.get('sales', w_sales)
        w_time = weight_overrides.get('time', w_time)

    today = date.today()

    # 1. Refresh first_seen so newly-added SKUs are tracked
    refresh_sku_first_seen()

    # 2-6. Load data
    master = _load_master_skus()           # {sku_upper: description}
    status_map = _load_sku_status()        # {sku_upper: 'active'|'sunset'}
    top_sellers = _load_top_sellers()      # list of dicts with rank, sku, ...
    last_counted = get_last_counted_per_sku()   # {sku_upper: datetime|None}
    first_seen = get_first_seen_per_sku()       # {sku_upper: datetime}

    # Build sales rank lookup {sku_upper: rank}
    rank_map = {}
    for entry in top_sellers:
        rank_map[entry['sku'].upper()] = entry['rank']
    n_top_sellers = len(top_sellers)
    top_sellers_missing = (n_top_sellers == 0)

    # Cutoff for new-SKU delay
    new_sku_cutoff = today - timedelta(days=ASSIGNMENT_NEW_SKU_DELAY_WEEKS * 7)

    # 7. Build eligible pool
    sunset_excluded = 0
    new_sku_delayed = 0
    eligible = []

    for sku_raw in master:
        sku = sku_raw.upper()
        sku_status = status_map.get(sku)

        # Skip sunset SKUs
        if sku_status == 'sunset':
            sunset_excluded += 1
            continue

        # Check first_seen date
        fs_dt = first_seen.get(sku)
        if fs_dt is None:
            # Shouldn't happen after refresh, but be safe
            fs_date = today
        else:
            fs_date = fs_dt.date()

        # Skip if added too recently (< ASSIGNMENT_NEW_SKU_DELAY_WEEKS ago)
        if fs_date > new_sku_cutoff:
            new_sku_delayed += 1
            continue

        eligible.append(sku)

    # 8. Score each eligible SKU
    scored = []
    for sku in eligible:
        description = master.get(sku, '')

        # a. sales_score
        if top_sellers_missing:
            sales_score = 0.0
            rank = None
        else:
            rank = rank_map.get(sku)
            if rank is not None:
                sales_score = (n_top_sellers + 1 - rank) / n_top_sellers
            else:
                sales_score = 0.0

        # b. time_score
        last_dt = last_counted.get(sku)
        fs_dt = first_seen.get(sku)
        if last_dt is not None:
            weeks_since = (today - last_dt.date()).days / 7.0
        elif fs_dt is not None:
            weeks_since = (today - fs_dt.date()).days / 7.0
        else:
            weeks_since = 12.0  # treat as maximally stale

        weeks_since_capped = min(weeks_since, 12.0)
        time_score = weeks_since_capped / 12.0

        # c. composite
        composite_score = (sales_score * w_sales) + (time_score * w_time)

        # Reasoning string
        weeks_since_rounded = round(weeks_since, 1)
        weeks_int = int(weeks_since_rounded) if weeks_since_rounded == int(weeks_since_rounded) else weeks_since_rounded

        # First-seen age for "new SKU" prefix
        fs_date_obj = fs_dt.date() if fs_dt else today
        sku_age_weeks = round((today - fs_date_obj).days / 7.0)

        if top_sellers_missing:
            if last_dt is None:
                reasoning = "Top sellers file missing — never counted in current system"
            else:
                reasoning = f"Top sellers file missing — last counted {weeks_int} week{'s' if weeks_int != 1 else ''} ago"
        else:
            if rank is not None and last_dt is not None and weeks_since_rounded > 0.5:
                reasoning = f"Top seller (rank {rank}) + last counted {weeks_int} week{'s' if weeks_int != 1 else ''} ago"
            elif rank is not None and (last_dt is None or weeks_since_rounded <= 0.5):
                reasoning = f"Top seller (rank {rank}), counted this week"
            elif rank is None and last_dt is not None:
                reasoning = f"Not in top sellers, last counted {weeks_int} week{'s' if weeks_int != 1 else ''} ago"
            else:
                reasoning = "Not in top sellers, never counted in current system"

        # Prepend new-SKU note if SKU is relatively new (within 2x the delay)
        if sku_age_weeks <= ASSIGNMENT_NEW_SKU_DELAY_WEEKS * 2:
            reasoning = f"New SKU (added {sku_age_weeks} week{'s' if sku_age_weeks != 1 else ''} ago) — {reasoning}"

        scored.append({
            'sku': sku,
            'description': description,
            'rank': rank,
            'sales_score': round(sales_score, 4),
            'time_score': round(time_score, 4),
            'composite_score': round(composite_score, 4),
            'weeks_since_counted': round(weeks_since, 2),
            'reasoning': reasoning,
        })

    # 9. Sort: composite_score desc, then sales_score desc, then sku asc
    scored.sort(key=lambda x: (-x['composite_score'], -x['sales_score'], x['sku']))

    # 10. Take top N
    selected = scored[:ASSIGNMENT_TARGET_LIST_SIZE]

    return {
        'target_week_identifier': target_week_identifier,
        'weights': {'sales': w_sales, 'time': w_time},
        'target_list_size': ASSIGNMENT_TARGET_LIST_SIZE,
        'new_sku_delay_weeks': ASSIGNMENT_NEW_SKU_DELAY_WEEKS,
        'selected': selected,
        'stats': {
            'eligible_pool_size': len(eligible),
            'sunset_excluded': sunset_excluded,
            'new_sku_delayed': new_sku_delayed,
            'total_master_skus': len(master),
        },
    }

# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def record_assignment_run(result, triggered_by_username=None, published=False,
                           published_at=None, published_filename=None):
    """
    Insert a row into sku_assignment_runs. Returns the new row id.
    """
    conn = _get_db()
    try:
        selected_skus = [s['sku'] for s in result['selected']]
        cursor = conn.execute(
            '''INSERT INTO sku_assignment_runs
               (triggered_by_username, target_week_identifier,
                selected_skus_json, selected_skus_count,
                published, published_at, published_filename,
                weight_sales, weight_time,
                new_sku_delay_weeks, target_list_size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                triggered_by_username,
                result['target_week_identifier'],
                json.dumps(selected_skus),
                len(selected_skus),
                1 if published else 0,
                published_at.isoformat() if published_at else None,
                published_filename,
                result['weights']['sales'],
                result['weights']['time'],
                result['new_sku_delay_weeks'],
                result['target_list_size'],
            )
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f'[record_assignment_run] error: {e}', file=sys.stderr)
        return None
    finally:
        conn.close()


def mark_run_published(run_id, published_filename):
    """Update a run row to mark it as published."""
    conn = _get_db()
    try:
        conn.execute(
            '''UPDATE sku_assignment_runs
               SET published = 1, published_at = CURRENT_TIMESTAMP, published_filename = ?
               WHERE id = ?''',
            (published_filename, run_id)
        )
        conn.commit()
    except Exception as e:
        print(f'[mark_run_published] error: {e}', file=sys.stderr)
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# SKUList file writer
# ---------------------------------------------------------------------------

def write_skulist_file(target_week_identifier, selected):
    """
    Write the SKU list to /input/SKUList_MM-DD-YY.csv.
    Archives any existing file at that path first.
    Returns the full filepath written.

    selected: list of dicts with 'sku' and 'description' keys (from generate_assignment output)
    """
    input_dir = _get_input_dir()
    archive_fn = _get_archive()
    filename = f'SKUList_{target_week_identifier}.csv'
    filepath = os.path.join(input_dir, filename)

    # Archive existing file if present
    archive_fn(filepath, 'sku_list', None)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['SKU ', 'Product Name'])  # trailing space matches reconcile.py expectation
        for item in selected:
            writer.writerow([item['sku'], item['description']])

    return filepath

# ---------------------------------------------------------------------------
# Next-Monday helper
# ---------------------------------------------------------------------------

def next_monday_week_identifier():
    """
    Returns the next Monday's date as MM-DD-YY string.
    If today is Monday, returns today + 7 days (next Monday, not today).
    """
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # today is Monday — use next Monday
    target = today + timedelta(days=days_until_monday)
    return target.strftime('%m-%d-%y')
