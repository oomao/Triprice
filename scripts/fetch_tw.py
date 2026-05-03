#!/usr/bin/env python3
"""Fetch TW stock data from FinMind, compute valuations, save JSON per stock.

Outputs one JSON per stock to data/tw/{code}.json with current price,
yield-method valuation, PE-method valuation, EPS quarterly, and dividend history.

Usage:
    python scripts/fetch_tw.py              # fetch all in stocks.json
    python scripts/fetch_tw.py 2330 0050    # fetch specific codes

Env:
    FINMIND_TOKEN  Optional FinMind API token (raises rate limit).
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STOCKS_FILE = ROOT / 'data' / 'stocks.json'
OUTPUT_DIR = ROOT / 'data' / 'tw'

FINMIND_BASE = 'https://api.finmindtrade.com/api/v4/data'
TOKEN = os.environ.get('FINMIND_TOKEN', '')

TAIPEI = timezone(timedelta(hours=8))


def now_taipei() -> datetime:
    return datetime.now(TAIPEI)


def finmind(dataset: str, **params) -> list:
    p = {'dataset': dataset, **params}
    if TOKEN:
        p['token'] = TOKEN
    r = requests.get(FINMIND_BASE, params=p, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get('status') != 200:
        raise RuntimeError(f"FinMind {dataset}: {j.get('msg')}")
    return j.get('data', [])


def parse_year(y) -> int | None:
    """Parse year field which can be '109', '109年第3季', 2020 etc.
    Returns 西元 (Gregorian) year. Treats < 200 as 民國 and adds 1911."""
    if y is None:
        return None
    s = str(y).strip()
    m = re.match(r'^(\d+)', s)
    if not m:
        return None
    n = int(m.group(1))
    if n < 200:
        n += 1911
    return n


def pick_latest_dividend(by_year: dict, current_year: int):
    """Pick the most recent year with a meaningful dividend.
    If current calendar year is in data and its total < 50% of previous year,
    treat as incomplete and fall back to previous year."""
    sorted_years = sorted(by_year.keys(), reverse=True)
    if not sorted_years:
        return None, 0.0
    top = sorted_years[0]
    top_div = by_year[top]
    if top == current_year and len(sorted_years) >= 2:
        prev = sorted_years[1]
        prev_div = by_year[prev]
        if prev_div > 0 and top_div < 0.5 * prev_div:
            return prev, prev_div
    return top, top_div


def compute_yield_valuation(latest_dividend, yields):
    pos = [y for y in yields if y and y > 0]
    if not pos or not latest_dividend:
        return None, None
    high, low, avg = max(pos), min(pos), sum(pos) / len(pos)
    return (
        {
            'cheap': round(latest_dividend / high, 2),
            'fair': round(latest_dividend / avg, 2),
            'expensive': round(latest_dividend / low, 2),
        },
        {'high': round(high, 4), 'avg': round(avg, 4), 'low': round(low, 4)},
    )


def compute_pe_valuation(eps_ttm, pes):
    pos = [p for p in pes if p and p > 0]
    if not pos or not eps_ttm or eps_ttm <= 0:
        return None, None
    high, low, avg = max(pos), min(pos), sum(pos) / len(pos)
    return (
        {
            'cheap': round(eps_ttm * low, 2),
            'fair': round(eps_ttm * avg, 2),
            'expensive': round(eps_ttm * high, 2),
        },
        {'high': round(high, 2), 'avg': round(avg, 2), 'low': round(low, 2)},
    )


def fetch_stock(code: str, name: str | None = None) -> dict | None:
    today = now_taipei()
    today_str = today.strftime('%Y-%m-%d')
    three_y = (today - timedelta(days=365 * 3 + 10)).strftime('%Y-%m-%d')
    five_y = (today - timedelta(days=365 * 5 + 60)).strftime('%Y-%m-%d')

    # 1. Daily prices for 3 years (covers current + change + yield calc)
    prices_3y = finmind('TaiwanStockPrice', data_id=code,
                        start_date=three_y, end_date=today_str)
    if not prices_3y:
        print(f"  [{code}] no price data")
        return None
    latest = prices_3y[-1]
    prev = prices_3y[-2] if len(prices_3y) > 1 else None
    current_price = float(latest['close'])
    change = round(current_price - float(prev['close']), 2) if prev else 0
    change_pct = round(change / float(prev['close']) * 100, 2) if prev else 0

    # 2. Dividend history (5 years)
    div_data = finmind('TaiwanStockDividend', data_id=code,
                       start_date=five_y, end_date=today_str)
    by_year = defaultdict(float)
    for d in div_data:
        year = parse_year(d.get('year'))
        if year is None:
            continue
        cash = (
            float(d.get('CashEarningsDistribution') or 0)
            + float(d.get('CashStatutorySurplus') or 0)
        )
        by_year[year] += cash

    latest_year, latest_dividend = pick_latest_dividend(dict(by_year), today.year)

    # If current year's dividend is partial (less than half of previous), substitute previous year's
    # for daily yield calculation. Avoids artificially low daily yields polluting the range.
    adj_by_year = dict(by_year)
    if today.year in adj_by_year and (today.year - 1) in adj_by_year:
        cur = adj_by_year[today.year]
        prev = adj_by_year[today.year - 1]
        if prev > 0 and cur < 0.5 * prev:
            adj_by_year[today.year] = prev

    # 3. Compute daily yields for past 3 years (effective annual dividend / day's close)
    year_closes = defaultdict(list)
    daily_yields = []
    for p in prices_3y:
        try:
            year = int(p['date'][:4])
            close = float(p['close'])
            if close <= 0:
                continue
            year_closes[year].append(close)
            div = adj_by_year.get(year)
            if div and div > 0:
                daily_yields.append(div / close)
        except (KeyError, ValueError, TypeError):
            continue

    # 4. PER history (3 years; empty for ETFs without earnings)
    try:
        per_data = finmind('TaiwanStockPER', data_id=code,
                           start_date=three_y, end_date=today_str)
        pes_3y = [float(d['PER']) for d in per_data
                  if d.get('PER') is not None and float(d['PER']) > 0]
    except Exception:
        pes_3y = []

    # 5. Quarterly EPS (last 8 for YoY) — skipped for ETFs (will be empty list)
    eps_quarterly = []
    eps_ttm = None
    try:
        fs_data = finmind(
            'TaiwanStockFinancialStatements',
            data_id=code,
            start_date=(today - timedelta(days=750)).strftime('%Y-%m-%d'),
            end_date=today_str,
        )
        eps_rows = [r for r in fs_data if r.get('type') == 'EPS']
        eps_rows.sort(key=lambda x: x['date'], reverse=True)
        for r in eps_rows[:8]:
            eps_quarterly.append({
                'period': r['date'],
                'eps': round(float(r['value']), 2),
            })
        if len(eps_quarterly) >= 4:
            eps_ttm = round(sum(q['eps'] for q in eps_quarterly[:4]), 2)
        period_to_eps = {q['period']: q['eps'] for q in eps_quarterly}
        for q in eps_quarterly:
            try:
                d = datetime.strptime(q['period'], '%Y-%m-%d')
                prev_period = d.replace(year=d.year - 1).strftime('%Y-%m-%d')
                prev_eps = period_to_eps.get(prev_period)
                if prev_eps is not None and prev_eps != 0:
                    q['yoy'] = round((q['eps'] - prev_eps) / abs(prev_eps), 4)
                else:
                    q['yoy'] = None
            except Exception:
                q['yoy'] = None
    except Exception as e:
        print(f"  [{code}] EPS fetch failed: {e}")

    # 6. Compute valuations
    valuation_yield, yield_stats = compute_yield_valuation(latest_dividend, daily_yields)
    valuation_pe, pe_stats = compute_pe_valuation(eps_ttm, pes_3y)

    # 7. Per-year dividend history with avg yield
    dividend_history = []
    for year in sorted(by_year.keys(), reverse=True)[:5]:
        dividend = by_year[year]
        closes = year_closes.get(year, [])
        if closes and dividend > 0:
            avg_close = sum(closes) / len(closes)
            year_yield = dividend / avg_close
        else:
            year_yield = None
        dividend_history.append({
            'year': year,
            'cash_dividend': round(dividend, 4),
            'yield': round(year_yield, 4) if year_yield else None,
        })

    return {
        'code': code,
        'name': name,
        'updated': today.strftime('%Y-%m-%d %H:%M:%S+08:00'),
        'close_date': latest['date'],
        'current_price': current_price,
        'change': change,
        'change_pct': change_pct,
        'dividend_used': round(latest_dividend, 4),
        'dividend_year': latest_year,
        'eps_ttm': eps_ttm,
        'valuation_yield': valuation_yield,
        'yield_stats': yield_stats,
        'valuation_pe': valuation_pe,
        'pe_stats': pe_stats,
        'eps_quarterly': eps_quarterly[:4],
        'dividend_history': dividend_history,
    }


def main():
    parser = argparse.ArgumentParser(description='Fetch TW stock data and compute valuations.')
    parser.add_argument('codes', nargs='*', help='Stock codes (default: all from stocks.json)')
    args = parser.parse_args()

    with open(STOCKS_FILE, encoding='utf-8') as f:
        meta = json.load(f)

    targets = args.codes if args.codes else list(meta['tw_stocks'].keys())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {len(targets)} TW stocks (FinMind token: {'set' if TOKEN else 'none'})...")
    success = 0
    failures = []
    for code in targets:
        name = meta['tw_stocks'].get(code, {}).get('name', code)
        print(f"[{code}] {name}")
        try:
            data = fetch_stock(code, name)
            if data is None:
                failures.append(code)
                continue
            with open(OUTPUT_DIR / f'{code}.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            success += 1
            tags = []
            if data.get('valuation_yield'):
                tags.append('yield')
            if data.get('valuation_pe'):
                tags.append('pe')
            print(f"  saved (close {data['current_price']}, methods: {','.join(tags) or 'none'})")
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append(code)

    print(f"\nDone: {success}/{len(targets)} succeeded")
    if failures:
        print(f"Failed: {', '.join(failures)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
