#!/usr/bin/env python3
"""Fetch all (mainstream) Taiwan ETFs and compute a 5-dimension score.

For each ETF:
  - 1Y prices  -> current_price, 1Y return %, annualized volatility, avg daily turnover
  - dividends  -> TTM cash dividend, yield = ttm_div / current_price

Score dimensions (each 0..100, equal-weighted):
  - yield_score    : higher TTM yield is better  (capped at 8%)
  - return_score   : higher 1Y total return is better
  - scale_score    : log10(avg daily turnover NTD)
  - stability_score: lower volatility is better
  - cost_score     : reserved (FinMind doesn't expose expense ratios) — placeholder

Output: data/etf_list.json
  {
    "updated": "...",
    "count": N,
    "etfs": [
      {code, name, current_price, change_pct, return_1y, volatility, ttm_dividend,
       yield_pct, avg_turnover, scores: {yield, return, scale, stability, total},
       category}, ...
    ]
  }

Usage:
    python scripts/fetch_etf.py
    python scripts/fetch_etf.py --limit 50    # for quick local runs
    python scripts/fetch_etf.py --include-bond  # keep bond/leveraged ETFs
"""
import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / 'data' / 'etf_list.json'

FINMIND_BASE = 'https://api.finmindtrade.com/api/v4/data'
TOKEN = os.environ.get('FINMIND_TOKEN', '')
TAIPEI = timezone(timedelta(hours=8))


def finmind(dataset, **params):
    p = {'dataset': dataset, **params}
    if TOKEN:
        p['token'] = TOKEN
    r = requests.get(FINMIND_BASE, params=p, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get('status') != 200:
        raise RuntimeError(f"FinMind {dataset}: {j.get('msg')}")
    return j.get('data', [])


# Regex flags to skip non-equity / leveraged / inverse / bond ETFs.
BOND_PATTERNS = re.compile(r'(債|公債|金融債|投資級|高評級|高息債|可轉債|REITs|商品|期信|黃金)')
LEVER_PATTERNS = re.compile(r'(正2|正二|反1|反一|槓桿|反向)')


def categorize(name: str) -> str:
    """Loose category for filtering; not a formal taxonomy."""
    if BOND_PATTERNS.search(name):
        return 'bond'
    if LEVER_PATTERNS.search(name):
        return 'leveraged'
    if re.search(r'(美國|S&P|那斯|納斯|科技ETF|半導體)', name):
        return 'us_tech'
    if re.search(r'(高股息|高息|配息|月配|季配)', name):
        return 'dividend'
    if re.search(r'(臺灣|台灣|0050|台股)', name):
        return 'tw_market'
    if re.search(r'(陸|中國|港|越南|印度|東協|日本|新興)', name):
        return 'foreign'
    return 'other'


def fetch_etf_universe(include_bond: bool, limit: int | None) -> list[dict]:
    rows = finmind('TaiwanStockInfo')
    etfs = [
        r for r in rows
        if 'ETF' in (r.get('industry_category') or '')
    ]
    # Dedupe by stock_id (TaiwanStockInfo can return duplicates per market)
    seen = set()
    deduped = []
    for r in etfs:
        sid = r.get('stock_id')
        if not sid or sid in seen:
            continue
        seen.add(sid)
        # Skip futures/options-style codes (suffix not in mainstream listing)
        if not re.match(r'^00\d{2,4}[A-Z]?$', sid):
            continue
        name = r.get('stock_name', '')
        cat = categorize(name)
        if not include_bond and cat in ('bond', 'leveraged'):
            continue
        deduped.append({'code': sid, 'name': name, 'category': cat})
    deduped.sort(key=lambda x: x['code'])
    if limit:
        deduped = deduped[:limit]
    return deduped


def annualized_vol(closes: list[float]) -> float | None:
    """Daily log-return std × sqrt(250).

    Single-day moves larger than ±30% (|log-return| > 0.30) are skipped: the
    only thing that moves a TW-listed ETF that much in one day is a split /
    reverse-split on FinMind's *unadjusted* free-tier prices (e.g. 0050's 1:4
    split → a −75% gap). Counting that artificial gap as real volatility
    crushed flagship ETFs (0050 showed ~137% annualized vol → stability ≈ 0,
    ranked near the bottom). Real moves are capped at the ±10% daily limit, so
    this filter is a no-op for non-split ETFs.
    """
    if len(closes) < 30:
        return None
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            r = math.log(closes[i] / closes[i - 1])
            if abs(r) > 0.30:
                continue  # split / reverse-split artifact (unadjusted prices)
            rets.append(r)
    if not rets:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(var) * math.sqrt(250)


def detect_split(closes: list[float], threshold: float = 0.30) -> bool:
    """Return True if any consecutive day-over-day drop exceeds `threshold` (proportion).
    FinMind free tier does not provide adjusted closes; a single-day -75% gap from a
    1:4 split (e.g. 0050 in 2024-12) would otherwise be reported as a -75% 1Y return.
    """
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] / closes[i - 1] < (1 - threshold):
            return True
    return False


