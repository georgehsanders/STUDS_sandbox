"""Master Zebra Templates blueprint.

HQ uploads the 5 master Zebra data files into 5 fixed slots; full version
history is preserved per slot. Stores hit a single endpoint that returns a
ZIP with the latest version of each slot, named with the canonical filenames
the Zebra portal templates are configured to match.

Self-contained — owns its own routes, templates, DB schema initialiser, and
storage layout. The only external touch points are:
  - app.py registers the blueprint and calls init_master_templates_db()
  - templates/hq_base.html links to /hq/master-templates in the right_nav
  - help/templates/help/tutorial.html links Step 2.a to the studio ZIP
"""

import io
import os
import sqlite3
import zipfile
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, send_file, session, url_for,
)


# --- Canonical slot definitions -------------------------------------------
# These filenames MUST match what the Zebra portal templates reference. HQ
# can upload any local filename; the system always serves these names.
CANONICAL_SLOTS = {
    1: "1 Bin Labels - Fashion.csv",
    2: "2 Bin Labels - Piercing.xlsx",
    3: "3 Bin Labels - Newness.xlsx",
    4: "4 SKU Labels - Fashion.xlsx",
    5: "5 SKU Labels - Piercing.xlsx",
}
SLOT_NUMBERS = sorted(CANONICAL_SLOTS.keys())

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


# --- Storage paths --------------------------------------------------------
# Mirror app.py's STUDS_DATA_DIR pattern so the storage folder can live on a
# mounted volume in production-style deploys.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
_DATA_DIR = os.environ.get('STUDS_DATA_DIR', '').strip()

STORAGE_DIR = (
    os.path.join(_DATA_DIR, 'master_templates_storage')
    if _DATA_DIR
    else os.path.join(_REPO_ROOT, 'master_templates_storage')
)

# Use the same SQLite database the rest of the app uses for store/HQ data.
DATABASE_DIR = (
    os.path.join(_DATA_DIR, 'database')
    if _DATA_DIR
    else os.path.join(_REPO_ROOT, 'database')
)
STORE_DB = os.path.join(DATABASE_DIR, 'store_profiles.db')


# --- Auth decorators ------------------------------------------------------
# Mirror the session-check semantics from app.py without importing from it
# (avoids the circular-import risk a blueprint module hits during registration).
def _hq_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('hq_logged_in'):
            return redirect(url_for('hq_login'))
        return view(*args, **kwargs)
    return wrapped


def _studio_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('studio_logged_in'):
            return redirect(url_for('studio_login'))
        return view(*args, **kwargs)
    return wrapped


