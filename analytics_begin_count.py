"""
analytics_begin_count.py — Phase 2 HQ Analytics backend helpers.

Queries stock_checks and stock_check_skus tables in store_profiles.db to produce
the data for the three-tab Analytics UI (Overview, Participation, Leaderboard) plus
per-studio drill-downs.

All helpers:
- Accept range_key ("4w" | "12w" | "all") and apply a started_at cutoff.
- Treat as "abandoned" any row where status = 'abandoned' OR
  (status = 'in_progress' AND started_at < now - 3 days). Query-time only —
  we never write back to the DB.
- Gracefully handle a missing table or empty result set.
- Never crash; always return a predictable shape.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# DB helper — mirrors get_db() in app.py without importing app (circular-import risk)
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.environ.get('STUDS_DATA_DIR', '').strip()
_DATABASE_DIR = os.path.join(_DATA_DIR, 'database') if _DATA_DIR else os.path.join(_REPO_ROOT, 'database')
_STORE_DB = os.path.join(_DATABASE_DIR, 'store_profiles.db')


def _get_db():
    """Open a connection to store_profiles.db with Row factory."""
    conn = sqlite3.connect(_STORE_DB)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Duration formatter — mirrors format_duration() in app.py
# ---------------------------------------------------------------------------

def _format_duration(seconds):
    """Format elapsed seconds as a compact human-readable string."""
    if seconds is None:
        return '\u2014'
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return '\u2014'
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return '<1m'
    if seconds < 3600:
        return '{}m'.format(seconds // 60)
    return '{}h {}m'.format(seconds // 3600, (seconds % 3600) // 60)


# ---------------------------------------------------------------------------
# Range helpers
# ---------------------------------------------------------------------------

_VALID_RANGES = {'4w', '12w', 'all'}


def _range_cutoff(range_key):
    """Return a UTC datetime cutoff for the range, or None for 'all'."""
    now = datetime.now(timezone.utc)
    if range_key == '4w':
        return now - timedelta(weeks=4)
    if range_key == '12w':
        return now - timedelta(weeks=12)
    return None  # 'all'


def _abandoned_cutoff():
    """Timestamp 3 days ago — used to classify stale in-progress rows."""
    return datetime.now(timezone.utc) - timedelta(days=3)


def _effective_status(status, started_at_str):
    """
    Return the effective status, promoting old in-progress rows to 'abandoned'.
    status  : value from stock_checks.status column
    started_at_str : ISO timestamp string from DB
    """
    if status == 'completed':
        return 'completed'
    if status == 'abandoned':
        return 'abandoned'
    # in_progress — check age
    if status == 'in_progress':
        try:
            started = datetime.fromisoformat(started_at_str)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started < _abandoned_cutoff():
                return 'abandoned'
        except Exception:
            pass
        return 'in_progress'
    return status  # unexpected value — pass through


def _tables_exist(conn):
    """Return True if both analytics tables exist."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name IN ('stock_checks', 'stock_check_skus')"
    ).fetchone()
    return row[0] == 2


# ---------------------------------------------------------------------------
# Helper 1: get_analytics_overview
# ---------------------------------------------------------------------------

