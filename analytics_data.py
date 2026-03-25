"""
Dummy analytics data for STUDS HQ dashboard.
Uses fixed seed for consistent data across reloads.
"""
import random

random.seed(42)

WEEK_LABELS = [f'W{i}' for i in range(1, 13)]

# Store personality profiles: (compliance_base, lag_base, trend_type)
STORE_PROFILES = {
    '001': (0.92, 6, 'stable'), '002': (0.88, 8, 'stable'), '003': (0.90, 7, 'improving'),
    '004': (0.85, 10, 'stable'), '005': (0.93, 5, 'stable'),
    '006': (0.75, 18, 'declining'), '007': (0.78, 15, 'stable'), '008': (0.72, 20, 'improving'),
    '009': (0.80, 12, 'stable'), '010': (0.70, 22, 'declining'),
    '011': (0.65, 24, 'improving'), '012': (0.68, 22, 'declining'), '013': (0.72, 18, 'stable'),
    '014': (0.60, 28, 'declining'), '015': (0.74, 16, 'improving'),
    '016': (0.55, 32, 'declining'), '017': (0.58, 30, 'stable'), '018': (0.52, 35, 'declining'),
    '019': (0.62, 26, 'improving'), '020': (0.50, 38, 'declining'),
    '021': (0.56, 34, 'stable'), '022': (0.60, 28, 'improving'), '023': (0.54, 36, 'declining'),
    '024': (0.65, 24, 'stable'), '025': (0.58, 30, 'improving'),
    '026': (0.78, 14, 'stable'), '027': (0.82, 12, 'improving'), '028': (0.75, 16, 'stable'),
    '029': (0.70, 20, 'declining'), '030': (0.80, 10, 'stable'),
    '031': (0.76, 15, 'improving'), '032': (0.82, 11, 'stable'), '033': (0.78, 14, 'stable'),
    '034': (0.84, 9, 'improving'), '035': (0.72, 18, 'declining'),
    '036': (0.88, 7, 'stable'), '037': (0.85, 8, 'improving'), '038': (0.90, 6, 'stable'),
    '039': (0.82, 10, 'stable'), '040': (0.86, 9, 'stable'),
}

DUMMY_SKUS = [
    ('PS083GCL', '14K Marquise Clear'), ('PS154KCL', 'Twinkle Star 14K Stud'),
    ('HU004G', 'Small Huggie Gold'), ('FB012S', 'Flat Back Silver 12mm'),
    ('FC006G', 'CZ Clicker Gold 6mm'), ('PS170KCL', '14K 4mm CZ Stud'),
    ('CI002G', 'Small Chain Connector Gold'), ('HP010G', 'French Twist Hoop'),
    ('PS134KOP', 'Opal 14K Stud'), ('FI002GT', 'Industrial Bar 38mm'),
    ('EAR-TI-GLD', 'Tiny Gold Studs'), ('EAR-HG-SLV', 'Huggie Silver Hoops'),
    ('HP004G', 'Small Slim Hoop Gold'), ('PS177SGR', 'Crown Marquise Titanium'),
    ('FB008G', 'Flat Back Gold 8mm'),
]


def _gen_weekly_history():
    """Generate 12 weeks of per-store compliance data."""
    history = {}
    for sid, (comp_base, lag_base, trend) in STORE_PROFILES.items():
        weeks = []
        for w in range(12):
            # Apply trend: improving stores get better over time, declining get worse
            if trend == 'improving':
                adj = (w - 6) * 0.02
            elif trend == 'declining':
                adj = -(w - 6) * 0.02
            else:
                adj = 0
            eff_comp = min(0.98, max(0.30, comp_base + adj + random.uniform(-0.12, 0.12)))
            roll = random.random()
            if roll < eff_comp:
                status = 'Updated'
                disc = 0
                net = 0
                lag = max(0.5, lag_base + random.uniform(-lag_base * 0.4, lag_base * 0.4))
            elif roll < eff_comp + (1 - eff_comp) * 0.7:
                status = 'Discrepancy Detected'
                disc = random.randint(1, 8)
                net = random.randint(-15, 15)
                if net == 0:
                    net = random.choice([-1, 1])
                lag = max(1, lag_base * 1.3 + random.uniform(-5, 10))
            else:
                status = 'Incomplete (missing file)'
                disc = 0
                net = 0
                lag = None
            weeks.append({
                'week': WEEK_LABELS[w],
                'status': status,
                'discrepancy_count': disc,
                'net_discrepancy': net,
                'update_lag_hours': round(lag, 1) if lag is not None else None,
            })
        history[sid] = weeks
    return history


def _gen_top_skus():
    """Generate top discrepancy SKUs company-wide."""
    result = []
    for sku, desc in DUMMY_SKUS:
        result.append({
            'sku': sku,
            'description': desc,
            'total_discrepancy_units': random.randint(20, 150),
            'stores_affected': random.randint(3, 25),
            'weeks_appearing': random.randint(4, 12),
        })
    result.sort(key=lambda x: x['total_discrepancy_units'], reverse=True)
    return result


