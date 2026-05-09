#!/usr/bin/env python3
"""Backtest ADR / SOX → next-day TW open/high/low/close.

For each (TW stock, ADR) pair flagged as `dashboard: true` in stocks.json,
computes empirical conditional distributions of next-day TW move given:
  1. ADR overnight change %     (ADR[T] vs ADR[T-1])
  2. ADR-TW premium %           ((ADR[T]*FX[T]/ratio - TW[T]) / TW[T])
  3. SOX index change %         (^SOX[T] vs ^SOX[T-1])

Pairs each US trading day T (calendar-aligned to TW day T) with the next
available TW trading day T+1, then reports per-bucket count / mean /
median / max / min / hit-rate for next-day TW open-gap, intraday high/low
versus prior close, and full-day close change.

Output: data/adr_backtest.json (consumed by ADRDashboardView).

Usage:
    python scripts/backtest_adr.py
"""
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
STOCKS_FILE = ROOT / 'data' / 'stocks.json'
TW_DIR = ROOT / 'data' / 'tw'
OUTPUT = ROOT / 'data' / 'adr_backtest.json'

TAIPEI = timezone(timedelta(hours=8))
LOOKBACK_DAYS = 730  # ~2 years; intersected with available TW kline window

# Bucket edges for ADR change %, premium %, SOX change %.
# Boundaries chosen to give roughly balanced sample sizes around zero
# while still isolating tail moves.
ADR_CHANGE_BUCKETS = [-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3]
PREMIUM_BUCKETS    = [-3, -1, 0, 1, 3, 5, 8]
SOX_BUCKETS        = [-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3]


def fetch_history(symbol: str, start: str):
    """Return {date_str: {'o','h','l','c'}} or empty dict on failure."""
    try:
        h = yf.Ticker(symbol).history(start=start, auto_adjust=False)
    except Exception as e:
        print(f"  fetch fail {symbol}: {e}", file=sys.stderr)
        return {}
    if h.empty:
        return {}
    out = {}
    for ts, row in h.iterrows():
        d = str(ts.date())
        try:
            out[d] = {
                'o': float(row['Open']),
                'h': float(row['High']),
                'l': float(row['Low']),
                'c': float(row['Close']),
            }
        except (KeyError, ValueError, TypeError):
            continue
    return out


def fetch_close_series(symbol: str, start: str):
    """Return {date_str: close_float} — used for FX & SOX where we only need close."""
    h = fetch_history(symbol, start)
    return {d: row['c'] for d, row in h.items()}


def bucket_index(value: float, edges):
    """Return bucket index 0..len(edges) for value, given sorted edges."""
    for i, e in enumerate(edges):
        if value < e:
            return i
    return len(edges)


def bucket_label(idx: int, edges):
    if idx == 0:
        return f"≤ {edges[0]:g}%"
    if idx == len(edges):
        return f"> {edges[-1]:g}%"
    return f"{edges[idx-1]:g}% ~ {edges[idx]:g}%"


def summarize(values, signs):
    """Stats on a list of floats. signs: list of +1/-1 from the predictor;
    hit_rate = fraction of days where target sign matches predictor sign."""
    if not values:
        return None
    out = {
        'n': len(values),
        'mean':   round(statistics.mean(values), 3),
        'median': round(statistics.median(values), 3),
        'max':    round(max(values), 3),
        'min':    round(min(values), 3),
    }
    if len(values) >= 4:
        try:
            qs = statistics.quantiles(values, n=4)
            out['p25'] = round(qs[0], 3)
            out['p75'] = round(qs[2], 3)
        except statistics.StatisticsError:
            pass
    if signs and len(signs) == len(values):
        same = sum(1 for v, s in zip(values, signs)
                   if (v > 0 and s > 0) or (v < 0 and s < 0))
        out['hit_rate'] = round(same / len(values), 3)
    return out