# --- Database -------------------------------------------------------------
def _db():
    conn = sqlite3.connect(STORE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_master_templates_db():
    """Create the master_template_versions table on app startup. Idempotent."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(STORAGE_DIR, exist_ok=True)
    conn = _db()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS master_template_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_number INTEGER NOT NULL,
                uploaded_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                notes TEXT
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_mtv_slot
            ON master_template_versions(slot_number)
        ''')
        conn.commit()
    finally:
        conn.close()


def _latest_version_per_slot():
    """Return a dict {slot_number: row or None} for all 5 slots."""
    conn = _db()
    try:
        rows = conn.execute('''
            SELECT v.*
            FROM master_template_versions v
            JOIN (
                SELECT slot_number, MAX(id) AS max_id
                FROM master_template_versions
                GROUP BY slot_number
            ) latest ON latest.slot_number = v.slot_number AND latest.max_id = v.id
        ''').fetchall()
    finally:
        conn.close()
    by_slot = {n: None for n in SLOT_NUMBERS}
    for r in rows:
        by_slot[r['slot_number']] = dict(r)
    return by_slot


def _versions_for_slot(slot_number):
    conn = _db()
    try:
        rows = conn.execute(
            'SELECT * FROM master_template_versions WHERE slot_number = ? ORDER BY id DESC',
            (slot_number,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _get_version(version_id):
    conn = _db()
    try:
        r = conn.execute(
            'SELECT * FROM master_template_versions WHERE id = ?',
            (version_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(r) if r else None


def _format_size(n):
    if n is None:
        return '—'
    if n < 1024:
        return f'{n} B'
    if n < 1024 * 1024:
        return f'{n / 1024:.1f} KB'
    return f'{n / (1024 * 1024):.2f} MB'


def _format_ts(iso_ts):
    if not iso_ts:
        return '— never uploaded —'
    try:
        dt = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except (ValueError, AttributeError):
        return iso_ts


# --- Blueprint ------------------------------------------------------------
master_templates_bp = Blueprint(
    'master_templates',
    __name__,
    template_folder='templates',
)


# --- HQ admin index -------------------------------------------------------
@master_templates_bp.route('/hq/master-templates')
@_hq_login_required
def hq_index():
    latest = _latest_version_per_slot()
    rows = []
    for n in SLOT_NUMBERS:
        v = latest[n]
        rows.append({
            'slot': n,
            'canonical': CANONICAL_SLOTS[n],
            'has_version': v is not None,
            'uploaded_filename': v['uploaded_filename'] if v else '',
            'uploaded_at': _format_ts(v['uploaded_at']) if v else '— never uploaded —',
            'size': _format_size(v['file_size']) if v else '—',
            'version_count': _slot_version_count(n),
            'latest_id': v['id'] if v else None,
        })
    return render_template(
        'master_templates/index.html',
        rows=rows,
        slot_numbers=SLOT_NUMBERS,
        canonical_slots=CANONICAL_SLOTS,
        max_upload_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
        studio_zip_url=url_for('master_templates.studio_zip', _external=False),
    )


def _slot_version_count(slot_number):
    conn = _db()
    try:
        r = conn.execute(
            'SELECT COUNT(*) AS c FROM master_template_versions WHERE slot_number = ?',
            (slot_number,),
        ).fetchone()
    finally:
        conn.close()
    return r['c'] if r else 0


# --- HQ upload handler ----------------------------------------------------
@master_templates_bp.route('/hq/master-templates/upload', methods=['POST'])
@_hq_login_required
def hq_upload():
    try:
        slot_number = int(request.form.get('slot_number', '0'))
    except (TypeError, ValueError):
        flash('Invalid slot number.', 'error')
        return redirect(url_for('master_templates.hq_index'))

    if slot_number not in CANONICAL_SLOTS:
        flash(f'Invalid slot number: {slot_number}. Must be 1-5.', 'error')
        return redirect(url_for('master_templates.hq_index'))

    f = request.files.get('file')
    if not f or not f.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('master_templates.hq_index'))

    # Read the upload into memory so we know its real size before committing.
    blob = f.read()
    if not blob:
        flash('Uploaded file is empty.', 'error')
        return redirect(url_for('master_templates.hq_index'))
    if len(blob) > MAX_UPLOAD_BYTES:
        flash(
            f'File is too large ({_format_size(len(blob))}). '
            f'Max allowed: {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.',
            'error',
        )
        return redirect(url_for('master_templates.hq_index'))

    notes = (request.form.get('notes') or '').strip() or None
    uploaded_filename = f.filename
    canonical = CANONICAL_SLOTS[slot_number]
    now_iso = datetime.now(timezone.utc).isoformat(timespec='seconds')

    # Non-blocking extension warning.
    canonical_ext = os.path.splitext(canonical)[1].lower()
    upload_ext = os.path.splitext(uploaded_filename)[1].lower()
    extension_warning = None
    if canonical_ext and upload_ext and canonical_ext != upload_ext:
        extension_warning = (
            f'Heads up — slot {slot_number} normally holds a {canonical_ext} '
            f'file but you uploaded a {upload_ext}. Stored anyway and will be '
            f'served to stores as "{canonical}".'
        )

    # Insert DB row first so we get the autoincrement id; then write file
    # named with that id. If the file write fails, delete the DB row to keep
    # DB and filesystem in sync.
    conn = _db()
    try:
        cur = conn.execute(
            '''INSERT INTO master_template_versions
               (slot_number, uploaded_filename, file_path, file_size, uploaded_at, notes)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (slot_number, uploaded_filename, '', len(blob), now_iso, notes),
        )
        version_id = cur.lastrowid
        rel_path = _build_storage_path(slot_number, version_id, canonical)
        abs_path = os.path.join(STORAGE_DIR, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        try:
            with open(abs_path, 'wb') as out:
                out.write(blob)
        except OSError as e:
            conn.execute('DELETE FROM master_template_versions WHERE id = ?', (version_id,))
            conn.commit()
            flash(f'Failed to save uploaded file: {e}', 'error')
            return redirect(url_for('master_templates.hq_index'))

        conn.execute(
            'UPDATE master_template_versions SET file_path = ? WHERE id = ?',
            (rel_path, version_id),
        )
        conn.commit()
    finally:
        conn.close()

    if extension_warning:
        flash(extension_warning, 'warning')
    flash(
        f'Slot {slot_number} updated — "{canonical}" now points to the new '
        f'version uploaded at {_format_ts(now_iso)}.',
        'success',
    )
    return redirect(url_for('master_templates.hq_index'))


def _build_storage_path(slot_number, version_id, canonical_filename):
    """Return the relative path under STORAGE_DIR for a given version."""
    return os.path.join(
        f'slot_{slot_number}',
        f'{version_id:04d}__{canonical_filename}',
    )


# --- HQ history view ------------------------------------------------------
@master_templates_bp.route('/hq/master-templates/slot/<int:slot_number>/history')
@_hq_login_required
def hq_slot_history(slot_number):
    if slot_number not in CANONICAL_SLOTS:
        abort(404)
    versions = _versions_for_slot(slot_number)
    return render_template(
        'master_templates/history.html',
        slot_number=slot_number,
        canonical_filename=CANONICAL_SLOTS[slot_number],
        versions=[
            {
                **v,
                'size': _format_size(v['file_size']),
                'uploaded_at': _format_ts(v['uploaded_at']),
            }
            for v in versions
        ],
    )


# --- HQ download (latest or specific version) -----------------------------
@master_templates_bp.route('/hq/master-templates/slot/<int:slot_number>/download')
@_hq_login_required
def hq_download_latest(slot_number):
    if slot_number not in CANONICAL_SLOTS:
        abort(404)
    latest = _latest_version_per_slot().get(slot_number)
    if not latest:
        abort(404)
    return _send_canonical(latest)


@master_templates_bp.route('/hq/master-templates/version/<int:version_id>/download')
@_hq_login_required
def hq_download_version(version_id):
    v = _get_version(version_id)
    if not v:
        abort(404)
    return _send_canonical(v)


def _send_canonical(version_row):
    abs_path = os.path.join(STORAGE_DIR, version_row['file_path'])
    if not os.path.isfile(abs_path):
        abort(404)
    canonical = CANONICAL_SLOTS[version_row['slot_number']]
    return send_file(
        abs_path,
        as_attachment=True,
        download_name=canonical,
    )


# --- Studio ZIP endpoint --------------------------------------------------
@master_templates_bp.route('/studio/master-templates.zip')
@_studio_login_required
def studio_zip():
    latest = _latest_version_per_slot()
    present = [n for n in SLOT_NUMBERS if latest[n] is not None]
    missing = [n for n in SLOT_NUMBERS if latest[n] is None]

    if not present:
        return (
            'No master templates have been uploaded by HQ yet. '
            'Please contact your manager.',
            404,
            {'Content-Type': 'text/plain; charset=utf-8'},
        )

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for n in present:
            v = latest[n]
            abs_path = os.path.join(STORAGE_DIR, v['file_path'])
            if not os.path.isfile(abs_path):
                continue  # storage drift; skip rather than 500
            with open(abs_path, 'rb') as fh:
                zf.writestr(CANONICAL_SLOTS[n], fh.read())

        readme_lines = [
            f'STUDS Master Templates — Downloaded {today}',
            '',
            'Included files:',
        ]
        for n in present:
            readme_lines.append(f'  - {CANONICAL_SLOTS[n]}')
        if missing:
            readme_lines.append('')
            readme_lines.append('MISSING (HQ has not uploaded these yet):')
            for n in missing:
                readme_lines.append(f'  - {CANONICAL_SLOTS[n]}')
            readme_lines.append('')
            readme_lines.append(
                'Ask HQ to upload the missing slot(s) and re-download this ZIP.'
            )
        else:
            readme_lines.append('')
            readme_lines.append('All 5 slots present.')
        zf.writestr('README.txt', '\n'.join(readme_lines) + '\n')

    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'STUDS_zebra_templates_{today}.zip',
    )
