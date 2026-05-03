#!/usr/bin/env python3
"""Fetch TAIEX + OTC daily prices and 三大法人 aggregate net buy/sell.

Outputs:
  data/market.json {
    indices: {TAIEX:{current, change, change_pct, history:[...] }, OTC:{...}},
    institutional: {
      records: [{date, foreign_net, dealer_net, trust_net, total_net}, ...],
      latest: {...}
    },
    updated: ...
  }

Usage:
    python scripts/fetch_market.py
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'data' / 'market.json'

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


def fetch_index(code: str, start: str, end: str) -> dict | None:
    rows = finmind('TaiwanStockPrice', data_id=code, start_date=start, end_date=end)
    if not rows:
        return None
    rows.sort(key=lambda r: r.get('date', ''))
    closes = []
    sampled = []  # weekly sample for sparkline
    for i, r in enumerate(rows):
        try:
            c = float(r.get('close') or 0)
            if c <= 0:
                continue
        except (TypeError, ValueError):
            continue
        closes.append({'d': r['date'], 'c': c})
        if i == 0 or i == len(rows) - 1 or i % 4 == 0:
            sampled.append({'d': r['date'], 'c': round(c, 2)})
    if not closes:
        return None
    last = closes[-1]['c']
    prev = closes[-2]['c'] if len(closes) > 1 else None
    change = round(last - prev, 2) if prev else 0
    change_pct = round((last - prev) / prev * 100, 2) if prev else 0
    first_year = closes[0]['c']
    return_1y = round((last - first_year) / first_year * 100, 2) if first_year else 0
    return {
        'current': round(last, 2),
        'date': closes[-1]['d'],
        'change': change,
        'change_pct': change_pct,
        'return_1y': return_1y,
        'history': sampled,
    }


def fetch_institutional(start: str, end: str) -> dict:
    rows = finmind('TaiwanStockTotalInstitutionalInvestors',
                   start_date=start, end_date=end)
    by_date = defaultdict(lambda: {
        'foreign_net': 0, 'dealer_net': 0, 'trust_net': 0, 'total_net': 0,
    })
    for r in rows:
        try:
            d = r.get('date')
            name = r.get('name', '')
            buy = float(r.get('buy') or 0)
            sell = float(r.get('sell') or 0)
            net = buy - sell
        except (TypeError, ValueError):
            continue
        if not d:
            continue
        bucket = by_date[d]
        # FinMind returns multiple sub-categories per investor type — sum them.
        if name.startswith('Foreign'):
            bucket['foreign_net'] += net
        elif name.startswith('Dealer'):
            bucket['dealer_net'] += net
        elif name.startswith('Investment_Trust') or name.startswith('Trust'):
            bucket['trust_net'] += net
        bucket['total_net'] = bucket['foreign_net'] + bucket['dealer_net'] + bucket['trust_net']
    records = []
    for d in sorted(by_date.keys()):
        b = by_date[d]
        records.append({
            'date': d,
            'foreign_net': round(b['foreign_net']),
            'dealer_net': round(b['dealer_net']),
            'trust_net': round(b['trust_net']),
            'total_net': round(b['total_net']),
        })
    latest = records[-1] if records else None
    return {'records': records[-30:], 'latest': latest}


def main():
    today = datetime.now(TAIPEI)
    today_str = today.strftime('%Y-%m-%d')
    one_y = (today - timedelta(days=400)).strftime('%Y-%m-%d')
    one_m = (today - timedelta(days=45)).strftime('%Y-%m-%d')

    print(f"Fetching market data (FinMind token: {'set' if TOKEN else 'none'})...")
    indices = {}
    for label, code in (('TAIEX', 'TAIEX'), ('OTC', 'TPEx')):
        try:
            info = fetch_index(code, one_y, today_str)
            if info:
                indices[label] = info
                print(f"  {label}: {info['current']} ({info['change']:+.2f}, {info['change_pct']:+.2f}%) 1Y {info['return_1y']:+.2f}%")
            else:
                print(f"  {label}: no data")
        except Exception as e:
            print(f"  {label}: FAILED {e}")

    print('Fetching institutional flow...')
    try:
        inst = fetch_institutional(one_m, today_str)
        print(f"  records: {len(inst['records'])} latest: {inst['latest']}")
    except Exception as e:
        print(f"  FAILED {e}")
        inst = {'records': [], 'latest': None}

    payload = {
        'updated': today.strftime('%Y-%m-%d %H:%M:%S+08:00'),
        'indices': indices,
        'institutional': inst,
    }
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUTPUT}")


if __name__ == '__main__':
    main()
