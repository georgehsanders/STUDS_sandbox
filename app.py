import os
import re
import csv
import io
import json
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone, date
from functools import wraps
import bcrypt
import pytz
from flask import (Flask, render_template, jsonify, request, redirect,
                   url_for, session, send_file, send_from_directory, flash)
import analytics_begin_count
from reconcile import (
    INPUT_DIR, STATUS_UPDATED, STATUS_DISCREPANCY, STATUS_INCOMPLETE,
    STATUS_INCOMPLETE_FORMAT, RE_SKU_LIST, RE_VARIANCE, RE_AUDIT_TRAIL,
    VARIANCE_COLUMNS, RE_RS_PREFIX, is_excluded_sku, clean_csv_content,
    parse_csv, classify_upload_filename, scan_input_files, load_sku_list,
    load_variance, parse_warehouse_id, load_audit_trail,
    build_store_name_map, get_audit_date_range, reconcile_store,
    run_reconciliation,
)
import reconcile

app = Flask(__name__)

# --- Authentication ---
ADMIN_USERNAME = 'hq'
ADMIN_PASSWORD = 'hq'
app.secret_key = 'studs-secret-key-change-in-production'

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.environ.get('STUDS_DATA_DIR', '').strip()

PROCESSED_DIR = os.path.join(_DATA_DIR, 'processed') if _DATA_DIR else os.path.join(_REPO_ROOT, 'processed')
SETTINGS_FILE = os.path.join(_REPO_ROOT, 'settings.json')
DATABASE_DIR = os.path.join(_DATA_DIR, 'database') if _DATA_DIR else os.path.join(_REPO_ROOT, 'database')
MASTER_DIR = os.path.join(DATABASE_DIR, 'master')
IMAGES_DIR = os.path.join(DATABASE_DIR, 'images')
STORE_DB = os.path.join(DATABASE_DIR, 'store_profiles.db')
ARCHIVE_DB = os.path.join(DATABASE_DIR, 'archive.db')

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(MASTER_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# --- Feature flags ---
# Flip SHOW_START_STOCK_CHECK to True to restore the "Start Your Stock Check"
# button on the studio homepage. The flow itself (/studio/stock-check/*) is
# unaffected by this flag — only the homepage button is hidden when False.
SHOW_START_STOCK_CHECK = False

# --- Default email template ---
DEFAULT_EMAIL_BODY = (
    "We recently completed an inventory audit and found discrepancies in the following SKUs "
    "at your location. Please review and reconcile these items at your earliest convenience.\n\n"
    "{{sku_table}}\n\n"
    "Please confirm once these have been addressed.\n\n"
    "Thank you,\nInventory Management Team"
)


# --- Store profiles database ---

SEED_STORES = [
    ("001", "001 NY Nolita", "America/New_York"),
    ("002", "002 NY Hudson Yards", "America/New_York"),
    ("006", "006 CA Century City", "America/New_York"),
    ("007", "007 NY Upper East Side", "America/New_York"),
    ("008", "008 TX Domain Northside", "America/New_York"),
    ("009", "009 FL Wynwood", "America/New_York"),
    ("010", "010 MA Back Bay", "America/New_York"),
    ("011", "011 MA The Street, Chestnut Hill", "America/New_York"),
    ("012", "012 TN Fifth and Broadway", "America/New_York"),
    ("014", "014 WA Capitol Hill", "America/New_York"),
    ("015", "015 SC King Street", "America/New_York"),
    ("016", "016 TX Rice Village", "America/New_York"),
    ("017", "017 WI State Street", "America/New_York"),
    ("018", "018 LA Magazine Street", "America/New_York"),
    ("019", "019 TX West Village", "America/New_York"),
    ("020", "020 DC Georgetown", "America/New_York"),
    ("021", "021 IL Gold Coast", "America/New_York"),
    ("022", "022 MA Seaport", "America/New_York"),
    ("023", "023 NY Flatiron", "America/New_York"),
    ("024", "024 NY Rockefeller Center", "America/New_York"),
    ("025", "025 GA Ponce", "America/New_York"),
    ("026", "026 NY Meatpacking", "America/New_York"),
    ("027", "027 TX South Congress", "America/New_York"),
    ("028", "028 CA UTC San Diego", "America/New_York"),
    ("029", "029 MA Harvard Square", "America/New_York"),
    ("030", "030 DC Union Market", "America/New_York"),
    ("031", "031 CA Westfield Topanga", "America/New_York"),
    ("032", "032 CA Irvine Spectrum", "America/New_York"),
    ("033", "033 CA Fashion Island", "America/New_York"),
    ("034", "034 TX Lovers Lane", "America/New_York"),
    ("035", "035 FL Hyde Park Village", "America/New_York"),
    ("036", "036 CA Abbot Kinney", "America/New_York"),
    ("037", "037 TX Heights Mercantile", "America/New_York"),
    ("038", "038 CA Valley Fair", "America/New_York"),
    ("039", "039 VA Tysons Corner", "America/New_York"),
    ("040", "040 TX Houston Galleria", "America/New_York"),
    ("041", "041 NV Grand Canal Shoppes", "America/New_York"),
    ("042", "042 CA Roseville", "America/New_York"),
    ("043", "043 IL Plaza Del Lago", "America/New_York"),
    ("044", "044 HI Ala Moana", "America/New_York"),
    ("045", "045 MN Mall of America", "America/New_York"),
]

# Real studio data with region — used for the one-time data migration.
# SEED_STORES above does not carry region because the DB schema migration adds that
# column first; region is populated separately by migrate_to_real_studios().
REAL_STUDIOS = [
    ("001", "001 NY Nolita",                      "NY & East Coast Metro"),
    ("002", "002 NY Hudson Yards",                "NY & East Coast Metro"),
    ("006", "006 CA Century City",                "North Pacific"),
    ("007", "007 NY Upper East Side",             "NY & East Coast Metro"),
    ("008", "008 TX Domain Northside",            "South Central"),
    ("009", "009 FL Wynwood",                     "Southeast"),
    ("010", "010 MA Back Bay",                    "Northeast & Central"),
    ("011", "011 MA The Street, Chestnut Hill",   "Northeast & Central"),
    ("012", "012 TN Fifth and Broadway",          "Southeast"),
    ("014", "014 WA Capitol Hill",                "North Pacific"),
    ("015", "015 SC King Street",                 "Southeast"),
    ("016", "016 TX Rice Village",                "South Central"),
    ("017", "017 WI State Street",                "Northeast & Central"),
    ("018", "018 LA Magazine Street",             "Southeast"),
    ("019", "019 TX West Village",                "South Central"),
    ("020", "020 DC Georgetown",                  "Northeast & Central"),
    ("021", "021 IL Gold Coast",                  "Northeast & Central"),
    ("022", "022 MA Seaport",                     "Northeast & Central"),
    ("023", "023 NY Flatiron",                    "NY & East Coast Metro"),
    ("024", "024 NY Rockefeller Center",          "NY & East Coast Metro"),
    ("025", "025 GA Ponce",                       "Southeast"),
    ("026", "026 NY Meatpacking",                 "NY & East Coast Metro"),
    ("027", "027 TX South Congress",              "South Central"),
    ("028", "028 CA UTC San Diego",               "North Pacific"),
    ("029", "029 MA Harvard Square",              "Northeast & Central"),
    ("030", "030 DC Union Market",                "Northeast & Central"),
    ("031", "031 CA Westfield Topanga",           "North Pacific"),
    ("032", "032 CA Irvine Spectrum",             "North Pacific"),
    ("033", "033 CA Fashion Island",              "North Pacific"),
    ("034", "034 TX Lovers Lane",                 "South Central"),
    ("035", "035 FL Hyde Park Village",           "Southeast"),
    ("036", "036 CA Abbot Kinney",                "North Pacific"),
    ("037", "037 TX Heights Mercantile",          "South Central"),
    ("038", "038 CA Valley Fair",                 "North Pacific"),
    ("039", "039 VA Tysons Corner",               "Northeast & Central"),
    ("040", "040 TX Houston Galleria",            "South Central"),
    ("041", "041 NV Grand Canal Shoppes",         "North Pacific"),
    ("042", "042 CA Roseville",                   "North Pacific"),
    ("043", "043 IL Plaza Del Lago",              "Northeast & Central"),
    ("044", "044 HI Ala Moana",                   "North Pacific"),
    ("045", "045 MN Mall of America",             "Northeast & Central"),
]

VALID_REGIONS = {
    'NY & East Coast Metro',
    'North Pacific',
    'Southeast',
    'South Central',
    'Northeast & Central',
}


def get_db():
    """Get a SQLite connection to the store profiles database."""
    conn = sqlite3.connect(STORE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_to_real_studios(conn):
    """One-time migration: replace old dummy studio data with the real studio list.

    Detects dummy data by checking for the known old name '001 NY SoHo'.
    Idempotent: if the real data is already in place (or the DB was freshly seeded
    from the updated SEED_STORES), the function returns immediately.

    Must be called AFTER the schema migration that adds the 'region' column.
    """
    has_dummy = conn.execute(
        "SELECT 1 FROM stores WHERE name = '001 NY SoHo'"
    ).fetchone()
    if not has_dummy:
        return
    conn.execute('DELETE FROM stores')
    for store_id, name, region in REAL_STUDIOS:
        pw_hash = bcrypt.hashpw(store_id.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn.execute(
            "INSERT INTO stores (store_id, name, timezone, username, password_hash, region) "
            "VALUES (?, ?, 'America/New_York', ?, ?, ?)",
            (store_id, name, store_id, pw_hash, region),
        )


def init_store_db():
    """Create and seed the store profiles database if it doesn't exist."""
    need_seed = not os.path.exists(STORE_DB)
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(STORE_DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS stores (
        store_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        timezone TEXT NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    if need_seed:
        for store_id, name, tz in SEED_STORES:
            pw_hash = bcrypt.hashpw(store_id.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn.execute(
                'INSERT OR IGNORE INTO stores (store_id, name, timezone, username, password_hash) VALUES (?, ?, ?, ?, ?)',
                (store_id, name, tz, store_id, pw_hash)
            )
    # Add columns if missing (schema migrations — run before data migration)
    existing = [row[1] for row in conn.execute('PRAGMA table_info(stores)').fetchall()]
    if 'manager' not in existing:
        conn.execute("ALTER TABLE stores ADD COLUMN manager TEXT DEFAULT ''")
    if 'phone' not in existing:
        conn.execute("ALTER TABLE stores ADD COLUMN phone TEXT DEFAULT ''")
    if 'region' not in existing:
        conn.execute("ALTER TABLE stores ADD COLUMN region TEXT DEFAULT ''")
    # Create hq_users table
    conn.execute('''CREATE TABLE IF NOT EXISTS hq_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        email TEXT DEFAULT '',
        is_admin INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Seed Jasmine's account if not present
    if not conn.execute("SELECT 1 FROM hq_users WHERE username = 'jasmine.vu'").fetchone():
        pw_hash = bcrypt.hashpw('lilbamboo'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn.execute(
            "INSERT INTO hq_users (username, password_hash, display_name, email) VALUES (?, ?, ?, ?)",
            ('jasmine.vu', pw_hash, 'Jasmine Vu', 'jasmine.vu@studs.com')
        )
    # Analytics tables — Begin Count stock check history
    conn.execute('''CREATE TABLE IF NOT EXISTS stock_checks (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id            TEXT    NOT NULL,
        counter_name        TEXT    NOT NULL DEFAULT '',
        skulist_filename    TEXT,
        week_identifier     TEXT,
        started_at          TIMESTAMP NOT NULL,
        completed_at        TIMESTAMP,
        duration_seconds    INTEGER,
        status              TEXT    NOT NULL DEFAULT 'in_progress',
        furthest_step       INTEGER NOT NULL DEFAULT 1,
        assigned_sku_count  INTEGER,
        total_variances     INTEGER,
        variances_reconciled INTEGER,
        variances_still_off INTEGER,
        bp_filename         TEXT,
        oc_filename         TEXT,
        bp_verify_filename  TEXT,
        created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS stock_check_skus (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_check_id  INTEGER NOT NULL,
        sku             TEXT    NOT NULL,
        on_hand         INTEGER,
        counted         INTEGER,
        new_on_hand     INTEGER,
        final_counted   INTEGER,
        matched         INTEGER,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    # Data migration: replace dummy studios with real list (idempotent)
    migrate_to_real_studios(conn)
    conn.commit()
    conn.close()


def get_hq_user(username):
    """Look up an HQ user by username. Returns a dict or None."""
    conn = get_db()
    row = conn.execute('SELECT * FROM hq_users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_store_by_username(username):
    """Look up a store by username. Returns a dict or None."""
    conn = get_db()
    row = conn.execute('SELECT * FROM stores WHERE username = ?', (username,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_all_stores_db():
    """Return all stores from the database as a list of dicts."""
    conn = get_db()
    rows = conn.execute('SELECT * FROM stores ORDER BY store_id').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_store_by_id_db(store_id):
    """Look up a store by store_id. Returns a dict or None."""
    conn = get_db()
    row = conn.execute('SELECT * FROM stores WHERE store_id = ?', (store_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def check_password(stored_hash, password):
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))


def is_studio_locked(timezone_str):
    """Check if the Studio portal is locked for the given timezone.
    Locked Friday (4) through Sunday (6). Returns True if locked."""
    settings = load_settings()
    if not settings.get('feature_studio_lockout', True):
        return False
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        return False
    now = datetime.now(tz)
    return now.weekday() >= 4  # 4=Friday, 5=Saturday, 6=Sunday


# --- Archive database ---

def get_archive_db():
    """Get a SQLite connection to the archive database."""
    conn = sqlite3.connect(ARCHIVE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_archive_db():
    """Create the archive database and tables if they don't exist."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(ARCHIVE_DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS archive_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_type TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        store_id TEXT,
        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_date TEXT,
        row_count INTEGER,
        file_size_bytes INTEGER,
        content TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS image_flags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_filename TEXT NOT NULL UNIQUE,
        flag_type TEXT NOT NULL,
        sku TEXT,
        status TEXT DEFAULT 'unresolved',
        resolved_at TIMESTAMP,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


def archive_file_if_exists(filepath, file_type, store_id=None):
    """Archive a file before it gets overwritten. Returns True if archived."""
    if not os.path.isfile(filepath):
        return False
    with open(filepath, 'r', errors='replace') as f:
        content = f.read()
    file_size = os.path.getsize(filepath)
    row_count = max(0, content.count('\n') - 1)  # subtract header row
    filename = os.path.basename(filepath)
    conn = get_archive_db()
    conn.execute(
        'INSERT INTO archive_files (file_type, original_filename, store_id, file_size_bytes, row_count, content) VALUES (?, ?, ?, ?, ?, ?)',
        (file_type, filename, store_id, file_size, row_count, content)
    )
    conn.commit()
    conn.close()
    return True



def load_master_skus():
    """Load SKU_Master.csv and return a dict of SKU (uppercase) -> DESCRIPTION."""
    filepath = os.path.join(MASTER_DIR, 'SKU_Master.csv')
    if not os.path.isfile(filepath):
        return {}
    rows = parse_csv(filepath)
    result = {}
    for row in rows:
        sku = row.get('sku', '').strip().upper()
        desc = row.get('description', '').strip()
        if sku:
            result[sku] = desc
    return result


def load_sku_status():
    """Load SKU_Status.csv and return a dict of SKU (uppercase) -> status (lowercase)."""
    filepath = os.path.join(MASTER_DIR, 'SKU_Status.csv')
    if not os.path.isfile(filepath):
        return {}
    rows = parse_csv(filepath)
    result = {}
    for row in rows:
        sku = row.get('sku', '').strip().upper()
        status = row.get('status', '').strip().lower()
        if sku and status in ('active', 'sunset'):
            result[sku] = status
    return result


def load_sku_prices():
    """Load SKU_Prices.csv and return a dict of SKU (uppercase) -> retail_price (float)."""
    filepath = os.path.join(DATABASE_DIR, 'SKU_Prices.csv')
    if not os.path.isfile(filepath):
        return {}
    rows = parse_csv(filepath)
    result = {}
    for row in rows:
        sku = row.get('sku', '').strip().upper()
        price_str = row.get('retail_price', '').strip()
        if not sku or not price_str:
            continue
        try:
            result[sku] = float(price_str)
        except ValueError:
            continue
    return result


def find_image_for_sku(sku):
    """Find an image file in IMAGES_DIR whose name starts with the SKU (case-insensitive)."""
    if not os.path.isdir(IMAGES_DIR):
        return None
    sku_lower = sku.lower()
    for fname in os.listdir(IMAGES_DIR):
        if fname.lower().startswith(sku_lower):
            return fname
    return None


def run_image_sku_audit():
    """Audit image/SKU matches. Returns {orphaned: N, missing: N}."""
    master = load_master_skus()
    master_skus = set(master.keys())  # uppercase

    # Scan images
    image_files = []
    if os.path.isdir(IMAGES_DIR):
        image_files = [f for f in os.listdir(IMAGES_DIR) if os.path.isfile(os.path.join(IMAGES_DIR, f))]

    # Build matched sets
    matched_images = set()
    matched_skus = set()
    for img in image_files:
        img_lower = img.lower()
        for sku in master_skus:
            if img_lower.startswith(sku.lower()):
                matched_images.add(img)
                matched_skus.add(sku)
                break

    orphaned_images = [img for img in image_files if img not in matched_images]
    missing_skus = [sku for sku in master_skus if sku not in matched_skus]

    conn = get_archive_db()

    # Clear flags that are now resolved
    conn.execute("DELETE FROM image_flags WHERE flag_type = 'orphaned_image' AND status = 'unresolved' AND image_filename NOT IN ({})".format(
        ','.join('?' * len(orphaned_images)) if orphaned_images else "'__none__'"
    ), orphaned_images if orphaned_images else [])

    conn.execute("DELETE FROM image_flags WHERE flag_type = 'missing_image' AND status = 'unresolved' AND image_filename NOT IN ({})".format(
        ','.join('?' * len(missing_skus)) if missing_skus else "'__none__'"
    ), missing_skus if missing_skus else [])

    # Insert new orphaned image flags
    for img in orphaned_images:
        conn.execute(
            "INSERT OR IGNORE INTO image_flags (image_filename, flag_type) VALUES (?, 'orphaned_image')",
            (img,)
        )

    # Insert new missing image flags (use SKU as image_filename for uniqueness)
    for sku in missing_skus:
        conn.execute(
            "INSERT OR IGNORE INTO image_flags (image_filename, flag_type, sku) VALUES (?, 'missing_image', ?)",
            (sku, sku)
        )

    conn.commit()
    conn.close()
    return {'orphaned': len(orphaned_images), 'missing': len(missing_skus)}


def studio_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('studio_logged_in'):
            return redirect(url_for('studio_login'))
        return f(*args, **kwargs)
    return decorated


def hq_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('hq_logged_in'):
            return redirect(url_for('hq_login'))
        return f(*args, **kwargs)
    return decorated


def load_settings():
    """Load settings from JSON file."""
    defaults = {
        'email_body_template': DEFAULT_EMAIL_BODY,
        'store_emails': {},
        'feature_studio_lockout': True,
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                saved = json.load(f)
            defaults.update(saved)
        except (json.JSONDecodeError, IOError):
            pass
    return defaults


def save_settings(settings):
    """Save settings to JSON file."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)



# --- Inject DB dependency into reconcile module ---
reconcile.get_all_stores_db = get_all_stores_db


# Functions moved to reconcile.py:
# scan_input_files, load_sku_list, load_variance, parse_warehouse_id,
# load_audit_trail, build_store_name_map, get_audit_date_range,
# reconcile_store, run_reconciliation, classify_upload_filename,
# clean_csv_content, parse_csv, is_excluded_sku


# --- Flask routes ---

# --- Landing page (unauthenticated) ---

@app.route('/')
def landing():
    return render_template('landing.html')


# --- Studio portal ---

@app.route('/studio/login', methods=['GET', 'POST'])
def studio_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        # Check admin credentials first (bypass lockout)
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['studio_logged_in'] = True
            session['is_admin'] = True
            return redirect(url_for('studio_index'))
        # Look up store
        store = get_store_by_username(username)
        if not store or not check_password(store['password_hash'], password):
            flash('Incorrect username or password.', 'error')
        elif is_studio_locked(store['timezone']):
            flash('Sorry, stud! The new SKU list will be available Monday.', 'lockout')
        else:
            session['studio_logged_in'] = True
            session['store_id'] = store['store_id']
            session['is_admin'] = False
            return redirect(url_for('studio_index'))
    return render_template('studio_login.html')


@app.route('/studio/logout')
def studio_logout():
    session.pop('studio_logged_in', None)
    return redirect(url_for('landing'))


@app.route('/studio/goto-hq')
@studio_login_required
def studio_goto_hq():
    session['hq_logged_in'] = True
    session['is_admin'] = True
    return redirect(url_for('hq_index'))


@app.route('/database/images/<filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


@app.route('/studio/')
@studio_login_required
def studio_index():
    scan = scan_input_files()
    sku_list_filename = None
    no_sku_list = True
    sku_items = []

    if scan['sku_lists']:
        no_sku_list = False
        sku_list_filename = scan['sku_lists'][0][0]
        filepath = os.path.join(INPUT_DIR, sku_list_filename)

        # Parse SKU list with product names
        sku_rows = parse_csv(filepath)
        sku_names = {}
        sku_set = set()
        for row in sku_rows:
            sku = row.get('sku', '').strip()
            name = row.get('product name', '').strip()
            if sku and not is_excluded_sku(sku):
                sku_set.add(sku)
                sku_names[sku] = name

        master = load_master_skus()
        sku_status = load_sku_status()
        sku_prices = load_sku_prices()

        for sku in sorted(sku_set):
            desc = master.get(sku.upper(), '') or sku_names.get(sku, '') or sku
            image_filename = find_image_for_sku(sku)
            status = sku_status.get(sku.upper())
            price = sku_prices.get(sku.upper())
            sku_items.append({
                'sku': sku,
                'description': desc,
                'image_filename': image_filename,
                'status': status,
                'retail_price': price,
            })

    # Welcome message: neighborhood from store name, week from today's date
    store = get_store_by_id_db(session.get('store_id', ''))
    welcome_neighborhood = parse_neighborhood(store['name']) if store else ''
    welcome_week_number = date.today().isocalendar()[1]

    return render_template('studio.html',
                           sku_items=sku_items,
                           sku_list_filename=sku_list_filename,
                           no_sku_list=no_sku_list,
                           show_start_stock_check=SHOW_START_STOCK_CHECK,
                           welcome_neighborhood=welcome_neighborhood,
                           welcome_week_number=welcome_week_number)


def format_duration(seconds):
    """Format elapsed seconds as a compact human-readable string.
    <1m / 25m / 1h 23m"""
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return '<1m'
    if seconds < 3600:
        return '{}m'.format(int(seconds // 60))
    return '{}h {}m'.format(int(seconds // 3600), int((seconds % 3600) // 60))


def _resume_duration(sess):
    """Compute duration string from begin_count_started_at in session, or '—'."""
    started_at = sess.get('begin_count_started_at')
    if not started_at:
        return '\u2014'
    try:
        start = datetime.fromisoformat(started_at)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return format_duration(elapsed)
    except Exception:
        return '\u2014'


# ---------------------------------------------------------------------------
# Begin Count analytics — week identifier helper
# ---------------------------------------------------------------------------

# Local copy of the SKU list filename pattern. Defined here rather than imported
# from reconcile.py to keep the analytics layer decoupled from the reconciliation
# pipeline. Must stay in sync with RE_SKU_LIST in reconcile.py.
_RE_SKULIST_WEEK = re.compile(
    r'^SKU[_ ]?[Ll]ist[-_](\d{2}[-_]\d{2}[-_]\d{2})\.csv$', re.IGNORECASE
)


def parse_week_identifier(skulist_filename):
    """Extract the MM-DD-YY date string from a SKU list filename.

    Normalizes separators to dashes so the stored value is always MM-DD-YY.
    Returns None if the filename doesn't match the expected pattern.

    Examples:
      'SKU_List-04_21_26.csv' -> '04-21-26'
      'SKU List-04-21-26.csv' -> '04-21-26'
      'SKUList_04-14-26.csv'  -> '04-14-26'
      'random.csv'            -> None
    """
    if not skulist_filename:
        return None
    m = _RE_SKULIST_WEEK.match(skulist_filename)
    if not m:
        return None
    return m.group(1).replace('_', '-')


def iso_week_from_mmddyy(mmddyy):
    """Convert a MM-DD-YY date string (from parse_week_identifier) to an ISO
    week number (int).  Returns None if the input is malformed.

    Example: '04-14-26' -> 16
    """
    if not mmddyy:
        return None
    try:
        dt = datetime.strptime(mmddyy, '%m-%d-%y')
        return dt.isocalendar()[1]
    except (ValueError, TypeError):
        return None


def parse_neighborhood(store_name):
    """Strip the store number and 2-letter state code from a store name.

    '001 NY Nolita'                    -> 'Nolita'
    '002 NY Hudson Yards'              -> 'Hudson Yards'
    '011 MA The Street, Chestnut Hill' -> 'The Street, Chestnut Hill'

    Fallback: returns the full name if it doesn't match the expected
    '<number> <2-letter-state> <rest>' pattern.
    """
    if not store_name:
        return ''
    tokens = store_name.split()
    if len(tokens) < 3:
        return store_name
    if len(tokens[1]) != 2 or not tokens[1].isalpha():
        return store_name
    return ' '.join(tokens[2:])


# Department mapping for Step 4 per-department variance columns
DEPARTMENT_KEYS = ['accessory', 'bins_backstock', 'dcr_piercing', 'visual_display']
DEPARTMENT_LABELS = ['Accessory', 'Bins & Backstock', 'DCR/Piercing Room', 'Visual Display']

# Ordered from most-specific to most-general so prefix checks don't shadow each other.
_DEPARTMENT_MAPPING = [
    ('fashion inv',           'bins_backstock'),  # "Fashion Inv - Bins & Backstock"
    ('piercing inv - bins',   'bins_backstock'),  # "Piercing Inv - Bins & Backstock"
    ('piercing inv - dcr',    'dcr_piercing'),    # "Piercing Inv - DCR &Piercing Rooms"
    ('accessory inv',         'accessory'),       # all "Accessory Inv - *" rows
    ('visual display',        'visual_display'),  # "Visual Display Inv - Barcode Sheets"
]


def map_department_desc(dept_desc):
    """Maps a raw "Department Desc" value from the OmniCounts Count Report
    to one of four abbreviated column keys:
      - "accessory"
      - "bins_backstock"
      - "dcr_piercing"
      - "visual_display"
    Returns None if no mapping matches (caller should skip and log these rows).

    Matching is case-insensitive and tolerates extra whitespace.  A substring
    match is used so minor label variations (extra punctuation, spacing) are
    handled gracefully.

    Known mappings:
      Accessory Inv - Insertion Tools     -> accessory
      Accessory Inv - Jewelry Boxes       -> accessory
      Accessory Inv - Piercing Pillows    -> accessory
      Accessory Inv - Saline              -> accessory
      Fashion Inv - Bins & Backstock      -> bins_backstock
      Piercing Inv - Bins & Backstock     -> bins_backstock
      Piercing Inv - DCR &Piercing Rooms  -> dcr_piercing
      Visual Display Inv - Barcode Sheets -> visual_display
    """
    if not dept_desc:
        return None
    normalized = ' '.join(dept_desc.strip().lower().split())
    for pattern, key in _DEPARTMENT_MAPPING:
        if pattern in normalized:
            return key
    return None


# ---------------------------------------------------------------------------
# Begin Count analytics — write-hook helpers
#
# Every helper wraps its DB operations in try/except.  On failure the error is
# printed to stderr and a sentinel (None / False) is returned.  Callers must
# never propagate analytics failures to the user-facing JSON response.
# ---------------------------------------------------------------------------

def create_stock_check_row(store_id, counter_name, started_at):
    """Insert a new stock_checks row.  Returns the new row id, or None on failure."""
    try:
        conn = get_db()
        try:
            started_str = (
                started_at.isoformat()
                if hasattr(started_at, 'isoformat')
                else str(started_at)
            )
            cur = conn.execute(
                "INSERT INTO stock_checks "
                "(store_id, counter_name, started_at, status, furthest_step) "
                "VALUES (?, ?, ?, 'in_progress', 1)",
                (store_id, counter_name or '', started_str),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] create_stock_check_row failed: {exc}', file=sys.stderr)
        return None


def update_stock_check_row(run_id, **fields):
    """UPDATE stock_checks row id=run_id with the supplied keyword fields.
    Also sets updated_at = CURRENT_TIMESTAMP.
    Returns True on success, False on failure.  No-op if run_id is None."""
    if run_id is None or not fields:
        return False
    try:
        conn = get_db()
        try:
            set_clause = ', '.join(f'{k} = ?' for k in fields)
            values = list(fields.values()) + [run_id]
            conn.execute(
                f'UPDATE stock_checks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                values,
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] update_stock_check_row failed: {exc}', file=sys.stderr)
        return False


def bump_furthest_step(run_id, new_step):
    """UPDATE furthest_step = MAX(furthest_step, new_step) for the given run.
    Returns True on success, False on failure.  No-op if run_id is None."""
    if run_id is None:
        return False
    try:
        conn = get_db()
        try:
            conn.execute(
                'UPDATE stock_checks '
                'SET furthest_step = MAX(furthest_step, ?), updated_at = CURRENT_TIMESTAMP '
                'WHERE id = ?',
                (new_step, run_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] bump_furthest_step failed: {exc}', file=sys.stderr)
        return False


def replace_stock_check_skus(run_id, sku_data):
    """Delete all stock_check_skus rows for run_id and re-insert from sku_data.

    sku_data is a list of dicts each containing at least: sku, on_hand, counted.
    Atomic: rolls back on any insertion error.
    Returns True on success, False on failure.  No-op if run_id is None.
    """
    if run_id is None:
        return False
    try:
        conn = get_db()
        try:
            conn.execute(
                'DELETE FROM stock_check_skus WHERE stock_check_id = ?', (run_id,)
            )
            for row in sku_data:
                conn.execute(
                    'INSERT INTO stock_check_skus (stock_check_id, sku, on_hand, counted) '
                    'VALUES (?, ?, ?, ?)',
                    (run_id, row['sku'], row.get('on_hand'), row.get('counted')),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] replace_stock_check_skus failed: {exc}', file=sys.stderr)
        return False


def update_stock_check_sku_counted(run_id, sku, counted):
    """UPDATE the stock_check_skus row for (run_id, sku) with the new counted value.
    Returns True on success, False on failure.  No-op if run_id is None."""
    if run_id is None:
        return False
    try:
        conn = get_db()
        try:
            conn.execute(
                'UPDATE stock_check_skus SET counted = ? '
                'WHERE stock_check_id = ? AND sku = ?',
                (counted, run_id, sku),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] update_stock_check_sku_counted failed: {exc}', file=sys.stderr)
        return False


def finalize_stock_check_skus(run_id, verify_data):
    """UPDATE each stock_check_skus row for run_id with new_on_hand, final_counted, matched.

    verify_data: dict mapping sku -> {'new_on_hand': int, 'final_counted': int, 'matched': bool}
    Returns True on success, False on failure.  No-op if run_id is None.
    """
    if run_id is None:
        return False
    try:
        conn = get_db()
        try:
            for sku, vals in verify_data.items():
                conn.execute(
                    'UPDATE stock_check_skus '
                    'SET new_on_hand = ?, final_counted = ?, matched = ? '
                    'WHERE stock_check_id = ? AND sku = ?',
                    (
                        vals.get('new_on_hand'),
                        vals.get('final_counted'),
                        1 if vals.get('matched') else 0,
                        run_id,
                        sku,
                    ),
                )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] finalize_stock_check_skus failed: {exc}', file=sys.stderr)
        return False


def mark_stock_check_abandoned(run_id):
    """Mark a stock_checks row as abandoned.
    Returns True on success, False on failure.  No-op if run_id is None."""
    if run_id is None:
        return False
    try:
        conn = get_db()
        try:
            conn.execute(
                "UPDATE stock_checks "
                "SET status = 'abandoned', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND status != 'completed'",
                (run_id,),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] mark_stock_check_abandoned failed: {exc}', file=sys.stderr)
        return False


@app.route('/studio/tutorial')
@studio_login_required
def studio_tutorial():
    current_step = session.get('begin_count_step', 0)
    current_store_id = session.get('store_id', '').lstrip('0') or '0'
    bp_upload_done = 'begin_count_bp_onhand' in session
    bp_filename = session.get('begin_count_bp_filename', '')

    # Load master lookups (used by both Step 3 grid and Step 4 variance rows)
    master = load_master_skus()
    sku_status = load_sku_status()
    sku_prices = load_sku_prices()

    # Step 3: load assigned SKU list using the same helpers as the studio homepage
    scan = scan_input_files()
    assigned_skus = []
    skulist_filename = None
    if scan['sku_lists']:
        skulist_filename = scan['sku_lists'][0][0]
        filepath = os.path.join(INPUT_DIR, skulist_filename)
        sku_rows = parse_csv(filepath)
        sku_names = {}
        sku_set = set()
        for row in sku_rows:
            sku = row.get('sku', '').strip()
            name = row.get('product name', '').strip()
            if sku and not is_excluded_sku(sku):
                sku_set.add(sku)
                sku_names[sku] = name
        for sku in sorted(sku_set):
            desc = master.get(sku.upper(), '') or sku_names.get(sku, '') or sku
            image_filename = find_image_for_sku(sku)
            status = sku_status.get(sku.upper())
            price = sku_prices.get(sku.upper())
            assigned_skus.append({
                'sku': sku,
                'description': desc,
                'image_filename': image_filename,
                'status': status,
                'retail_price': price,
            })

    # Migration: if session has the old flat shape (sku -> int) instead of the new
    # nested shape (sku -> {dept: int, ...}), wipe it so the user re-uploads.
    _oc_raw = session.get('begin_count_oc_counted', {})
    if _oc_raw and any(isinstance(v, int) for v in _oc_raw.values()):
        print('[migrate] begin_count_oc_counted has old flat shape — wiping for re-upload',
              file=sys.stderr)
        session.pop('begin_count_oc_counted', None)
        session.pop('begin_count_oc_filename', None)
        session.modified = True

    # Step 4: rebuild variance rows from session if OC count report already uploaded
    oc_uploaded = 'begin_count_oc_counted' in session
    oc_filename = session.get('begin_count_oc_filename', '')
    oc_matched_rows = 0
    variance_rows = []
    if oc_uploaded:
        oc_counted = session.get('begin_count_oc_counted', {})
        bp_onhand = session.get('begin_count_bp_onhand', {})
        desc_map = {item['sku'].upper(): item['description'] for item in assigned_skus}
        for sku in sorted(oc_counted.keys()):
            desc = desc_map.get(sku.upper(), '') or master.get(sku.upper(), '') or sku
            dept_counts = oc_counted[sku] if isinstance(oc_counted[sku], dict) else {}
            acc   = dept_counts.get('accessory', 0)
            bins  = dept_counts.get('bins_backstock', 0)
            dcr   = dept_counts.get('dcr_piercing', 0)
            vis   = dept_counts.get('visual_display', 0)
            total_counted = acc + bins + dcr + vis
            bp_val = bp_onhand.get(sku) if bp_onhand else None
            variance = (total_counted - bp_val) if bp_val is not None else None
            variance_rows.append({
                'sku': sku,
                'description': desc,
                'bp_onhand': bp_val,
                'accessory': acc,
                'bins_backstock': bins,
                'dcr_piercing': dcr,
                'visual_display': vis,
                'total_counted': total_counted,
                'variance': variance,
            })
        oc_matched_rows = len(variance_rows)

    # Step 7: rebuild crosscheck rows if verify upload already done this session
    bp_verify_raw = session.get('begin_count_bp_verify_onhand', {})
    bp_verify_uploaded = bool(bp_verify_raw)
    bp_verify_filename = session.get('begin_count_bp_verify_filename', '')
    bp_verify_matched_rows = sum(1 for v in bp_verify_raw.values() if v != 0) if bp_verify_uploaded else 0
    crosscheck_rows = []
    summary = None
    if bp_verify_uploaded:
        oc_counted_s7 = session.get('begin_count_oc_counted', {})
        desc_map7 = {item['sku'].upper(): item['description'] for item in assigned_skus}
        for sku in sorted(bp_verify_raw.keys()):
            product_name = desc_map7.get(sku.upper(), '') or master.get(sku.upper(), '') or sku
            new_on_hand = bp_verify_raw[sku]
            _s7_val = oc_counted_s7.get(sku, 0)
            # Aggregate from nested dept dict; fall back gracefully for old flat shape
            if isinstance(_s7_val, dict):
                final_counted = sum(_s7_val.values())
            else:
                final_counted = int(_s7_val) if _s7_val else 0
            match = (new_on_hand == final_counted)
            crosscheck_rows.append({
                'sku': sku,
                'product_name': product_name,
                'new_on_hand': new_on_hand,
                'final_counted': final_counted,
                'match': match,
            })
        total_s7 = len(crosscheck_rows)
        reconciled_s7 = sum(1 for r in crosscheck_rows if r['match'])
        summary = {
            'total_skus': total_s7,
            'reconciled': reconciled_s7,
            'still_off': total_s7 - reconciled_s7,
            'bp_filename': session.get('begin_count_bp_filename', ''),
            'oc_filename': session.get('begin_count_oc_filename', ''),
            'bp_verify_filename': bp_verify_filename,
            'completed_at': '',  # not recorded on resume
            'counter_name': session.get('begin_count_counter_name', ''),
            'duration': _resume_duration(session),
        }

    # Step 6: condensed variance table — non-zero rows only, sorted by abs(variance) desc
    _s6_oc_counted = session.get('begin_count_oc_counted')
    step6_oc_counted_present = _s6_oc_counted is not None
    step6_variance_rows = []
    if step6_oc_counted_present:
        _s6_bp_onhand = session.get('begin_count_bp_onhand', {})
        _s6_desc_map = {item['sku'].upper(): item['description'] for item in assigned_skus}
        for sku in sorted(_s6_oc_counted.keys()):
            _s6_dept = _s6_oc_counted[sku]
            if isinstance(_s6_dept, dict):
                _s6_total = sum(_s6_dept.values())
            else:
                _s6_total = int(_s6_dept) if _s6_dept else 0
            _s6_bp = _s6_bp_onhand.get(sku) or 0
            _s6_variance = _s6_total - _s6_bp
            if _s6_variance != 0:
                desc = _s6_desc_map.get(sku.upper(), '') or master.get(sku.upper(), '') or sku
                step6_variance_rows.append({
                    'sku': sku,
                    'description': desc,
                    'bp_on_hand': _s6_bp,
                    'total_counted': _s6_total,
                    'variance': _s6_variance,
                })
        # Sort by abs(variance) descending, ties broken by SKU ascending
        step6_variance_rows.sort(key=lambda r: (-abs(r['variance']), r['sku']))

    # Step indicator: compute completion state per step (1–7)
    _done_map = {
        1: bool(session.get('begin_count_bp_onhand')),
        2: bool(session.get('begin_count_step2_done')),
        3: bool(session.get('begin_count_step3_done')),
        4: bool(session.get('begin_count_oc_counted')),
        5: bool(session.get('begin_count_step5_done')),
        6: bool(session.get('begin_count_step6_done')),
        7: bool(session.get('begin_count_bp_verify_onhand')),
    }
    step_status = []
    for _num in range(1, 8):
        if _num == current_step:
            _status = 'current'
        elif _done_map[_num]:
            _status = 'completed'
        else:
            _status = 'locked'
        step_status.append({'step_num': _num, 'status': _status})

    return render_template('studio_tutorial.html',
                           current_step=current_step,
                           current_store_id=current_store_id,
                           bp_upload_done=bp_upload_done,
                           bp_filename=bp_filename,
                           assigned_skus=assigned_skus,
                           skulist_filename=skulist_filename,
                           skulist_count=len(assigned_skus),
                           oc_uploaded=oc_uploaded,
                           oc_filename=oc_filename,
                           oc_matched_rows=oc_matched_rows,
                           variance_rows=variance_rows,
                           has_bp=bp_upload_done,
                           bp_verify_uploaded=bp_verify_uploaded,
                           bp_verify_filename=bp_verify_filename,
                           bp_verify_matched_rows=bp_verify_matched_rows,
                           crosscheck_rows=crosscheck_rows,
                           summary=summary,
                           step_status=step_status,
                           counter_name=session.get('begin_count_counter_name', ''),
                           step6_oc_counted_present=step6_oc_counted_present,
                           step6_variance_rows=step6_variance_rows)


@app.route('/studio/tutorial/step', methods=['POST'])
@studio_login_required
def studio_tutorial_step():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    step = data.get('step')
    if step is None:
        return jsonify({'ok': False, 'error': 'Missing step field'}), 400
    if not isinstance(step, int) or step < 0 or step > 7:
        return jsonify({'ok': False, 'error': 'step must be an integer 0–7'}), 400
    old_step = session.get('begin_count_step', 0)
    session['begin_count_step'] = step
    # Capture start timestamp exactly once: intro (0) → Step 1 transition.
    # Guard prevents the timer resetting if the user navigates backward and re-enters Step 1.
    if step == 1 and old_step == 0 and 'begin_count_started_at' not in session:
        session['begin_count_started_at'] = datetime.now(timezone.utc).isoformat()
        # Analytics: create the stock_checks row for this run.
        # Errors are swallowed — must not affect the user's flow.
        try:
            _store_id = session.get('store_id')
            if _store_id:
                _run_id = create_stock_check_row(
                    store_id=_store_id,
                    counter_name=session.get('begin_count_counter_name', ''),
                    started_at=datetime.now(timezone.utc),
                )
                if _run_id is not None:
                    session['begin_count_run_id'] = _run_id
            else:
                print('[analytics] step 0→1: store_id missing from session', file=sys.stderr)
        except Exception as _exc:
            print(f'[analytics] step 0→1 row creation failed: {_exc}', file=sys.stderr)
    # When advancing forward, mark the step being left as done.
    # Steps 1, 4, 7 use data-presence checks; only 2, 3, 5, 6 need explicit flags.
    if step > old_step:
        _done_flags = {
            2: 'begin_count_step2_done',
            3: 'begin_count_step3_done',
            5: 'begin_count_step5_done',
            6: 'begin_count_step6_done',
        }
        if old_step in _done_flags:
            session[_done_flags[old_step]] = True
        # Analytics: track the furthest step reached.
        bump_furthest_step(session.get('begin_count_run_id'), step)
    return jsonify({'ok': True})


@app.route('/studio/tutorial/upload-bp', methods=['POST'])
@studio_login_required
def studio_tutorial_upload_bp():
    """Accept a Brightpearl Inventory Summary CSV for the Begin Count wizard (Step 1).
    Parsed on-hand quantities are stored in session['begin_count_bp_onhand'].
    Kept separate from session['bp_onhand'] used by the Start Your Stock Check flow."""
    f = request.files.get('bp_file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'No file uploaded'}), 400
    try:
        filename = f.filename
        raw_bytes = f.read()
        text = clean_csv_content(raw_bytes)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return jsonify({'ok': False, 'error': 'Could not read file headers'}), 400
        headers = [h.strip().lower() for h in reader.fieldnames]
        reader.fieldnames = headers
        sku_col = None
        qty_col = None
        for h in headers:
            if h == 'sku' and sku_col is None:
                sku_col = h
        for h in headers:
            if ('on hand' in h or 'onhand' in h or 'on-hand' in h) and qty_col is None:
                qty_col = h
        if qty_col is None:
            for h in headers:
                if 'quantity' in h and qty_col is None:
                    qty_col = h
        if sku_col is None:
            return jsonify({'ok': False, 'error': 'No SKU column found in uploaded file'}), 400
        if qty_col is None:
            return jsonify({'ok': False, 'error': 'No on-hand quantity column found. Expected a column containing "on hand" or "quantity".'}), 400
        bp_data = {}
        for row in reader:
            sku = (row.get(sku_col) or '').strip().upper()
            qty_str = (row.get(qty_col) or '').strip()
            if not sku or is_excluded_sku(sku):
                continue
            try:
                qty = int(float(qty_str))
            except (ValueError, TypeError):
                qty = 0
            bp_data[sku] = qty
        session['begin_count_bp_onhand'] = bp_data
        session['begin_count_bp_filename'] = filename
        # Analytics: record BP filename, assigned SKU count, and week identifier.
        # Errors are swallowed — must not affect the user's flow.
        try:
            _run_id = session.get('begin_count_run_id')
            _skl_filename = None
            _week_id = None
            _scan = scan_input_files()
            if _scan['sku_lists']:
                _skl_filename = _scan['sku_lists'][0][0]
                _week_id = parse_week_identifier(_skl_filename)
            update_stock_check_row(
                _run_id,
                bp_filename=filename,
                assigned_sku_count=len(bp_data),
                skulist_filename=_skl_filename,
                week_identifier=_week_id,
            )
            bump_furthest_step(_run_id, 1)
        except Exception as _exc:
            print(f'[analytics] upload-bp update failed: {_exc}', file=sys.stderr)
        return jsonify({'ok': True, 'sku_count': len(bp_data), 'filename': filename})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/studio/tutorial/upload-oc', methods=['POST'])
@studio_login_required
def studio_tutorial_upload_oc():
    """Accept an OmniCounts Count Report CSV for the Begin Count wizard (Step 4).
    Sums counts per SKU, filters to this week's assigned SKUs, and stores results in session."""
    f = request.files.get('oc_file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'No file uploaded'}), 400
    try:
        filename = f.filename
        raw_bytes = f.read()
        text = clean_csv_content(raw_bytes)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return jsonify({'ok': False, 'error': 'Could not read file headers'}), 400
        headers = [h.strip().lower() for h in reader.fieldnames]
        reader.fieldnames = headers

        # Detect SKU column
        sku_col = None
        for candidate in ['sku', 'product sku', 'product code', 'item sku', 'code']:
            if candidate in headers:
                sku_col = candidate
                break

        # Detect Counted column
        counted_col = None
        for candidate in ['counted units', 'counted', 'count', 'count qty', 'counted quantity', 'quantity', 'qty']:
            if candidate in headers:
                counted_col = candidate
                break

        # Detect Department Desc column (required for per-department counts)
        dept_col = None
        for candidate in ['department desc', 'department description', 'dept desc',
                          'department name', 'department']:
            if candidate in headers:
                dept_col = candidate
                break

        if sku_col is None:
            return jsonify({'ok': False, 'error': 'No SKU column found. Expected one of: SKU, Product SKU, Product Code, Item SKU, Code.'}), 400
        if counted_col is None:
            return jsonify({'ok': False, 'error': 'No count column found. Expected one of: Counted Units, Counted, Count, Count Qty, Counted Quantity, Quantity, Qty.'}), 400
        if dept_col is None:
            return jsonify({'ok': False, 'error': 'No Department Desc column found. Expected "Department Desc" in the OmniCounts Count Report.'}), 400

        # Aggregate counts by (SKU, department_key) across all rows
        _empty_depts = lambda: {'accessory': 0, 'bins_backstock': 0, 'dcr_piercing': 0, 'visual_display': 0}
        raw_counts = {}  # {sku_upper: {dept_key: int}}
        for row in reader:
            sku = (row.get(sku_col) or '').strip().upper()
            dept_raw = (row.get(dept_col) or '').strip()
            qty_str = (row.get(counted_col) or '').strip()
            if not sku or is_excluded_sku(sku):
                continue
            dept_key = map_department_desc(dept_raw)
            if dept_key is None:
                print(f'[upload-oc] unknown Department Desc: {dept_raw!r} — skipping row',
                      file=sys.stderr)
                continue
            try:
                qty = int(float(qty_str))
            except (ValueError, TypeError):
                qty = 0
            if sku not in raw_counts:
                raw_counts[sku] = _empty_depts()
            raw_counts[sku][dept_key] += qty

        # Load assigned SKU list to filter results
        scan = scan_input_files()
        assigned_set = set()
        assigned_names = {}
        if scan['sku_lists']:
            skulist_path = os.path.join(INPUT_DIR, scan['sku_lists'][0][0])
            for row in parse_csv(skulist_path):
                sku = row.get('sku', '').strip().upper()
                name = row.get('product name', '').strip()
                if sku and not is_excluded_sku(sku):
                    assigned_set.add(sku)
                    assigned_names[sku] = name

        master = load_master_skus()

        # Build nested counted dict filtered to assigned SKUs (default all-zero for missing)
        oc_counted = {}
        for sku in sorted(assigned_set):
            oc_counted[sku] = raw_counts.get(sku, _empty_depts())

        session['begin_count_oc_counted'] = oc_counted
        session['begin_count_oc_filename'] = filename
        session.modified = True

        # Analytics: record OC filename, total variances, and per-SKU rows.
        # DB receives the aggregated total (sum of 4 depts) — schema unchanged.
        # Errors are swallowed — must not affect the user's flow.
        try:
            _run_id = session.get('begin_count_run_id')
            _bp_onhand = session.get('begin_count_bp_onhand', {})
            _sku_data = []
            _total_variances = 0
            for sku, dept_counts in oc_counted.items():
                agg = sum(dept_counts.values())
                _sku_data.append({'sku': sku, 'on_hand': _bp_onhand.get(sku), 'counted': agg})
                if _bp_onhand.get(sku) is not None and agg != _bp_onhand[sku]:
                    _total_variances += 1
            update_stock_check_row(_run_id, oc_filename=filename, total_variances=_total_variances)
            replace_stock_check_skus(_run_id, _sku_data)
            bump_furthest_step(_run_id, 4)
        except Exception as _exc:
            print(f'[analytics] upload-oc update failed: {_exc}', file=sys.stderr)

        # Build variance rows for the response (includes per-dept breakdown)
        bp_onhand = session.get('begin_count_bp_onhand', {})
        variance_rows = []
        for sku in sorted(oc_counted.keys()):
            desc = master.get(sku, '') or assigned_names.get(sku, '') or sku
            dept_counts = oc_counted[sku]
            acc   = dept_counts.get('accessory', 0)
            bins  = dept_counts.get('bins_backstock', 0)
            dcr   = dept_counts.get('dcr_piercing', 0)
            vis   = dept_counts.get('visual_display', 0)
            total_counted = acc + bins + dcr + vis
            bp_val = bp_onhand.get(sku) if bp_onhand else None
            variance = (total_counted - bp_val) if bp_val is not None else None
            variance_rows.append({
                'sku': sku,
                'description': desc,
                'bp_onhand': bp_val,
                'accessory': acc,
                'bins_backstock': bins,
                'dcr_piercing': dcr,
                'visual_display': vis,
                'total_counted': total_counted,
                'variance': variance,
            })

        return jsonify({
            'ok': True,
            'sku_count': len(oc_counted),
            'filename': filename,
            'variance_rows': variance_rows,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/studio/tutorial/variance/update', methods=['POST'])
@studio_login_required
def studio_tutorial_variance_update():
    """Update a single SKU's per-department count in the session (Step 4 editable table).

    Request JSON: {sku, department, counted}
    department must be one of: accessory, bins_backstock, dcr_piercing, visual_display.
    DB receives the aggregated total (sum of 4 depts) — schema unchanged.
    """
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    sku = (data.get('sku') or '').strip().upper()
    department = (data.get('department') or '').strip().lower()
    counted = data.get('counted')
    if not sku:
        return jsonify({'ok': False, 'error': 'Missing SKU'}), 400
    if department not in DEPARTMENT_KEYS:
        return jsonify({'ok': False, 'error': f'Invalid department: {department!r}'}), 400
    if counted is None:
        return jsonify({'ok': False, 'error': 'Missing counted'}), 400
    try:
        counted = int(counted)
        if counted < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'counted must be a non-negative integer'}), 400

    # Reassign to ensure Flask detects the mutation
    oc_counted = dict(session.get('begin_count_oc_counted', {}))
    existing = oc_counted.get(sku)
    if isinstance(existing, dict):
        dept_counts = dict(existing)
    else:
        dept_counts = {'accessory': 0, 'bins_backstock': 0, 'dcr_piercing': 0, 'visual_display': 0}
    dept_counts[department] = counted
    oc_counted[sku] = dept_counts
    session['begin_count_oc_counted'] = oc_counted
    session.modified = True

    # Recompute aggregate for DB write (schema stores aggregate only)
    aggregated = sum(dept_counts.values())

    # Analytics: persist the updated aggregated count to the DB row.
    try:
        _run_id = session.get('begin_count_run_id')
        update_stock_check_sku_counted(_run_id, sku, aggregated)
    except Exception as _exc:
        print(f'[analytics] variance-update sku write failed: {_exc}', file=sys.stderr)

    bp_onhand = session.get('begin_count_bp_onhand', {})
    bp_val = bp_onhand.get(sku) if bp_onhand else None
    variance = (aggregated - bp_val) if bp_val is not None else None

    return jsonify({'ok': True, 'sku': sku, 'total_counted': aggregated, 'variance': variance})


@app.route('/studio/tutorial/upload-bp-verify', methods=['POST'])
@studio_login_required
def studio_tutorial_upload_bp_verify():
    """Accept a fresh post-adjustment Brightpearl Inventory Summary CSV for Step 7.
    Crosschecks the new on-hand values against the final Step 4 counts stored in session.
    Stores results in session['begin_count_bp_verify_onhand'] and
    session['begin_count_bp_verify_filename']. Never touches begin_count_bp_onhand or
    begin_count_oc_counted — those are read-only from this route's perspective."""

    # Guard: Step 4 data must exist before Step 7 can run
    oc_counted = session.get('begin_count_oc_counted', {})
    if not oc_counted:
        return jsonify({'ok': False, 'error': 'Please complete Step 4 before verifying adjustments.'}), 400

    f = request.files.get('bp_verify_file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'No file uploaded'}), 400

    try:
        filename = f.filename
        raw_bytes = f.read()
        text = clean_csv_content(raw_bytes)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return jsonify({'ok': False, 'error': 'Could not read file headers'}), 400
        headers = [h.strip().lower() for h in reader.fieldnames]
        reader.fieldnames = headers

        # Same column-detection logic as /upload-bp
        sku_col = None
        qty_col = None
        for h in headers:
            if h == 'sku' and sku_col is None:
                sku_col = h
        for h in headers:
            if ('on hand' in h or 'onhand' in h or 'on-hand' in h) and qty_col is None:
                qty_col = h
        if qty_col is None:
            for h in headers:
                if 'quantity' in h and qty_col is None:
                    qty_col = h

        if sku_col is None:
            return jsonify({'ok': False, 'error': 'No SKU column found in uploaded file'}), 400
        if qty_col is None:
            return jsonify({'ok': False, 'error': 'No on-hand quantity column found. Expected a column containing "on hand" or "quantity".'}), 400

        # Parse raw on-hand values from file
        raw_bp = {}
        for row in reader:
            sku = (row.get(sku_col) or '').strip().upper()
            qty_str = (row.get(qty_col) or '').strip()
            if not sku or is_excluded_sku(sku):
                continue
            try:
                qty = int(float(qty_str))
            except (ValueError, TypeError):
                qty = 0
            raw_bp[sku] = qty

        # Load assigned SKUs for this week
        scan = scan_input_files()
        assigned_set = set()
        assigned_names = {}
        if scan['sku_lists']:
            skulist_path = os.path.join(INPUT_DIR, scan['sku_lists'][0][0])
            for row in parse_csv(skulist_path):
                sku = row.get('sku', '').strip().upper()
                name = row.get('product name', '').strip()
                if sku and not is_excluded_sku(sku):
                    assigned_set.add(sku)
                    assigned_names[sku] = name

        master = load_master_skus()

        # Build verify dict: all assigned SKUs, default 0 if missing from file
        bp_verify = {}
        for sku in sorted(assigned_set):
            bp_verify[sku] = raw_bp.get(sku, 0)

        # Count how many assigned SKUs were actually present in the uploaded file
        matched_rows = sum(1 for sku in assigned_set if sku in raw_bp)

        # Persist to session (read-only for begin_count_bp_onhand / begin_count_oc_counted)
        session['begin_count_bp_verify_onhand'] = bp_verify
        session['begin_count_bp_verify_filename'] = filename
        session.modified = True

        # Build crosscheck rows
        crosscheck_rows = []
        for sku in sorted(assigned_set):
            product_name = master.get(sku, '') or assigned_names.get(sku, '') or sku
            new_on_hand = bp_verify[sku]
            _oc_val = oc_counted.get(sku, 0)
            # Aggregate from nested dept dict; fall back gracefully for old flat shape
            if isinstance(_oc_val, dict):
                final_counted = sum(_oc_val.values())
            else:
                final_counted = int(_oc_val) if _oc_val else 0
            match = (new_on_hand == final_counted)
            crosscheck_rows.append({
                'sku': sku,
                'product_name': product_name,
                'new_on_hand': new_on_hand,
                'final_counted': final_counted,
                'match': match,
            })

        total_skus = len(crosscheck_rows)
        reconciled = sum(1 for r in crosscheck_rows if r['match'])
        still_off = total_skus - reconciled

        # Analytics: mark the stock check complete with final stats.
        try:
            _run_id = session.get('begin_count_run_id')
            _started_at_str = session.get('begin_count_started_at')
            _duration_seconds = None
            if _started_at_str:
                try:
                    _started_dt = datetime.fromisoformat(_started_at_str)
                    _duration_seconds = int(
                        (datetime.now(timezone.utc) - _started_dt).total_seconds()
                    )
                except Exception:
                    pass
            update_stock_check_row(
                _run_id,
                bp_verify_filename=filename,
                variances_reconciled=reconciled,
                variances_still_off=still_off,
                completed_at=datetime.now(timezone.utc),
                duration_seconds=_duration_seconds,
                status='completed',
            )
            _verify_data = {r['sku']: {'new_on_hand': r['new_on_hand'], 'final_counted': r['final_counted'], 'matched': r['match']} for r in crosscheck_rows}
            finalize_stock_check_skus(_run_id, _verify_data)
            bump_furthest_step(_run_id, 7)
        except Exception as _exc:
            print(f'[analytics] upload-bp-verify finalize failed: {_exc}', file=sys.stderr)

        completed_at = datetime.now().strftime('%B %d, %Y at %I:%M %p')

        summary = {
            'total_skus': total_skus,
            'reconciled': reconciled,
            'still_off': still_off,
            'bp_filename': session.get('begin_count_bp_filename', ''),
            'oc_filename': session.get('begin_count_oc_filename', ''),
            'bp_verify_filename': filename,
            'completed_at': completed_at,
            'counter_name': session.get('begin_count_counter_name', ''),
            'duration': _resume_duration(session),
        }

        return jsonify({
            'ok': True,
            'filename': filename,
            'matched_rows': matched_rows,
            'crosscheck_rows': crosscheck_rows,
            'summary': summary,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/studio/tutorial/reset', methods=['POST'])
@studio_login_required
def studio_tutorial_reset():
    """Clear all Begin Count session keys. Never touches any Start Your Stock Check keys."""
    # Analytics: mark any in-progress run as abandoned before clearing the session.
    try:
        _run_id = session.get('begin_count_run_id')
        if _run_id is not None:
            mark_stock_check_abandoned(_run_id)
    except Exception as _exc:
        print(f'[analytics] reset abandon failed: {_exc}', file=sys.stderr)

    _keys = [
        'begin_count_step',
        'begin_count_bp_onhand',
        'begin_count_bp_filename',
        'begin_count_oc_counted',
        'begin_count_oc_filename',
        'begin_count_bp_verify_onhand',
        'begin_count_bp_verify_filename',
        'begin_count_step2_done',
        'begin_count_step3_done',
        'begin_count_step5_done',
        'begin_count_step6_done',
        'begin_count_counter_name',
        'begin_count_started_at',
        'begin_count_run_id',
    ]
    for key in _keys:
        session.pop(key, None)
    return jsonify({'ok': True})


@app.route('/studio/tutorial/counter-name', methods=['POST'])
@studio_login_required
def studio_tutorial_counter_name():
    """Store the counter's name in the session for the Begin Count flow."""
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    name = data.get('name', '')
    if not isinstance(name, str):
        return jsonify({'ok': False, 'error': 'Name must be a string'}), 400
    name = name.strip()
    if len(name) < 1:
        return jsonify({'ok': False, 'error': 'Name cannot be empty'}), 400
    if len(name) > 100:
        return jsonify({'ok': False, 'error': 'Name must be 100 characters or fewer'}), 400
    session['begin_count_counter_name'] = name
    return jsonify({'ok': True})


@app.route('/studio/omnicounts', methods=['GET', 'POST'])
@studio_login_required
def studio_omnicounts():
    if request.method == 'GET':
        return render_template('studio_omnicounts.html')

    store_number = request.form.get('store_number', '').strip()
    if not store_number or not store_number.isdigit():
        flash('Store number must be numeric.', 'error')
        return redirect(url_for('studio_omnicounts'))

    bp_file = request.files.get('bp_file')
    if not bp_file or not bp_file.filename:
        flash('Please upload a Brightpearl inventory CSV.', 'error')
        return redirect(url_for('studio_omnicounts'))

    error, result = _generate_omnicounts(store_number, bp_file)
    if error:
        flash(error, 'error')
        return redirect(url_for('studio_omnicounts'))

    result_bytes, download_name = result
    return send_file(result_bytes, mimetype='text/csv', as_attachment=True, download_name=download_name)


@app.route('/studio/catalog')
def studio_catalog():
    if not session.get('studio_logged_in') and not session.get('hq_logged_in'):
        return redirect(url_for('studio_login'))

    master_filename = None
    master = {}
    sku_status = {}
    sku_prices = {}
    msf_path = os.path.join(MASTER_DIR, 'SKU_Master.csv')
    if os.path.isfile(msf_path):
        master_filename = 'SKU_Master.csv'
        master = load_master_skus()
        sku_status = load_sku_status()
        sku_prices = load_sku_prices()

    displays = []
    planogram_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'planogram_order.json')
    if os.path.isfile(planogram_path):
        try:
            with open(planogram_path, 'r') as f:
                planogram_data = json.load(f)
            displays = planogram_data.get('displays', [])
        except Exception:
            pass

    skus = {}
    for display in displays:
        for slot in display.get('slots', []):
            slot_desc = slot.get('description', '')
            slot_price = slot.get('price')
            for sku_code in slot.get('skus', []):
                upper = sku_code.strip().upper()
                if upper in skus or is_excluded_sku(upper):
                    continue
                desc = master.get(upper) or slot_desc or ''
                price = sku_prices.get(upper) if upper in sku_prices else slot_price
                skus[upper] = {
                    'sku': upper,
                    'description': desc,
                    'image_filename': find_image_for_sku(upper),
                    'status': sku_status.get(upper),
                    'retail_price': price,
                }
    # Also include master SKUs not covered by the planogram
    for sku_code, desc in master.items():
        if sku_code not in skus and not is_excluded_sku(sku_code):
            skus[sku_code] = {
                'sku': sku_code,
                'description': desc,
                'image_filename': find_image_for_sku(sku_code),
                'status': sku_status.get(sku_code),
                'retail_price': sku_prices.get(sku_code),
            }

    sku_count = len(skus)
    return render_template('catalog.html',
                           skus=skus,
                           displays=displays,
                           sku_count=sku_count,
                           master_filename=master_filename)


@app.route('/studio/catalog/debug')
@studio_login_required
def studio_catalog_debug():
    """Temporary diagnostic endpoint — shows what the catalog route actually sees on this server."""
    import traceback
    out = {}
    out['MASTER_DIR'] = MASTER_DIR
    out['DATABASE_DIR'] = DATABASE_DIR
    out['IMAGES_DIR'] = IMAGES_DIR
    msf_path = os.path.join(MASTER_DIR, 'SKU_Master.csv')
    out['msf_path'] = msf_path
    out['msf_exists'] = os.path.isfile(msf_path)
    try:
        master = load_master_skus()
        out['master_count'] = len(master)
        out['master_first5'] = list(master.keys())[:5]
    except Exception:
        out['master_error'] = traceback.format_exc()
    try:
        status = load_sku_status()
        out['status_count'] = len(status)
    except Exception:
        out['status_error'] = traceback.format_exc()
    try:
        prices = load_sku_prices()
        out['prices_count'] = len(prices)
    except Exception:
        out['prices_error'] = traceback.format_exc()
    planogram_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'planogram_order.json')
    out['planogram_exists'] = os.path.isfile(planogram_path)
    if out['planogram_exists']:
        with open(planogram_path) as f:
            pdata = json.load(f)
        all_skus = []
        for d in pdata.get('displays', []):
            for slot in d.get('slots', []):
                all_skus.extend(slot.get('skus', []))
        out['planogram_sku_count'] = len(all_skus)
        out['planogram_first5'] = all_skus[:5]
        if 'master_first5' in out:
            out['sample_matches'] = {
                s: s.strip().upper() in load_master_skus()
                for s in all_skus[:5]
            }
    images_dir_exists = os.path.isdir(IMAGES_DIR)
    out['images_dir_exists'] = images_dir_exists
    if images_dir_exists:
        out['images_count'] = len(os.listdir(IMAGES_DIR))
        out['images_first3'] = os.listdir(IMAGES_DIR)[:3]
    return jsonify(out)


@app.route('/studio/stock-check')
@studio_login_required
def studio_stock_check():
    scan = scan_input_files()
    sku_items = []
    sku_list_filename = None
    if scan['sku_lists']:
        sku_list_filename = scan['sku_lists'][0][0]
        filepath = os.path.join(INPUT_DIR, sku_list_filename)
        sku_rows = parse_csv(filepath)
        sku_names = {}
        sku_set = set()
        for row in sku_rows:
            sku = row.get('sku', '').strip()
            name = row.get('product name', '').strip()
            if sku and not is_excluded_sku(sku):
                sku_set.add(sku)
                sku_names[sku] = name
        master = load_master_skus()
        sku_status = load_sku_status()
        sku_prices = load_sku_prices()
        for sku in sorted(sku_set):
            desc = master.get(sku.upper(), '') or sku_names.get(sku, '') or sku
            image_filename = find_image_for_sku(sku)
            status = sku_status.get(sku.upper())
            price = sku_prices.get(sku.upper())
            sku_items.append({
                'sku': sku,
                'description': desc,
                'image_filename': image_filename,
                'status': status,
                'retail_price': price,
            })
    return render_template('stock_check.html',
                           sku_items=sku_items,
                           sku_list_filename=sku_list_filename)


@app.route('/studio/stock-check/upload', methods=['POST'])
@studio_login_required
def studio_stock_check_upload():
    f = request.files.get('bp_file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'No file uploaded'}), 400
    try:
        raw_bytes = f.read()
        text = clean_csv_content(raw_bytes)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return jsonify({'ok': False, 'error': 'Could not read file headers'}), 400
        headers = [h.strip().lower() for h in reader.fieldnames]
        reader.fieldnames = headers
        sku_col = None
        qty_col = None
        for h in headers:
            if h == 'sku' and sku_col is None:
                sku_col = h
        for h in headers:
            if ('on hand' in h or 'onhand' in h or 'on-hand' in h) and qty_col is None:
                qty_col = h
        if qty_col is None:
            for h in headers:
                if 'quantity' in h and qty_col is None:
                    qty_col = h
        if sku_col is None:
            return jsonify({'ok': False, 'error': 'No SKU column found in uploaded file'}), 400
        if qty_col is None:
            return jsonify({'ok': False, 'error': 'No on-hand quantity column found. Expected a column containing "on hand" or "quantity".'}), 400
        bp_data = {}
        for row in reader:
            sku = (row.get(sku_col) or '').strip().upper()
            qty_str = (row.get(qty_col) or '').strip()
            if not sku or is_excluded_sku(sku):
                continue
            try:
                qty = int(float(qty_str))
            except (ValueError, TypeError):
                qty = 0
            bp_data[sku] = qty
        session['bp_onhand'] = bp_data
        return jsonify({'ok': True, 'sku_count': len(bp_data)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/studio/stock-check/count')
@studio_login_required
def studio_stock_check_count():
    scan = scan_input_files()
    sku_items = []
    if scan['sku_lists']:
        sku_list_filename = scan['sku_lists'][0][0]
        filepath = os.path.join(INPUT_DIR, sku_list_filename)
        sku_rows = parse_csv(filepath)
        sku_names = {}
        sku_set = set()
        for row in sku_rows:
            sku = row.get('sku', '').strip()
            name = row.get('product name', '').strip()
            if sku and not is_excluded_sku(sku):
                sku_set.add(sku)
                sku_names[sku] = name
        master = load_master_skus()
        sku_status = load_sku_status()
        sku_prices = load_sku_prices()
        bp_onhand = session.get('bp_onhand', {})
        for sku in sorted(sku_set):
            desc = master.get(sku.upper(), '') or sku_names.get(sku, '') or sku
            image_filename = find_image_for_sku(sku)
            status = sku_status.get(sku.upper())
            price = sku_prices.get(sku.upper())
            bp_qty = bp_onhand.get(sku.upper())
            sku_items.append({
                'sku': sku,
                'description': desc,
                'image_filename': image_filename,
                'status': status,
                'retail_price': price,
                'bp_onhand': bp_qty if bp_qty is not None else 0,
                'missing_in_bp': bp_qty is None,
            })
    return render_template('stock_check_count.html', sku_items=sku_items)


@app.route('/studio/stock-check/submit', methods=['POST'])
@studio_login_required
def studio_stock_check_submit():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    store_id = session.get('store_id', '')
    store_name = store_id or 'Studio'
    if store_id:
        conn = get_db()
        row = conn.execute('SELECT name FROM stores WHERE store_id = ?', (store_id,)).fetchone()
        conn.close()
        if row:
            store_name = row['name']
    # Save counts to session so the verify flow can access them
    sc_counts = {}
    for item in data:
        sku = (item.get('sku', '') or '').strip().upper()
        if sku:
            sc_counts[sku] = {
                'description': item.get('description', ''),
                'counted_total': item.get('counted_total', 0),
                'bp_onhand': item.get('bp_onhand', 0),
                'missing_in_bp': bool(item.get('missing_in_bp', False)),
            }
    session['sc_counts'] = sc_counts
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU', 'Description', 'BP On Hand', 'Counted Total', 'Variance'])
    for item in data:
        sku = item.get('sku', '')
        desc = item.get('description', '')
        bp_on = item.get('bp_onhand', 0)
        counted = item.get('counted_total', 0)
        variance = counted - bp_on
        writer.writerow([sku, desc, bp_on, counted, variance])
    output.seek(0)
    date_str = datetime.now().strftime('%Y%m%d')
    store_name_safe = re.sub(r'[^\w\s-]', '', store_name).strip().replace(' ', '_')
    filename = f'Stock_Check_{store_name_safe}_{date_str}.csv'
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


@app.route('/studio/stock-check/save-counts', methods=['POST'])
@studio_login_required
def studio_stock_check_save_counts():
    """Save current count totals to session so the verify flow can access them."""
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    sc_counts = {}
    for item in data:
        sku = (item.get('sku', '') or '').strip().upper()
        if sku:
            sc_counts[sku] = {
                'description': item.get('description', ''),
                'counted_total': item.get('counted_total', 0),
                'bp_onhand': item.get('bp_onhand', 0),
                'missing_in_bp': bool(item.get('missing_in_bp', False)),
            }
    session['sc_counts'] = sc_counts
    return jsonify({'ok': True})


@app.route('/studio/stock-check/verify')
@studio_login_required
def studio_stock_check_verify():
    sc_counts = session.get('sc_counts')
    if not sc_counts:
        flash('Please complete a stock check before verifying.', 'error')
        return redirect(url_for('studio_stock_check'))
    sku_items = []
    for sku_upper, count_data in sc_counts.items():
        sku_items.append({
            'sku': sku_upper,
            'description': count_data.get('description', ''),
            'counted_total': count_data.get('counted_total', 0),
            'bp_onhand': count_data.get('bp_onhand', 0),
            'missing_in_bp': count_data.get('missing_in_bp', False),
        })
    sku_items.sort(key=lambda x: x['sku'])
    return render_template('stock_check_verify.html', sku_items=sku_items)


@app.route('/studio/stock-check/verify/upload', methods=['POST'])
@studio_login_required
def studio_stock_check_verify_upload():
    f = request.files.get('bp_file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'No file uploaded'}), 400
    try:
        raw_bytes = f.read()
        text = clean_csv_content(raw_bytes)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return jsonify({'ok': False, 'error': 'Could not read file headers'}), 400
        headers = [h.strip().lower() for h in reader.fieldnames]
        reader.fieldnames = headers
        sku_col = None
        qty_col = None
        for h in headers:
            if h == 'sku' and sku_col is None:
                sku_col = h
        for h in headers:
            if ('on hand' in h or 'onhand' in h or 'on-hand' in h) and qty_col is None:
                qty_col = h
        if qty_col is None:
            for h in headers:
                if 'quantity' in h and qty_col is None:
                    qty_col = h
        if sku_col is None:
            return jsonify({'ok': False, 'error': 'No SKU column found in uploaded file'}), 400
        if qty_col is None:
            return jsonify({'ok': False, 'error': 'No on-hand quantity column found. Expected a column containing "on hand" or "quantity".'}), 400
        post_bp = {}
        for row in reader:
            sku = (row.get(sku_col) or '').strip().upper()
            qty_str = (row.get(qty_col) or '').strip()
            if not sku or is_excluded_sku(sku):
                continue
            try:
                qty = int(float(qty_str))
            except (ValueError, TypeError):
                qty = 0
            post_bp[sku] = qty
        session['post_bp_onhand'] = post_bp
        # Build comparison data for JS
        sc_counts = session.get('sc_counts', {})
        comparisons = []
        for sku_upper, count_data in sc_counts.items():
            counted_total = count_data.get('counted_total', 0)
            bp_qty = count_data.get('bp_onhand', 0)
            missing_in_bp = count_data.get('missing_in_bp', False)
            post_qty = post_bp.get(sku_upper)
            missing_in_post = post_qty is None
            comparisons.append({
                'sku': sku_upper,
                'description': count_data.get('description', ''),
                'counted_total': counted_total,
                'bp_onhand': bp_qty,
                'missing_in_bp': missing_in_bp,
                'post_bp_onhand': post_qty if post_qty is not None else 0,
                'missing_in_post': missing_in_post,
            })
        comparisons.sort(key=lambda x: x['sku'])
        return jsonify({'ok': True, 'sku_count': len(post_bp), 'comparisons': comparisons})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/studio/stock-check/verify/submit', methods=['POST'])
@studio_login_required
def studio_stock_check_verify_submit():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data'}), 400
    store_id = session.get('store_id', '')
    store_name = store_id or 'Studio'
    if store_id:
        conn = get_db()
        row = conn.execute('SELECT name FROM stores WHERE store_id = ?', (store_id,)).fetchone()
        conn.close()
        if row:
            store_name = row['name']
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU', 'Description', 'Original Count', 'Original Variance',
                     'Post-Adjustment BP On Hand', 'Verified', 'Reason', 'Notes'])
    for item in data:
        sku = item.get('sku', '')
        desc = item.get('description', '')
        original_count = item.get('counted_total', 0)
        original_variance = item.get('original_variance', '')
        post_bp = item.get('post_bp_onhand', '')
        verified = 'Yes' if item.get('verified') else 'No'
        reason = item.get('reason', '')
        notes = item.get('notes', '')
        writer.writerow([sku, desc, original_count, original_variance, post_bp, verified, reason, notes])
    output.seek(0)
    date_str = datetime.now().strftime('%Y%m%d')
    store_name_safe = re.sub(r'[^\w\s-]', '', store_name).strip().replace(' ', '_')
    filename = f'Stock_Check_Verification_{store_name_safe}_{date_str}.csv'
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


# --- HQ portal ---

@app.route('/hq/login', methods=['GET', 'POST'])
def hq_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['hq_logged_in'] = True
            session['is_admin'] = True
            session['display_name'] = ''
            return redirect(url_for('hq_index'))
        hq_user = get_hq_user(username)
        if hq_user and check_password(hq_user['password_hash'], password):
            session['hq_logged_in'] = True
            session['is_admin'] = True
            session['display_name'] = hq_user['display_name']
            return redirect(url_for('hq_index'))
        flash('Incorrect username or password.', 'error')
    return render_template('hq_login.html')


@app.route('/hq/logout')
def hq_logout():
    session.pop('hq_logged_in', None)
    return redirect(url_for('landing'))


@app.route('/hq/')
@hq_login_required
def hq_index():
    results = run_reconciliation()
    db_stores = get_all_stores_db()
    return render_template('hq_shell.html', data=results, db_stores=db_stores, current_user_name=session.get('display_name', ''))


@app.route('/hq/refresh', methods=['POST'])
@hq_login_required
def hq_refresh():
    results = run_reconciliation()
    return jsonify(results)


# --- SPA section fragment routes ---

@app.route('/hq/section/dashboard')
@hq_login_required
def hq_section_dashboard():
    return redirect(url_for('hq_section_analytics'))


@app.route('/hq/section/analytics')
@hq_login_required
def hq_section_analytics():
    return render_template('fragments/analytics.html')


# --- HQ Analytics data routes (Phase 2) ---

def _validated_range(req):
    """Return a validated range_key from request.args, defaulting to '4w'."""
    r = req.args.get('range', '4w')
    return r if r in ('4w', '12w', 'all') else '4w'


@app.route('/hq/analytics/overview')
@hq_login_required
def hq_analytics_overview():
    data = analytics_begin_count.get_analytics_overview(_validated_range(request))
    return jsonify(data)


@app.route('/hq/analytics/participation')
@hq_login_required
def hq_analytics_participation():
    data = analytics_begin_count.get_analytics_participation(_validated_range(request))
    return jsonify(data)


@app.route('/hq/analytics/leaderboard')
@hq_login_required
def hq_analytics_leaderboard():
    data = analytics_begin_count.get_analytics_leaderboard(_validated_range(request))
    return jsonify(data)


@app.route('/hq/analytics/studio/<store_id>')
@hq_login_required
def hq_analytics_studio(store_id):
    # 404 if the studio doesn't exist
    store = get_store_by_id_db(store_id)
    if not store:
        return jsonify({'ok': False, 'error': 'Studio not found'}), 404
    data = analytics_begin_count.get_studio_analytics(store_id, _validated_range(request))
    return jsonify(data)


@app.route('/hq/section/database')
@hq_login_required
def hq_section_database():
    msf_path = os.path.join(MASTER_DIR, 'SKU_Master.csv')
    msf_rows = 0
    msf_updated = 'N/A'
    if os.path.isfile(msf_path):
        msf_rows = len(load_master_skus())
        msf_updated = datetime.fromtimestamp(os.path.getmtime(msf_path)).strftime('%Y-%m-%d %H:%M:%S')
    image_count = 0
    if os.path.isdir(IMAGES_DIR):
        image_count = len([f for f in os.listdir(IMAGES_DIR) if os.path.isfile(os.path.join(IMAGES_DIR, f))])
    conn = get_archive_db()
    orphaned = [dict(r) for r in conn.execute(
        "SELECT * FROM image_flags WHERE flag_type = 'orphaned_image' AND status = 'unresolved' ORDER BY image_filename"
    ).fetchall()]
    missing = [dict(r) for r in conn.execute(
        "SELECT * FROM image_flags WHERE flag_type = 'missing_image' AND status = 'unresolved' ORDER BY sku"
    ).fetchall()]
    conn.close()
    master = load_master_skus()
    for m in missing:
        m['description'] = master.get(m['sku'], '')
    status_path = os.path.join(MASTER_DIR, 'SKU_Status.csv')
    status_rows = 0
    status_updated = 'N/A'
    if os.path.isfile(status_path):
        status_rows = len(load_sku_status())
        status_updated = datetime.fromtimestamp(os.path.getmtime(status_path)).strftime('%Y-%m-%d %H:%M:%S')
    prices_path = os.path.join(DATABASE_DIR, 'SKU_Prices.csv')
    prices_count = 0
    prices_updated = 'N/A'
    if os.path.isfile(prices_path):
        prices_count = len(load_sku_prices())
        prices_updated = datetime.fromtimestamp(os.path.getmtime(prices_path)).strftime('%Y-%m-%d %H:%M:%S')
    return render_template('fragments/database.html',
                           msf_rows=msf_rows, msf_updated=msf_updated,
                           status_rows=status_rows, status_updated=status_updated,
                           prices_count=prices_count, prices_updated=prices_updated,
                           image_count=image_count, orphaned=orphaned, missing=missing)


@app.route('/hq/section/studios')
@hq_login_required
def hq_section_studios():
    db_stores = get_all_stores_db()
    results = run_reconciliation()
    recon_status = {}
    recon_data = {}
    for s in results.get('stores', []):
        recon_status[s['store_id']] = s['status']
        recon_data[s['store_id']] = {
            'status': s['status'],
            'active_sku_count': s.get('active_sku_count', 0),
            'discrepancy_count': s.get('discrepancy_count', 0),
            'net_discrepancy': s.get('net_discrepancy', 0),
        }
    return render_template('fragments/studios.html', db_stores=db_stores, recon_status=recon_status, recon_data=recon_data)


@app.route('/hq/database/upload-msf', methods=['POST'])
@hq_login_required
def hq_database_upload_msf():
    msf_path = os.path.join(MASTER_DIR, 'SKU_Master.csv')
    f = request.files.get('msf_file')
    if f and f.filename:
        archive_file_if_exists(msf_path, 'master_sku')
        os.makedirs(MASTER_DIR, exist_ok=True)
        f.save(msf_path)
        run_image_sku_audit()
        flash('Master SKU file updated.', 'success')
    return redirect('/hq/?section=database')


@app.route('/hq/database/upload-sku-status', methods=['POST'])
@hq_login_required
def hq_database_upload_sku_status():
    status_path = os.path.join(MASTER_DIR, 'SKU_Status.csv')
    f = request.files.get('status_file')
    if f and f.filename:
        archive_file_if_exists(status_path, 'sku_status')
        os.makedirs(MASTER_DIR, exist_ok=True)
        f.save(status_path)
        count = len(load_sku_status())
        flash(f'SKU Status file updated. {count} SKUs loaded.', 'success')
    return redirect('/hq/?section=database')


@app.route('/hq/database/upload-sku-prices', methods=['POST'])
@hq_login_required
def hq_database_upload_sku_prices():
    prices_path = os.path.join(DATABASE_DIR, 'SKU_Prices.csv')
    f = request.files.get('prices_file')
    if f and f.filename:
        archive_file_if_exists(prices_path, 'sku_prices')
        os.makedirs(DATABASE_DIR, exist_ok=True)
        f.save(prices_path)
        count = len(load_sku_prices())
        flash(f'SKU Prices file updated. {count} SKUs loaded.', 'success')
    return redirect('/hq/?section=database')


@app.route('/hq/database/upload-images', methods=['POST'])
@hq_login_required
def hq_database_upload_images():
    img_files = request.files.getlist('image_files')
    count = 0
    os.makedirs(IMAGES_DIR, exist_ok=True)
    for f in img_files:
        if f.filename:
            f.save(os.path.join(IMAGES_DIR, f.filename))
            count += 1
    if count:
        run_image_sku_audit()
        flash(f'{count} images uploaded.', 'success')
    return redirect('/hq/?section=database')


@app.route('/hq/studios/update-credentials', methods=['POST'])
@hq_login_required
def hq_studios_update_credentials():
    data = request.get_json()
    store_id = data.get('store_id', '')
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if store_id and username:
        conn = get_db()
        conn.execute('UPDATE stores SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?',
                     (username, store_id))
        if password:
            pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn.execute('UPDATE stores SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?',
                         (pw_hash, store_id))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 400


@app.route('/hq/studios/update-store', methods=['POST'])
@hq_login_required
def hq_studios_update_store():
    data = request.get_json()
    store_id = data.get('store_id', '')
    if not store_id:
        return jsonify({'success': False, 'error': 'Missing store_id'}), 400
    manager = data.get('manager', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    username = data.get('username', '').strip()
    new_password = data.get('new_password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    if new_password and new_password != confirm_password:
        return jsonify({'success': False, 'error': 'Passwords do not match'})
    conn = get_db()
    conn.execute('UPDATE stores SET manager = ?, email = ?, phone = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?',
                 (manager, email, phone, store_id))
    if username:
        conn.execute('UPDATE stores SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?',
                     (username, store_id))
    if new_password:
        pw_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn.execute('UPDATE stores SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?',
                     (pw_hash, store_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/hq/studios/add', methods=['POST'])
@hq_login_required
def hq_studios_add():
    """Create a new studio. Validates input, checks uniqueness, inserts into the DB,
    and sets default credentials (username = password = store_id, bcrypt-hashed)."""
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data received'}), 400

    store_id = (data.get('store_id') or '').strip()
    name = (data.get('name') or '').strip()
    region = (data.get('region') or '').strip()

    if not store_id:
        return jsonify({'ok': False, 'error': 'Studio number is required'}), 400
    if not re.match(r'^[0-9]{1,4}$', store_id):
        return jsonify({'ok': False, 'error': 'Studio number must be 1–4 digits (numbers only)'}), 400
    if not name:
        return jsonify({'ok': False, 'error': 'Studio name is required'}), 400
    if len(name) > 100:
        return jsonify({'ok': False, 'error': 'Studio name must be 100 characters or fewer'}), 400
    if region not in VALID_REGIONS:
        return jsonify({'ok': False, 'error': 'Please select a valid region'}), 400

    conn = get_db()
    try:
        existing = conn.execute('SELECT 1 FROM stores WHERE store_id = ?', (store_id,)).fetchone()
        if existing:
            return jsonify({'ok': False, 'error': f'Studio {store_id} already exists in the list'}), 400
        pw_hash = bcrypt.hashpw(store_id.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn.execute(
            "INSERT INTO stores "
            "(store_id, name, timezone, username, password_hash, email, manager, phone, region) "
            "VALUES (?, ?, 'America/New_York', ?, ?, '', '', '', ?)",
            (store_id, name, store_id, pw_hash, region),
        )
        conn.commit()
        return jsonify({'ok': True, 'store_id': store_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/hq/goto-studio')
@hq_login_required
def hq_goto_studio():
    session['studio_logged_in'] = True
    session['is_admin'] = True
    return redirect(url_for('studio_index'))


@app.route('/hq/archive')
@hq_login_required
def hq_archive():
    conn = get_archive_db()
    archives = [dict(r) for r in conn.execute(
        "SELECT id, file_type, original_filename, store_id, archived_at, row_count, file_size_bytes FROM archive_files ORDER BY archived_at DESC LIMIT 50"
    ).fetchall()]
    conn.close()
    return render_template('archive.html', archives=archives)


@app.route('/hq/upload', methods=['GET', 'POST'])
@hq_login_required
def hq_upload():
    if request.method == 'POST':
        files = request.files.getlist('files')
        uploaded = []
        for f in files:
            if f.filename:
                filepath = os.path.join(INPUT_DIR, f.filename)
                file_type, store_id = classify_upload_filename(f.filename)
                if file_type:
                    archive_file_if_exists(filepath, file_type, store_id)
                f.save(filepath)
                uploaded.append(f.filename)
        if uploaded:
            flash(f'Uploaded {len(uploaded)} file(s): {", ".join(uploaded)}', 'success')
        return redirect(url_for('hq_upload'))

    # List current files in /input/
    global_files = []
    variance_files = []
    if os.path.isdir(INPUT_DIR):
        for fname in sorted(os.listdir(INPUT_DIR)):
            fpath = os.path.join(INPUT_DIR, fname)
            if os.path.isfile(fpath):
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                size_kb = os.path.getsize(fpath) / 1024
                finfo = {
                    'name': fname,
                    'modified': mtime.strftime('%Y-%m-%d %H:%M:%S'),
                    'size': f'{size_kb:.1f} KB',
                    'type': 'other',
                }
                if RE_SKU_LIST.match(fname):
                    finfo['type'] = 'sku_list'
                    global_files.append(finfo)
                elif RE_AUDIT_TRAIL.match(fname):
                    finfo['type'] = 'audit_trail'
                    global_files.append(finfo)
                elif RE_VARIANCE.match(fname):
                    finfo['type'] = 'variance'
                    variance_files.append(finfo)
                else:
                    global_files.append(finfo)
    return render_template('upload.html', global_files=global_files, variance_files=variance_files)


def _generate_omnicounts(store_number, bp_file):
    """Shared OmniCounts generation logic.

    Returns (error_message, None) on failure or (None, (bytes_io, filename)) on success.
    """
    scan = scan_input_files()
    if not scan['sku_lists']:
        return ('No weekly SKU list file found in /input/. Upload one before generating.', None)

    sku_list_filename = scan['sku_lists'][0][0]
    weekly_skus = load_sku_list(os.path.join(INPUT_DIR, sku_list_filename))

    raw_bytes = bp_file.read()
    text = clean_csv_content(raw_bytes)
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [h.strip() for h in reader.fieldnames]

    fieldnames = list(reader.fieldnames)

    sku_col = None
    product_id_col = None
    product_name_col = None
    options_col = None
    for h in fieldnames:
        hl = h.lower()
        if hl == 'sku' and sku_col is None:
            sku_col = h
        elif hl == 'product id' and product_id_col is None:
            product_id_col = h
        elif hl == 'product name' and product_name_col is None:
            product_name_col = h
        elif hl == 'options' and options_col is None:
            options_col = h
    if sku_col is None:
        return ('Uploaded CSV has no SKU column.', None)
    text_cols = {sku_col, product_id_col, product_name_col, options_col} - {None}

    matched_rows = []
    seen_skus = set()
    for row in reader:
        out = {}
        for col in fieldnames:
            val = row.get(col)
            out[col] = val.strip() if val else ''
        sku_val = out[sku_col]
        if sku_val and not is_excluded_sku(sku_val) and sku_val in weekly_skus:
            matched_rows.append(out)
            seen_skus.add(sku_val)

    sku_master_desc = {}
    sku_master_path = os.path.join(MASTER_DIR, 'SKU_Master.csv')
    if os.path.isfile(sku_master_path):
        master_rows = parse_csv(sku_master_path)
        for row in master_rows:
            s = row.get('sku', '').strip()
            if s:
                sku_master_desc[s] = row.get('description', '').strip()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in matched_rows:
        writer.writerow(row)
    for sku in sorted(weekly_skus - seen_skus):
        fill_row = {}
        for col in fieldnames:
            if col == sku_col:
                fill_row[col] = sku
            elif col == product_name_col:
                fill_row[col] = sku_master_desc.get(sku, '')
            elif col in text_cols:
                fill_row[col] = ''
            else:
                fill_row[col] = '0'
        writer.writerow(fill_row)

    output.seek(0)
    result_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
    download_name = f'{store_number}_OnHands.csv'
    return (None, (result_bytes, download_name))


@app.route('/hq/generate-omnicounts', methods=['POST'])
@hq_login_required
def hq_generate_omnicounts():
    store_number = request.form.get('store_number', '').strip()
    if not store_number or not store_number.isdigit():
        flash('Store number must be numeric.', 'error')
        return redirect(url_for('hq_upload'))

    bp_file = request.files.get('bp_file')
    if not bp_file or not bp_file.filename:
        flash('Please upload a Brightpearl inventory CSV.', 'error')
        return redirect(url_for('hq_upload'))

    error, result = _generate_omnicounts(store_number, bp_file)
    if error:
        flash(error, 'error')
        return redirect(url_for('hq_upload'))

    result_bytes, download_name = result
    return send_file(result_bytes, mimetype='text/csv', as_attachment=True, download_name=download_name)


@app.route('/hq/delete-file', methods=['POST'])
@hq_login_required
def hq_delete_file():
    filename = request.form.get('filename', '')
    if not filename or '/' in filename or '..' in filename:
        flash('Invalid filename.', 'error')
        return redirect(url_for('hq_upload'))
    filepath = os.path.join(INPUT_DIR, filename)
    if os.path.isfile(filepath):
        os.remove(filepath)
        flash(f'Deleted {filename}.', 'success')
    else:
        flash(f'File not found: {filename}', 'error')
    return redirect(url_for('hq_upload'))


@app.route('/hq/delete-all-files', methods=['POST'])
@hq_login_required
def hq_delete_all_files():
    count = 0
    if os.path.isdir(INPUT_DIR):
        for fname in os.listdir(INPUT_DIR):
            fpath = os.path.join(INPUT_DIR, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                count += 1
    flash(f'Deleted {count} file(s) from /input/.', 'success')
    return redirect(url_for('hq_upload'))


@app.route('/hq/download-file')
@hq_login_required
def hq_download_file():
    filename = request.args.get('filename', '')
    if not filename or '/' in filename or '..' in filename:
        return "Invalid filename", 400
    filepath = os.path.join(INPUT_DIR, filename)
    if os.path.isfile(filepath):
        return send_from_directory(INPUT_DIR, filename, as_attachment=True)
    return "File not found", 404


@app.route('/hq/download-selected', methods=['POST'])
@hq_login_required
def hq_download_selected():
    filenames = request.form.getlist('filenames')
    if not filenames:
        flash('No files selected.', 'error')
        return redirect(url_for('hq_upload'))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in filenames:
            if '/' in fname or '..' in fname:
                continue
            fpath = os.path.join(INPUT_DIR, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, fname)
    buf.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'STUDS_files_{timestamp}.zip')


@app.route('/hq/delete-selected', methods=['POST'])
@hq_login_required
def hq_delete_selected():
    filenames = request.form.getlist('filenames')
    count = 0
    for fname in filenames:
        if '/' in fname or '..' in fname:
            continue
        fpath = os.path.join(INPUT_DIR, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)
            count += 1
    flash(f'Deleted {count} file(s).', 'success')
    return redirect(url_for('hq_upload'))


@app.route('/hq/settings')
@hq_login_required
def hq_settings_page():
    return render_template('settings.html')


@app.route('/hq/settings/credentials', methods=['GET', 'POST'])
@hq_login_required
def hq_settings_credentials():
    if request.method == 'POST':
        cred_updated = False
        conn = get_db()
        for key, val in request.form.items():
            if key.startswith('store_username_'):
                store_id = key.replace('store_username_', '')
                new_username = val.strip()
                if new_username:
                    conn.execute('UPDATE stores SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?',
                                 (new_username, store_id))
                    cred_updated = True
            if key.startswith('store_password_'):
                store_id = key.replace('store_password_', '')
                new_pw = val.strip()
                if new_pw:
                    pw_hash = bcrypt.hashpw(new_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    conn.execute('UPDATE stores SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?',
                                 (pw_hash, store_id))
                    cred_updated = True
        conn.commit()
        conn.close()
        if cred_updated:
            flash('Credentials updated.', 'success')
        else:
            flash('No changes made.', 'success')
        return redirect(url_for('hq_settings_credentials'))
    db_stores = get_all_stores_db()
    return render_template('settings_credentials.html', db_stores=db_stores)


@app.route('/hq/settings/email', methods=['GET', 'POST'])
@hq_login_required
def hq_settings_email():
    settings = load_settings()
    if request.method == 'POST':
        settings['email_body_template'] = request.form.get('email_body_template', DEFAULT_EMAIL_BODY)
        store_emails = {}
        for key, val in request.form.items():
            if key.startswith('store_email_'):
                store_id = key.replace('store_email_', '')
                store_emails[store_id] = val.strip()
        settings['store_emails'] = store_emails
        save_settings(settings)
        flash('Email settings saved.', 'success')
        return redirect(url_for('hq_settings_email'))
    results = run_reconciliation()
    return render_template('settings_email.html', settings=settings, stores=results['stores'])


@app.route('/hq/email-draft/<store_id>')
@hq_login_required
def hq_email_draft(store_id):
    results = run_reconciliation()
    settings = load_settings()

    store = None
    for s in results['stores']:
        if s['store_id'] == store_id:
            store = s
            break

    if not store:
        return "Studio not found", 404

    store_name = store.get('store_name', store_id)
    store_email = settings.get('store_emails', {}).get(store_id, '')

    # Build SKU list
    sku_lines = []
    for d in store.get('sku_details', []):
        sku_lines.append(
            f"- SKU: {d['sku']} | Required Adjustment: {d['quantity']} "
            f"| Actual Adjustment: {d['actual_push']} | Discrepancy: {d['discrepancy']}"
        )
    sku_list = "\n".join(sku_lines) if sku_lines else "(No specific discrepancies)"

    subject = f"{store_name} — Stock Check Discrepancy"
    body = (
        f"Hi {store_name},\n\n"
        "We recently completed an inventory audit based on your most recent stock check "
        "and found discrepancies in the following SKUs at your location. Please review and "
        "adjust these items at your earliest convenience using reason code \"Stock Check\".\n\n"
        f"{sku_list}\n\n"
        "Please email logistics@studs.com to confirm once these have been addressed.\n\n"
        "Cheers,\nLogistics"
    )

    draft = {
        'to': store_email,
        'subject': subject,
        'body': body,
        'store_name': store_name,
    }
    return jsonify(draft)


@app.route('/hq/export')
@hq_login_required
def hq_export_csv():
    results = run_reconciliation()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Store ID', 'Store Name', 'Status', 'SKU', 'Product ID',
        'Required Push', 'Location', 'Item Cost Price',
        'Actual Push', 'Discrepancy'
    ])

    for store in results['stores']:
        if store.get('all_sku_details'):
            for d in store['all_sku_details']:
                writer.writerow([
                    store['store_id'],
                    store.get('store_name', ''),
                    store['status'],
                    d['sku'],
                    d.get('product_id', ''),
                    d['quantity'],
                    d.get('location', ''),
                    d.get('item_cost_price', ''),
                    d['actual_push'],
                    d['discrepancy'],
                ])
        else:
            writer.writerow([
                store['store_id'],
                store.get('store_name', ''),
                store['status'],
                '', '', '', '', '', '', '',
            ])

    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'STUDS_Dashboard_Export_{timestamp}.csv',
    )


@app.route('/hq/database', methods=['GET', 'POST'])
@hq_login_required
def hq_database():
    msf_path = os.path.join(MASTER_DIR, 'SKU_Master.csv')
    diff_added = []
    diff_removed = []

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'upload_msf':
            f = request.files.get('msf_file')
            if f and f.filename:
                # Archive old MSF
                archive_file_if_exists(msf_path, 'master_sku')
                # Read old SKUs for diff
                old_skus = set(load_master_skus().keys())
                # Save new file
                os.makedirs(MASTER_DIR, exist_ok=True)
                f.save(msf_path)
                # Diff
                new_skus = set(load_master_skus().keys())
                diff_added = sorted(new_skus - old_skus)
                diff_removed = sorted(old_skus - new_skus)
                # Run audit
                run_image_sku_audit()
                flash(f'Master SKU file updated. {len(diff_added)} SKUs added, {len(diff_removed)} SKUs removed.', 'success')

        elif action == 'upload_sku_status':
            f = request.files.get('status_file')
            if f and f.filename:
                status_path = os.path.join(MASTER_DIR, 'SKU_Status.csv')
                archive_file_if_exists(status_path, 'sku_status')
                os.makedirs(MASTER_DIR, exist_ok=True)
                f.save(status_path)
                count = len(load_sku_status())
                flash(f'SKU Status file updated. {count} SKUs loaded.', 'success')

        elif action == 'upload_sku_prices':
            f = request.files.get('prices_file')
            if f and f.filename:
                prices_path = os.path.join(DATABASE_DIR, 'SKU_Prices.csv')
                archive_file_if_exists(prices_path, 'sku_prices')
                os.makedirs(DATABASE_DIR, exist_ok=True)
                f.save(prices_path)
                count = len(load_sku_prices())
                flash(f'SKU Prices file updated. {count} SKUs loaded.', 'success')

        elif action == 'upload_images':
            img_files = request.files.getlist('image_files')
            count = 0
            os.makedirs(IMAGES_DIR, exist_ok=True)
            for f in img_files:
                if f.filename:
                    f.save(os.path.join(IMAGES_DIR, f.filename))
                    count += 1
            if count:
                run_image_sku_audit()
                flash(f'{count} images uploaded.', 'success')

        return redirect(url_for('hq_database'))

    # MSF status
    msf_rows = 0
    msf_updated = 'N/A'
    if os.path.isfile(msf_path):
        msf_rows = len(load_master_skus())
        msf_updated = datetime.fromtimestamp(os.path.getmtime(msf_path)).strftime('%Y-%m-%d %H:%M:%S')

    # Image count
    image_count = 0
    if os.path.isdir(IMAGES_DIR):
        image_count = len([f for f in os.listdir(IMAGES_DIR) if os.path.isfile(os.path.join(IMAGES_DIR, f))])

    # Audit flags
    conn = get_archive_db()
    orphaned = [dict(r) for r in conn.execute(
        "SELECT * FROM image_flags WHERE flag_type = 'orphaned_image' AND status = 'unresolved' ORDER BY image_filename"
    ).fetchall()]
    missing = [dict(r) for r in conn.execute(
        "SELECT * FROM image_flags WHERE flag_type = 'missing_image' AND status = 'unresolved' ORDER BY sku"
    ).fetchall()]

    # Add descriptions for missing images
    master = load_master_skus()
    for m in missing:
        m['description'] = master.get(m['sku'], '')

    # SKU Status file
    status_path = os.path.join(MASTER_DIR, 'SKU_Status.csv')
    status_rows = 0
    status_updated = 'N/A'
    if os.path.isfile(status_path):
        status_rows = len(load_sku_status())
        status_updated = datetime.fromtimestamp(os.path.getmtime(status_path)).strftime('%Y-%m-%d %H:%M:%S')

    # SKU Prices file
    prices_path = os.path.join(DATABASE_DIR, 'SKU_Prices.csv')
    prices_count = 0
    prices_updated = 'N/A'
    if os.path.isfile(prices_path):
        prices_count = len(load_sku_prices())
        prices_updated = datetime.fromtimestamp(os.path.getmtime(prices_path)).strftime('%Y-%m-%d %H:%M:%S')

    # Archive browser
    archives = [dict(r) for r in conn.execute(
        "SELECT id, file_type, original_filename, store_id, archived_at, row_count, file_size_bytes FROM archive_files ORDER BY archived_at DESC LIMIT 50"
    ).fetchall()]
    conn.close()

    return render_template('database.html',
                           msf_rows=msf_rows, msf_updated=msf_updated,
                           status_rows=status_rows, status_updated=status_updated,
                           prices_count=prices_count, prices_updated=prices_updated,
                           image_count=image_count,
                           orphaned=orphaned, missing=missing,
                           archives=archives,
                           diff_added=diff_added, diff_removed=diff_removed)


@app.route('/hq/database/assign-image', methods=['POST'])
@hq_login_required
def hq_assign_image():
    image_filename = request.form.get('image_filename', '')
    sku = request.form.get('sku', '').strip()
    if image_filename and sku and os.path.isdir(IMAGES_DIR):
        old_path = os.path.join(IMAGES_DIR, image_filename)
        if os.path.isfile(old_path):
            ext = os.path.splitext(image_filename)[1]
            new_filename = sku + ext
            new_path = os.path.join(IMAGES_DIR, new_filename)
            os.rename(old_path, new_path)
            conn = get_archive_db()
            conn.execute("UPDATE image_flags SET status = 'assigned', sku = ?, resolved_at = CURRENT_TIMESTAMP WHERE image_filename = ?",
                         (sku, image_filename))
            conn.commit()
            conn.close()
            run_image_sku_audit()
            flash(f'Image renamed to {new_filename} and assigned to {sku}.', 'success')
    return redirect(url_for('hq_database'))


@app.route('/hq/database/mark-discontinued', methods=['POST'])
@hq_login_required
def hq_mark_discontinued():
    image_filename = request.form.get('image_filename', '')
    if image_filename:
        conn = get_archive_db()
        conn.execute("UPDATE image_flags SET status = 'discontinued', resolved_at = CURRENT_TIMESTAMP WHERE image_filename = ?",
                     (image_filename,))
        conn.commit()
        conn.close()
        flash(f'Flagged as discontinued: {image_filename}', 'success')
    return redirect(url_for('hq_database'))


init_store_db()
init_archive_db()


@app.context_processor
def inject_globals():
    return {
        'current_user_name': session.get('display_name', ''),
        'last_loaded_global': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'studio_week_number': datetime.now().isocalendar()[1],
    }


if __name__ == '__main__':
    print(f"[STUDS Stock Check] Input directory: {INPUT_DIR}")
    print(f"[STUDS Stock Check] Database directory: {DATABASE_DIR}")
    print(f"[STUDS Stock Check] Starting on http://localhost:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