def build_buckets(samples, edges, predictor_key, target_keys):
    """Group samples by bucket, summarize each target column.
    samples: list of dicts each containing predictor_key + target_keys.
    Returns list of {label, lo, hi, n, <target>: {n,mean,median,...}}."""
    grouped = [[] for _ in range(len(edges) + 1)]
    for s in samples:
        v = s.get(predictor_key)
        if v is None:
            continue
        grouped[bucket_index(v, edges)].append(s)

    out = []
    for i, group in enumerate(grouped):
        lo = edges[i-1] if i > 0 else None
        hi = edges[i] if i < len(edges) else None
        entry = {
            'label': bucket_label(i, edges),
            'lo': lo,
            'hi': hi,
            'n': len(group),
        }
        if group:
            preds = [g[predictor_key] for g in group]
            entry['predictor_mean'] = round(statistics.mean(preds), 3)
            for tk in target_keys:
                vals = [g[tk] for g in group if g.get(tk) is not None]
                # Sign of predictor for each kept target sample.
                signs = [1 if g[predictor_key] >= 0 else -1
                         for g in group if g.get(tk) is not None]
                stats = summarize(vals, signs)
                if stats:
                    entry[tk] = stats
        out.append(entry)
    return out


def correlation(samples, x_key, y_key):
    pairs = [(s[x_key], s[y_key]) for s in samples
             if s.get(x_key) is not None and s.get(y_key) is not None]
    if len(pairs) < 5:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    try:
        return round(statistics.correlation(xs, ys), 3)
    except (statistics.StatisticsError, ValueError):
        return None