def fetch_metrics(code: str) -> dict | None:
    today = datetime.now(TAIPEI)
    today_str = today.strftime('%Y-%m-%d')
    one_y = (today - timedelta(days=400)).strftime('%Y-%m-%d')

    prices = finmind('TaiwanStockPrice', data_id=code,
                     start_date=one_y, end_date=today_str)
    if not prices:
        return None
    # Sort by date asc (FinMind usually does this but be safe)
    prices.sort(key=lambda p: p.get('date', ''))
    closes = []
    turnovers = []
    for p in prices:
        try:
            c = float(p.get('close') or 0)
            v = float(p.get('Trading_Volume') or 0)
            if c > 0:
                closes.append(c)
                turnovers.append(c * v)
        except (TypeError, ValueError):
            continue
    if len(closes) < 30:
        return None
    current = closes[-1]
    prev = closes[-2] if len(closes) > 1 else None
    change_pct = (current - prev) / prev * 100 if prev else 0
    # 1Y return: first close in series vs last. Skip if we detect a likely split.
    has_split = detect_split(closes)
    return_1y = None if has_split else (current - closes[0]) / closes[0] * 100
    vol = annualized_vol(closes)
    avg_turnover = sum(turnovers[-60:]) / max(1, len(turnovers[-60:])) if turnovers else 0

    # Dividends — use TTM (last 12 months sum)
    div_data = []
    try:
        div_data = finmind(
            'TaiwanStockDividend',
            data_id=code,
            start_date=(today - timedelta(days=400)).strftime('%Y-%m-%d'),
            end_date=today_str,
        )
    except Exception:
        pass
    ttm_div = 0.0
    cutoff = today - timedelta(days=365)
    for d in div_data:
        ex_date = d.get('CashExDividendTradingDate') or d.get('date') or ''
        try:
            ed = datetime.strptime(ex_date[:10], '%Y-%m-%d').replace(tzinfo=TAIPEI)
        except Exception:
            continue
        if ed < cutoff:
            continue
        cash = (
            float(d.get('CashEarningsDistribution') or 0)
            + float(d.get('CashStatutorySurplus') or 0)
        )
        ttm_div += cash
    yield_pct = (ttm_div / current * 100) if current > 0 and ttm_div > 0 else None

    return {
        'current_price': round(current, 2),
        'change_pct': round(change_pct, 2),
        'return_1y': round(return_1y, 2) if return_1y is not None else None,
        'split_detected': has_split,
        'volatility': round(vol * 100, 2) if vol is not None else None,
        'ttm_dividend': round(ttm_div, 4),
        'yield_pct': round(yield_pct, 2) if yield_pct is not None else None,
        'avg_turnover': round(avg_turnover, 0),
    }