def get_analytics_overview(range_key):
    """
    Returns network-level overview stats.

    Shape:
    {
      "empty": bool,
      "this_week": {
        "week_identifier": str | None,
        "completed_count": int,
        "total_studios": int,
        "pct_completed": float
      },
      "stats": {
        "avg_completion_time_seconds": int | None,
        "total_variances_found": int,
        "total_variances_reconciled": int,
        "total_variances_still_off": int
      },
      "trend": [
        {"week_identifier": str, "avg_variances_found": float, "avg_variances_still_off": float},
        ...
      ]
    }
    """
    if range_key not in _VALID_RANGES:
        range_key = '4w'

    _empty = {
        'empty': True,
        'this_week': {'week_identifier': None, 'completed_count': 0, 'total_studios': 0, 'pct_completed': 0.0},
        'stats': {'avg_completion_time_seconds': None, 'total_variances_found': 0,
                  'total_variances_reconciled': 0, 'total_variances_still_off': 0},
        'trend': [],
    }

    try:
        conn = _get_db()
        try:
            if not _tables_exist(conn):
                return _empty

            cutoff = _range_cutoff(range_key)

            # Total studios from stores table
            total_studios = conn.execute('SELECT COUNT(*) FROM stores').fetchone()[0]

            # Fetch all completed runs in the range
            if cutoff:
                cutoff_str = cutoff.isoformat()
                rows = conn.execute(
                    "SELECT store_id, week_identifier, duration_seconds, "
                    "total_variances, variances_reconciled, variances_still_off "
                    "FROM stock_checks "
                    "WHERE status = 'completed' AND started_at >= ?",
                    (cutoff_str,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT store_id, week_identifier, duration_seconds, "
                    "total_variances, variances_reconciled, variances_still_off "
                    "FROM stock_checks WHERE status = 'completed'"
                ).fetchall()

            if not rows:
                _empty['this_week']['total_studios'] = total_studios
                return _empty

            rows = [dict(r) for r in rows]

            # Most recent week_identifier among completed runs
            week_ids = sorted(
                {r['week_identifier'] for r in rows if r['week_identifier']},
                reverse=True
            )
            this_week_id = week_ids[0] if week_ids else None

            # this_week stats
            if this_week_id:
                this_week_stores = {r['store_id'] for r in rows if r['week_identifier'] == this_week_id}
                completed_count = len(this_week_stores)
            else:
                completed_count = 0

            pct = round(completed_count / total_studios, 4) if total_studios else 0.0

            # Aggregate stats over the full range
            durations = [r['duration_seconds'] for r in rows if r['duration_seconds'] is not None]
            avg_time = int(sum(durations) / len(durations)) if durations else None
            total_found = sum(r['total_variances'] or 0 for r in rows)
            total_reconciled = sum(r['variances_reconciled'] or 0 for r in rows)
            total_still_off = sum(r['variances_still_off'] or 0 for r in rows)

            # Trend: per-week aggregates, ascending order
            weeks_data = {}
            for r in rows:
                wk = r['week_identifier']
                if not wk:
                    continue
                if wk not in weeks_data:
                    weeks_data[wk] = {'found': [], 'still_off': []}
                if r['total_variances'] is not None:
                    weeks_data[wk]['found'].append(r['total_variances'])
                if r['variances_still_off'] is not None:
                    weeks_data[wk]['still_off'].append(r['variances_still_off'])

            trend = []
            for wk in sorted(weeks_data.keys()):
                d = weeks_data[wk]
                avg_found = round(sum(d['found']) / len(d['found']), 2) if d['found'] else 0.0
                avg_off = round(sum(d['still_off']) / len(d['still_off']), 2) if d['still_off'] else 0.0
                trend.append({'week_identifier': wk, 'avg_variances_found': avg_found, 'avg_variances_still_off': avg_off})

            return {
                'empty': False,
                'this_week': {
                    'week_identifier': this_week_id,
                    'completed_count': completed_count,
                    'total_studios': total_studios,
                    'pct_completed': pct,
                },
                'stats': {
                    'avg_completion_time_seconds': avg_time,
                    'total_variances_found': total_found,
                    'total_variances_reconciled': total_reconciled,
                    'total_variances_still_off': total_still_off,
                },
                'trend': trend,
            }
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] get_analytics_overview failed: {exc}', file=sys.stderr)
        return _empty


# ---------------------------------------------------------------------------
# Helper 2: get_analytics_participation
# ---------------------------------------------------------------------------