def _gen_leaderboard(history):
    """Generate store leaderboard from weekly history."""
    board = []
    for sid, weeks in sorted(history.items()):
        total = len(weeks)
        updated = sum(1 for w in weeks if w['status'] == 'Updated')
        comp_rate = round(updated / total * 100, 1) if total else 0
        lags = [w['update_lag_hours'] for w in weeks if w['update_lag_hours'] is not None]
        avg_lag = round(sum(lags) / len(lags), 1) if lags else 0
        total_disc = sum(abs(w['net_discrepancy']) for w in weeks)
        # Trend: compare last 4 vs previous 4
        recent = sum(1 for w in weeks[-4:] if w['status'] == 'Updated')
        earlier = sum(1 for w in weeks[4:8] if w['status'] == 'Updated')
        if recent > earlier + 1:
            trend = 'improving'
        elif recent < earlier - 1:
            trend = 'declining'
        else:
            trend = 'stable'
        board.append({
            'store_id': sid,
            'compliance_rate': comp_rate,
            'avg_update_lag_hours': avg_lag,
            'total_discrepancy_units': total_disc,
            'trend': trend,
        })
    board.sort(key=lambda x: x['compliance_rate'], reverse=True)
    return board


def _gen_weekly_trend(history):
    """Generate company-wide weekly trend."""
    trend = []
    for w in range(12):
        updated = discrepancy = incomplete = 0
        for weeks in history.values():
            s = weeks[w]['status']
            if s == 'Updated':
                updated += 1
            elif s == 'Discrepancy Detected':
                discrepancy += 1
            else:
                incomplete += 1
        trend.append({
            'week_label': WEEK_LABELS[w],
            'updated_count': updated,
            'discrepancy_count': discrepancy,
            'incomplete_count': incomplete,
        })
    return trend


def _gen_distribution(history):
    """Generate discrepancy size distribution."""
    buckets = {'0': 0, '1-2': 0, '3-5': 0, '6-10': 0, '11-20': 0, '20+': 0}
    for weeks in history.values():
        for w in weeks:
            d = abs(w['net_discrepancy'])
            if d == 0:
                buckets['0'] += 1
            elif d <= 2:
                buckets['1-2'] += 1
            elif d <= 5:
                buckets['3-5'] += 1
            elif d <= 10:
                buckets['6-10'] += 1
            elif d <= 20:
                buckets['11-20'] += 1
            else:
                buckets['20+'] += 1
    return buckets


def _gen_store_detail(history):
    """Generate per-store detail (chronic SKUs, sparkline data)."""
    detail = {}
    for sid, weeks in history.items():
        # Pick 2-4 chronic SKUs from the dummy list
        n = random.randint(2, 4)
        chronic = random.sample(DUMMY_SKUS, n)
        chronic_skus = [{'sku': s[0], 'description': s[1], 'occurrences': random.randint(3, 10)} for s in chronic]
        chronic_skus.sort(key=lambda x: x['occurrences'], reverse=True)
        sparkline = [w['net_discrepancy'] for w in weeks]
        detail[sid] = {
            'chronic_skus': chronic_skus,
            'sparkline': sparkline,
        }
    return detail


# Pre-generate all data at import time
_history = _gen_weekly_history()
_top_skus = _gen_top_skus()
_leaderboard = _gen_leaderboard(_history)
_weekly_trend = _gen_weekly_trend(_history)
_distribution = _gen_distribution(_history)
_store_detail = _gen_store_detail(_history)


def get_analytics_data():
    """Return all company-wide analytics data."""
    total_weeks = sum(len(w) for w in _history.values())
    total_updated = sum(1 for ws in _history.values() for w in ws if w['status'] == 'Updated')
    all_lags = [w['update_lag_hours'] for ws in _history.values() for w in ws if w['update_lag_hours'] is not None]
    total_disc = sum(abs(w['net_discrepancy']) for ws in _history.values() for w in ws)
    chronic_count = sum(1 for s in _leaderboard if s['compliance_rate'] < 60)
    top_count = sum(1 for s in _leaderboard if s['compliance_rate'] >= 90)
    chronic_stores = [s for s in _leaderboard if s['compliance_rate'] < 60]
    top_stores = sorted([s for s in _leaderboard if s['compliance_rate'] >= 90], key=lambda x: x['compliance_rate'], reverse=True)

    return {
        'network_compliance_rate': round(total_updated / total_weeks * 100, 1) if total_weeks else 0,
        'avg_update_lag': round(sum(all_lags) / len(all_lags), 1) if all_lags else 0,
        'total_discrepancy_units': total_disc,
        'chronic_offender_count': chronic_count,
        'top_performer_count': top_count,
        'chronic_stores': chronic_stores,
        'top_stores': top_stores,
        'weekly_trend': _weekly_trend,
        'leaderboard': _leaderboard,
        'top_skus': _top_skus,
        'distribution': _distribution,
    }


def get_store_analytics(store_id):
    """Return analytics data for a specific store."""
    lb = next((s for s in _leaderboard if s['store_id'] == store_id), None)
    detail = _store_detail.get(store_id, {'chronic_skus': [], 'sparkline': [0]*12})
    return {
        'compliance_rate': lb['compliance_rate'] if lb else 0,
        'avg_update_lag_hours': lb['avg_update_lag_hours'] if lb else 0,
        'total_discrepancy_units': lb['total_discrepancy_units'] if lb else 0,
        'chronic_skus': detail['chronic_skus'],
        'sparkline': detail['sparkline'],
    }


def get_all_store_analytics():
    """Return analytics data for all stores as a dict keyed by store_id."""
    result = {}
    for sid in STORE_PROFILES:
        result[sid] = get_store_analytics(sid)
    return result