def normalize(values: list[float], lower_is_better: bool = False) -> list[float | None]:
    """Min-max normalize to 0..100. Skip None entries."""
    valid = [v for v in values if v is not None]
    if not valid:
        return [None] * len(values)
    lo, hi = min(valid), max(valid)
    if hi == lo:
        return [50.0 if v is not None else None for v in values]
    out = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        score = (v - lo) / (hi - lo) * 100
        if lower_is_better:
            score = 100 - score
        out.append(round(score, 1))
    return out


def compute_scores(etfs: list[dict]) -> None:
    """Mutates each etf dict, adding `scores`."""
    yields = [e['metrics'].get('yield_pct') for e in etfs]
    returns = [e['metrics'].get('return_1y') for e in etfs]
    turnovers = [
        math.log10(e['metrics'].get('avg_turnover')) if e['metrics'].get('avg_turnover') and e['metrics']['avg_turnover'] > 0 else None
        for e in etfs
    ]
    vols = [e['metrics'].get('volatility') for e in etfs]

    yield_s = normalize(yields)
    return_s = normalize(returns)
    scale_s = normalize(turnovers)
    stab_s = normalize(vols, lower_is_better=True)

    for i, e in enumerate(etfs):
        s = {
            'yield': yield_s[i],
            'return': return_s[i],
            'scale': scale_s[i],
            'stability': stab_s[i],
        }
        present = [v for v in s.values() if v is not None]
        s['total'] = round(sum(present) / len(present), 1) if present else None
        e['scores'] = s


def main():
    parser = argparse.ArgumentParser(description='Fetch TW ETF list + compute scores.')
    parser.add_argument('--limit', type=int, default=None,
                        help='Cap how many ETFs to process (useful for local testing).')
    parser.add_argument('--include-bond', action='store_true',
                        help='Keep bond and leveraged ETFs in the universe.')
    parser.add_argument('--throttle', type=float, default=0.05,
                        help='Seconds to sleep between FinMind calls (rate limiting).')
    args = parser.parse_args()

    print(f"FinMind token: {'set' if TOKEN else 'none (anonymous)'}")
    print('Fetching ETF universe...')
    universe = fetch_etf_universe(args.include_bond, args.limit)
    print(f"Universe: {len(universe)} ETFs")

    results = []
    failures = []
    for i, ent in enumerate(universe, 1):
        code, name = ent['code'], ent['name']
        try:
            m = fetch_metrics(code)
            if m is None:
                failures.append(code)
                print(f"[{i}/{len(universe)}] {code} {name}: no usable price data, skip")
                continue
            results.append({
                'code': code,
                'name': name,
                'category': ent['category'],
                'metrics': m,
            })
            r1y_str = f"{m['return_1y']:+.1f}%" if m['return_1y'] is not None else 'split?'
            print(f"[{i}/{len(universe)}] {code} {name}: price {m['current_price']} 1Y {r1y_str} yield {m['yield_pct'] or 0:.2f}%")
        except Exception as e:
            failures.append(code)
            print(f"[{i}/{len(universe)}] {code} {name}: FAILED {e}")
        time.sleep(args.throttle)

    # Compute scores cross-ETF (relative ranking)
    compute_scores(results)

    # Flatten metrics into top-level for easier client use
    for r in results:
        r.update(r.pop('metrics'))

    payload = {
        'updated': datetime.now(TAIPEI).strftime('%Y-%m-%d %H:%M:%S+08:00'),
        'count': len(results),
        'etfs': sorted(
            results,
            key=lambda r: r.get('scores', {}).get('total') or -1,
            reverse=True,
        ),
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(results)} ETFs -> {OUTPUT_FILE}")
    if failures:
        print(f"Failed/skipped: {len(failures)} ({', '.join(failures[:10])}{'...' if len(failures) > 10 else ''})")


if __name__ == '__main__':
    main()