def get_analytics_participation(range_key):
    """
    Returns one row per studio with participation status for this week and
    the last 4 weeks.

    Shape:
    {
      "empty": bool,
      "rows": [
        {
          "store_id": str,
          "name": str,
          "region": str,
          "this_week_status": "completed" | "abandoned" | "in_progress" | "didnt_start",
          "last_4_weeks_status": [str, str, str, str],  # oldest → newest
          "runs_in_range": int
        },
        ...
      ]
    }
    """
    if range_key not in _VALID_RANGES:
        range_key = '4w'

    _empty = {'empty': True, 'rows': []}

    try:
        conn = _get_db()
        try:
            if not _tables_exist(conn):
                return _empty

            cutoff = _range_cutoff(range_key)

            # Load all studios
            stores = [dict(r) for r in conn.execute(
                'SELECT store_id, name, region FROM stores ORDER BY store_id'
            ).fetchall()]

            # Fetch ALL runs (no range filter) for week-based status logic
            all_runs = [dict(r) for r in conn.execute(
                "SELECT store_id, week_identifier, status, started_at "
                "FROM stock_checks"
            ).fetchall()]

            if not all_runs:
                # Tables exist but empty
                rows = []
                for s in stores:
                    rows.append({
                        'store_id': s['store_id'],
                        'name': s['name'],
                        'region': s['region'] or '',
                        'this_week_status': 'didnt_start',
                        'last_4_weeks_status': ['didnt_start', 'didnt_start', 'didnt_start', 'didnt_start'],
                        'runs_in_range': 0,
                    })
                return {'empty': True, 'rows': rows}

            # Find the 4 most recent week_identifiers across all completed runs
            completed_week_ids = sorted(
                {r['week_identifier'] for r in all_runs
                 if r['week_identifier'] and r['status'] == 'completed'},
                reverse=True
            )
            last_4_weeks = list(reversed(completed_week_ids[:4]))  # oldest → newest
            this_week_id = last_4_weeks[-1] if last_4_weeks else None

            def _studio_week_status(store_id, week_id):
                """Determine a studio's status for a specific week_identifier."""
                if not week_id:
                    return 'didnt_start'
                studio_runs = [r for r in all_runs
                               if r['store_id'] == store_id and r['week_identifier'] == week_id]
                if not studio_runs:
                    return 'didnt_start'
                # Determine effective status for each run
                eff = [_effective_status(r['status'], r['started_at']) for r in studio_runs]
                if 'completed' in eff:
                    return 'completed'
                if 'abandoned' in eff:
                    return 'abandoned'
                return 'in_progress'

            # Count runs in range per studio
            if cutoff:
                cutoff_str = cutoff.isoformat()
                range_runs = [r for r in all_runs if r['started_at'] >= cutoff_str]
            else:
                range_runs = all_runs

            runs_in_range_by_store = {}
            for r in range_runs:
                runs_in_range_by_store[r['store_id']] = runs_in_range_by_store.get(r['store_id'], 0) + 1

            rows = []
            for s in stores:
                sid = s['store_id']
                this_status = _studio_week_status(sid, this_week_id)
                l4 = [_studio_week_status(sid, wk) for wk in last_4_weeks]
                # Pad to exactly 4 if fewer than 4 weeks of history exist
                while len(l4) < 4:
                    l4.insert(0, 'didnt_start')

                rows.append({
                    'store_id': sid,
                    'name': s['name'],
                    'region': s['region'] or '',
                    'this_week_status': this_status,
                    'last_4_weeks_status': l4,
                    'runs_in_range': runs_in_range_by_store.get(sid, 0),
                })

            return {'empty': False, 'rows': rows}
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] get_analytics_participation failed: {exc}', file=sys.stderr)
        return _empty


# ---------------------------------------------------------------------------
# Helper 3: get_analytics_leaderboard
# ---------------------------------------------------------------------------

# Composite score weights — tune here without a schema change
SCORE_WEIGHT_COMPLETION    = 0.40
SCORE_WEIGHT_ADJUSTMENT    = 0.35
SCORE_WEIGHT_FOLLOW_THROUGH = 0.25