def main():
    with open(STOCKS_FILE, encoding='utf-8') as f:
        meta = json.load(f)

    headline_pairs = [
        {'tw_code': info['tw_code'], 'adr': adr, 'ratio': info['ratio']}
        for adr, info in meta['adr_mapping'].items()
        if info.get('dashboard')
    ]
    if not headline_pairs:
        print('No headline ADRs configured (set "dashboard": true in stocks.json).')
        return

    start = (datetime.now(TAIPEI) - timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    print(f"Backtest start date: {start}")

    print('Fetching FX (USD/TWD) history...')
    fx = fetch_close_series('USDTWD=X', start)
    print(f"  {len(fx)} days")

    print('Fetching SOX history...')
    sox = fetch_close_series('^SOX', start)
    print(f"  {len(sox)} days")

    # SOX overnight change %, indexed by US trading date.
    sox_dates = sorted(sox.keys())
    sox_change = {}
    for i in range(1, len(sox_dates)):
        d, prev = sox_dates[i], sox_dates[i-1]
        if sox[prev]:
            sox_change[d] = (sox[d] / sox[prev] - 1) * 100

    per_stock = {}
    for pair in headline_pairs:
        tw_code = pair['tw_code']
        adr_sym = pair['adr']
        ratio = pair['ratio']
        tw_meta = meta['tw_stocks'].get(tw_code, {})
        tw_name = tw_meta.get('name', tw_code)
        print(f"\n[{tw_code} {tw_name} / ADR {adr_sym} ratio={ratio}]")

        # Load TW kline (full OHLC, ~1y)
        tw_file = TW_DIR / f'{tw_code}.json'
        if not tw_file.exists():
            print(f"  TW file missing: {tw_file.name}")
            continue
        with open(tw_file, encoding='utf-8') as f:
            tw_data = json.load(f)
        kline = tw_data.get('kline', [])
        if not kline:
            print('  no kline data')
            continue
        tw_by_date = {row['d']: row for row in kline}
        tw_dates_sorted = sorted(tw_by_date.keys())

        # Fetch ADR history covering the kline range.
        adr_start = tw_dates_sorted[0]
        # Pad start by ~10 days so we have ADR[T-1] for the first TW day.
        adr_start_pad = (datetime.strptime(adr_start, '%Y-%m-%d')
                         - timedelta(days=10)).strftime('%Y-%m-%d')
        print(f"  fetching ADR {adr_sym} from {adr_start_pad}...")
        adr_hist = fetch_history(adr_sym, adr_start_pad)
        print(f"  ADR days: {len(adr_hist)}")
        if not adr_hist:
            continue

        adr_dates = sorted(adr_hist.keys())
        adr_change = {}
        for i in range(1, len(adr_dates)):
            d, prev = adr_dates[i], adr_dates[i-1]
            if adr_hist[prev]['c']:
                adr_change[d] = (adr_hist[d]['c'] / adr_hist[prev]['c'] - 1) * 100

        # Build samples: for each TW trading day T with a next TW day T+1,
        # collect signals @ T and targets @ T+1.
        samples = []
        for i in range(len(tw_dates_sorted) - 1):
            t = tw_dates_sorted[i]
            t_next = tw_dates_sorted[i+1]
            tw_t = tw_by_date[t]
            tw_n = tw_by_date[t_next]
            close_t = tw_t.get('c')
            if not close_t:
                continue

            # ADR signals @ T (calendar-aligned)
            adr_row = adr_hist.get(t)
            adr_chg = adr_change.get(t)
            premium = None
            if adr_row and t in fx:
                implied = adr_row['c'] * fx[t] / ratio
                premium = (implied - close_t) / close_t * 100

            sox_chg = sox_change.get(t)

            # Targets @ T+1 vs close @ T (in %).
            open_n = tw_n.get('o')
            high_n = tw_n.get('h')
            low_n = tw_n.get('l')
            close_n = tw_n.get('c')
            if not open_n:
                continue

            sample = {
                'date': t,
                'next_date': t_next,
                'adr_change': adr_chg,
                'premium': premium,
                'sox_change': sox_chg,
                'open_gap':    (open_n - close_t)  / close_t * 100 if open_n else None,
                'max_gain':    (high_n - close_t)  / close_t * 100 if high_n else None,
                'max_loss':    (low_n  - close_t)  / close_t * 100 if low_n else None,
                'close_change':(close_n - close_t) / close_t * 100 if close_n else None,
            }
            samples.append(sample)

        if not samples:
            print('  no usable samples')
            continue

        targets = ['open_gap', 'max_gain', 'max_loss', 'close_change']
        adr_samples = [s for s in samples if s['adr_change'] is not None]
        prem_samples = [s for s in samples if s['premium'] is not None]
        sox_samples = [s for s in samples if s['sox_change'] is not None]

        per_stock[tw_code] = {
            'name': tw_name,
            'adr': adr_sym,
            'ratio': ratio,
            'total_samples': len(samples),
            'date_range': [samples[0]['date'], samples[-1]['date']],
            'by_adr_change': {
                'n': len(adr_samples),
                'corr_open_gap':     correlation(adr_samples, 'adr_change', 'open_gap'),
                'corr_close_change': correlation(adr_samples, 'adr_change', 'close_change'),
                'buckets': build_buckets(adr_samples, ADR_CHANGE_BUCKETS, 'adr_change', targets),
            },
            'by_premium': {
                'n': len(prem_samples),
                'corr_open_gap':     correlation(prem_samples, 'premium', 'open_gap'),
                'corr_close_change': correlation(prem_samples, 'premium', 'close_change'),
                'buckets': build_buckets(prem_samples, PREMIUM_BUCKETS, 'premium', targets),
            },
            'by_sox_change': {
                'n': len(sox_samples),
                'corr_open_gap':     correlation(sox_samples, 'sox_change', 'open_gap'),
                'corr_close_change': correlation(sox_samples, 'sox_change', 'close_change'),
                'buckets': build_buckets(sox_samples, SOX_BUCKETS, 'sox_change', targets),
            },
        }
        print(f"  {len(samples)} samples · "
              f"corr(ADR change → open gap)={per_stock[tw_code]['by_adr_change']['corr_open_gap']} · "
              f"corr(SOX change → open gap)={per_stock[tw_code]['by_sox_change']['corr_open_gap']}")

    payload = {
        'updated': datetime.now(TAIPEI).strftime('%Y-%m-%d %H:%M:%S+08:00'),
        'lookback_days': LOOKBACK_DAYS,
        'adr_change_buckets': ADR_CHANGE_BUCKETS,
        'premium_buckets': PREMIUM_BUCKETS,
        'sox_buckets': SOX_BUCKETS,
        'targets_explained': {
            'open_gap':     '隔日 TW 開盤 vs 當日 TW 收盤（%）',
            'max_gain':     '隔日 TW 盤中最高 vs 當日收盤（%，最大上行幅度）',
            'max_loss':     '隔日 TW 盤中最低 vs 當日收盤（%，最大下行幅度）',
            'close_change': '隔日 TW 收盤 vs 當日收盤（%，全天淨變化）',
        },
        'stocks': per_stock,
    }
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {OUTPUT}")


if __name__ == '__main__':
    main()