def get_analytics_leaderboard(range_key):
    """
    Returns ranked leaderboard across all studios.

    Shape:
    {
      "empty": bool,
      "rows": [
        {
          "rank": int,
          "store_id": str,
          "name": str,
          "region": str,
          "score": int,
          "completion_rate": {"completed": int, "total_weeks": int, "pct": float},
          "follow_through_rate": {"completed": int, "started": int, "pct": float},
          "adjustment_success_rate": {"reconciled": int, "total_variances": int, "pct": float}
        },
        ...
      ]
    }
    """
    if range_key not in _VALID_RANGES:
        range_key = '4w'

    _empty = {'empty': True, 'rows': []}

    try:
        conn = _get_db()
        try:
            if not _tables_exist(conn):
                return _empty

            cutoff = _range_cutoff(range_key)

            # Load all studios
            stores = [dict(r) for r in conn.execute(
                'SELECT store_id, name, region FROM stores ORDER BY store_id'
            ).fetchall()]

            # Fetch all runs in the range
            if cutoff:
                cutoff_str = cutoff.isoformat()
                runs = [dict(r) for r in conn.execute(
                    "SELECT store_id, week_identifier, status, started_at, "
                    "variances_reconciled, variances_still_off "
                    "FROM stock_checks WHERE started_at >= ?",
                    (cutoff_str,)
                ).fetchall()]
            else:
                runs = [dict(r) for r in conn.execute(
                    "SELECT store_id, week_identifier, status, started_at, "
                    "variances_reconciled, variances_still_off "
                    "FROM stock_checks"
                ).fetchall()]

            if not runs:
                rows = []
                for s in stores:
                    rows.append({
                        'rank': 0,
                        'store_id': s['store_id'],
                        'name': s['name'],
                        'region': s['region'] or '',
                        'score': 0,
                        'completion_rate': {'completed': 0, 'total_weeks': 0, 'pct': 0.0},
                        'follow_through_rate': {'completed': 0, 'started': 0, 'pct': 0.0},
                        'adjustment_success_rate': {'reconciled': 0, 'total_variances': 0, 'pct': 0.0},
                    })
                # Assign rank (all tied at 0 — rank by store_id)
                for i, r in enumerate(rows, 1):
                    r['rank'] = i
                return {'empty': True, 'rows': rows}

            # All weeks present in this range
            total_weeks_in_range = len({r['week_identifier'] for r in runs if r['week_identifier']})

            # Index runs by store
            by_store = {}
            for r in runs:
                by_store.setdefault(r['store_id'], []).append(r)

            scored = []
            for s in stores:
                sid = s['store_id']
                store_runs = by_store.get(sid, [])

                # Apply effective status
                for r in store_runs:
                    r['_eff_status'] = _effective_status(r['status'], r['started_at'])

                completed_runs = [r for r in store_runs if r['_eff_status'] == 'completed']

                # completion_rate: distinct weeks with a completed run / total weeks in range
                completed_weeks = len({r['week_identifier'] for r in completed_runs if r['week_identifier']})
                completion_pct = completed_weeks / total_weeks_in_range if total_weeks_in_range else 0.0

                # follow_through_rate: completed runs / all started runs
                started = len(store_runs)
                follow_through_pct = len(completed_runs) / started if started else 0.0

                # adjustment_success_rate: variances_reconciled / (reconciled + still_off)
                total_rec = sum(r['variances_reconciled'] or 0 for r in completed_runs)
                total_still = sum(r['variances_still_off'] or 0 for r in completed_runs)
                denom = total_rec + total_still
                adjustment_pct = total_rec / denom if denom else 0.0

                score = int(round(
                    completion_pct    * SCORE_WEIGHT_COMPLETION +
                    adjustment_pct    * SCORE_WEIGHT_ADJUSTMENT +
                    follow_through_pct * SCORE_WEIGHT_FOLLOW_THROUGH
                ) * 100)

                scored.append({
                    'store_id': sid,
                    'name': s['name'],
                    'region': s['region'] or '',
                    'score': score,
                    '_completion_pct': completion_pct,
                    'completion_rate': {'completed': completed_weeks, 'total_weeks': total_weeks_in_range, 'pct': round(completion_pct, 4)},
                    'follow_through_rate': {'completed': len(completed_runs), 'started': started, 'pct': round(follow_through_pct, 4)},
                    'adjustment_success_rate': {'reconciled': total_rec, 'total_variances': denom, 'pct': round(adjustment_pct, 4)},
                })

            # Sort: score desc, completion_pct desc, store_id asc
            scored.sort(key=lambda x: (-x['score'], -x['_completion_pct'], x['store_id']))

            rows = []
            for i, s in enumerate(scored, 1):
                rows.append({
                    'rank': i,
                    'store_id': s['store_id'],
                    'name': s['name'],
                    'region': s['region'],
                    'score': s['score'],
                    'completion_rate': s['completion_rate'],
                    'follow_through_rate': s['follow_through_rate'],
                    'adjustment_success_rate': s['adjustment_success_rate'],
                })

            return {'empty': False, 'rows': rows}
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] get_analytics_leaderboard failed: {exc}', file=sys.stderr)
        return _empty


# ---------------------------------------------------------------------------
# Helper 4: get_studio_analytics
# ---------------------------------------------------------------------------

def get_studio_analytics(store_id, range_key):
    """
    Returns drill-down data for a single studio.

    Shape:
    {
      "empty": bool,
      "store_id": str,
      "name": str,
      "region": str,
      "funnel": [{"step": int, "count": int}, ...],   # steps 1–7
      "variance_trend": [{"week_identifier": str, "variances_found": int, "variances_still_off": int}, ...],
      "recent_runs": [
        {
          "id": int,
          "started_at": str,
          "counter_name": str,
          "status": str,
          "duration_seconds": int | None,
          "duration_formatted": str,
          "total_variances": int | None,
          "variances_reconciled": int | None
        },
        ...
      ]
    }
    """
    if range_key not in _VALID_RANGES:
        range_key = '4w'

    _empty_store = {'empty': True, 'store_id': store_id, 'name': '', 'region': '',
                    'funnel': [], 'variance_trend': [], 'recent_runs': []}

    try:
        conn = _get_db()
        try:
            if not _tables_exist(conn):
                return _empty_store

            # Look up studio
            store_row = conn.execute(
                'SELECT store_id, name, region FROM stores WHERE store_id = ?',
                (store_id,)
            ).fetchone()
            if not store_row:
                return _empty_store

            store_info = dict(store_row)

            cutoff = _range_cutoff(range_key)
            if cutoff:
                cutoff_str = cutoff.isoformat()
                runs = [dict(r) for r in conn.execute(
                    "SELECT id, store_id, week_identifier, status, started_at, "
                    "furthest_step, duration_seconds, total_variances, "
                    "variances_reconciled, variances_still_off, counter_name "
                    "FROM stock_checks WHERE store_id = ? AND started_at >= ? "
                    "ORDER BY started_at DESC",
                    (store_id, cutoff_str)
                ).fetchall()]
            else:
                runs = [dict(r) for r in conn.execute(
                    "SELECT id, store_id, week_identifier, status, started_at, "
                    "furthest_step, duration_seconds, total_variances, "
                    "variances_reconciled, variances_still_off, counter_name "
                    "FROM stock_checks WHERE store_id = ? "
                    "ORDER BY started_at DESC",
                    (store_id,)
                ).fetchall()]

            if not runs:
                return {**_empty_store, 'name': store_info['name'], 'region': store_info['region'] or ''}

            # Apply effective status
            for r in runs:
                r['_eff_status'] = _effective_status(r['status'], r['started_at'])

            # Funnel: for steps 1–7, count runs that reached at least that step
            funnel = []
            for step in range(1, 8):
                count = sum(1 for r in runs if (r['furthest_step'] or 0) >= step)
                funnel.append({'step': step, 'count': count})

            # Variance trend: completed runs only, per-week aggregates, ascending
            completed_runs = [r for r in runs if r['_eff_status'] == 'completed']
            weeks_data = {}
            for r in completed_runs:
                wk = r['week_identifier']
                if not wk:
                    continue
                if wk not in weeks_data:
                    weeks_data[wk] = {'found': 0, 'still_off': 0}
                weeks_data[wk]['found'] += r['total_variances'] or 0
                weeks_data[wk]['still_off'] += r['variances_still_off'] or 0

            variance_trend = [
                {'week_identifier': wk, 'variances_found': d['found'], 'variances_still_off': d['still_off']}
                for wk, d in sorted(weeks_data.items())
            ]

            # Recent runs: last 5, descending
            recent_runs = []
            for r in runs[:5]:
                recent_runs.append({
                    'id': r['id'],
                    'started_at': r['started_at'],
                    'counter_name': r['counter_name'] or '',
                    'status': r['_eff_status'],
                    'duration_seconds': r['duration_seconds'],
                    'duration_formatted': _format_duration(r['duration_seconds']),
                    'total_variances': r['total_variances'],
                    'variances_reconciled': r['variances_reconciled'],
                })

            return {
                'empty': False,
                'store_id': store_info['store_id'],
                'name': store_info['name'],
                'region': store_info['region'] or '',
                'funnel': funnel,
                'variance_trend': variance_trend,
                'recent_runs': recent_runs,
            }
        finally:
            conn.close()
    except Exception as exc:
        print(f'[analytics] get_studio_analytics failed: {exc}', file=sys.stderr)
        return _empty_store
