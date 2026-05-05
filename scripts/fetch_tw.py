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


HIGH_PCT = 0.95  # trim top 5% of daily extremes
LOW_PCT = 0.05   # trim bottom 5%


def percentile(sorted_data, p):
    """p in [0, 1]. sorted_data must be sorted ascending. Linear interpolation."""
    if not sorted_data:
        return None
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    k = (n - 1) * p
    f = int(k)
    c = k - f
    if f + 1 >= n:
        return sorted_data[-1]
    return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c


def compute_yield_valuation(latest_dividend, yields):
    pos = sorted(y for y in yields if y and y > 0)
    if not pos or not latest_dividend:
        return None, None
    high = percentile(pos, HIGH_PCT)
    low = percentile(pos, LOW_PCT)
    avg = sum(pos) / len(pos)
    return (
        {
            'cheap': round(latest_dividend / high, 2),
            'fair': round(latest_dividend / avg, 2),
            'expensive': round(latest_dividend / low, 2),
        },
        {'high': round(high, 4), 'avg': round(avg, 4), 'low': round(low, 4)},
    )


def compute_pe_valuation(eps_ttm, pes):
    pos = sorted(p for p in pes if p and p > 0)
    if not pos or not eps_ttm or eps_ttm <= 0:
        return None, None
    high = percentile(pos, HIGH_PCT)
    low = percentile(pos, LOW_PCT)
    avg = sum(pos) / len(pos)
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

    # 3. Aggregate daily closes by year (used for yearly yield + dividend history)
    year_closes = defaultdict(list)
    for p in prices_3y:
        try:
            year = int(p['date'][:4])
            close = float(p['close'])
            if close > 0:
                year_closes[year].append(close)
        except (KeyError, ValueError, TypeError):
            continue

    # 4. PER history (3 years; empty for ETFs without earnings) — aggregate by year
    #    Also keep a date->PER lookup for the band-chart time series, and grab
    #    the latest PBR / dividend_yield rows for the screener page.
    year_pes = defaultdict(list)
    per_by_date = {}
    latest_pbr = None
    try:
        per_data = finmind('TaiwanStockPER', data_id=code,
                           start_date=three_y, end_date=today_str)
        # Sort ascending by date so the trailing iteration finds the newest PBR.
        per_data.sort(key=lambda r: r.get('date', ''))
        for d in per_data:
            try:
                y = int(d['date'][:4])
                pe = float(d.get('PER') or 0)
                pb = float(d.get('PBR') or 0)
                if pe > 0:
                    year_pes[y].append(pe)
                    per_by_date[d['date']] = pe
                if pb > 0:
                    latest_pbr = pb
            except (KeyError, ValueError, TypeError):
                continue
    except Exception:
        pass

    # 5. Last 3 trailing years (include current year if it has >=30 trading days).
    # Captures recent re-rating which "complete years only" misses (TSMC PE expanded
    # from ~18 to ~32 across 2024-2026; skipping current year understates expensive band).
    all_years = sorted(year_closes.keys(), reverse=True)
    candidate_years = []
    for y in all_years:
        if y == today.year and len(year_closes[y]) < 30:
            continue
        candidate_years.append(y)
        if len(candidate_years) >= 3:
            break

    # Use DAILY yields/PEs across the 3-year window — captures actual extremes.
    # Yearly-avg approach was too tight for re-rated stocks (TSMC: 昂貴 was 91% of
    # current price after 2024-2026 PE expansion); daily extremes track recent peaks.
    all_yields = []
    all_pes = []
    for year in candidate_years:
        closes = year_closes[year]
        if not closes:
            continue

        # Yield: use that year's dividend. For incomplete current year (no dividend yet,
        # or div < 50% of prev year), substitute previous year's annual dividend.
        div = by_year.get(year, 0)
        if year == today.year:
            prev_div = by_year.get(year - 1, 0)
            if prev_div > 0 and (div == 0 or div < 0.5 * prev_div):
                div = prev_div

        if div > 0:
            all_yields.extend(div / c for c in closes if c > 0)
        all_pes.extend(year_pes.get(year, []))

    # Aliases kept for the compute_* function signature (which expects a flat list).
    yearly_yields = all_yields
    yearly_pes = all_pes

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

    # 6. Compute valuations from yearly aggregates
    valuation_yield, yield_stats = compute_yield_valuation(latest_dividend, yearly_yields)
    valuation_pe, pe_stats = compute_pe_valuation(eps_ttm, yearly_pes)

    # 7. Build sampled price history time series for band chart.
    #    Sample every Nth trading day to keep JSON small while preserving shape.
    #    Always include first + last point so the chart spans the full window.
    SAMPLE_STRIDE = 4  # ~one point per business week
    history = []
    n_prices = len(prices_3y)
    for i, row in enumerate(prices_3y):
        if i != 0 and i != n_prices - 1 and i % SAMPLE_STRIDE != 0:
            continue
        try:
            close = float(row['close'])
            if close <= 0:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        date = row['date']
        point = {'d': date, 'c': round(close, 2)}
        # Attach PER if we have one for this date (skipped silently for ETFs).
        pe = per_by_date.get(date)
        if pe is not None:
            point['p'] = round(pe, 2)
        history.append(point)

    # 7b. Daily OHLC for the K-line chart (last ~250 trading days = 1Y).
    kline = []
    for row in prices_3y[-260:]:
        try:
            o = float(row.get('open') or 0)
            h = float(row.get('max') or row.get('high') or 0)
            lo = float(row.get('min') or row.get('low') or 0)
            c = float(row.get('close') or 0)
            v = float(row.get('Trading_Volume') or 0)
            if c <= 0 or o <= 0 or h <= 0 or lo <= 0:
                continue
        except (TypeError, ValueError):
            continue
        kline.append({
            'd': row['date'],
            'o': round(o, 2),
            'h': round(h, 2),
            'l': round(lo, 2),
            'c': round(c, 2),
            'v': int(v),
        })

    # 7c. Institutional flow for last 60 trading days (foreign/dealer/trust net).
    chips = []
    try:
        chip_start = (today - timedelta(days=90)).strftime('%Y-%m-%d')
        chip_data = finmind('TaiwanStockInstitutionalInvestorsBuySell',
                            data_id=code, start_date=chip_start, end_date=today_str)
        by_date = defaultdict(lambda: {'foreign': 0, 'dealer': 0, 'trust': 0})
        for r in chip_data:
            try:
                d = r.get('date')
                # Use a different local var so we don't shadow the outer
                # `name` (which holds the company name and is later returned).
                inst = r.get('name', '')
                buy = float(r.get('buy') or 0)
                sell = float(r.get('sell') or 0)
                net = buy - sell
            except (TypeError, ValueError):
                continue
            if not d:
                continue
            if inst.startswith('Foreign'):
                # Foreign_Investor / Foreign_Dealer_Self all roll up here
                by_date[d]['foreign'] += net
            elif inst.startswith('Investment_Trust') or inst.startswith('Trust'):
                by_date[d]['trust'] += net
            elif inst.startswith('Dealer'):
                by_date[d]['dealer'] += net
        for d in sorted(by_date.keys())[-60:]:
            b = by_date[d]
            total = b['foreign'] + b['dealer'] + b['trust']
            chips.append({
                'd': d,
                'f': round(b['foreign']),
                'tr': round(b['trust']),
                'de': round(b['dealer']),
                't': round(total),
            })
    except Exception as e:
        print(f"  [{code}] chips fetch failed: {e}")

    # 8. Per-year dividend history with avg yield
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
        'price_history': history,
        'kline': kline,
        'chips': chips,
        'pbr': round(latest_pbr, 2) if latest_pbr is not None else None,
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
            # Preserve fields populated by other fetchers (notably `adr` from
            # fetch_us.py, which only re-runs once a day) so re-running fetch_tw
            # mid-day doesn't blank out cross-pipeline state.
            target_path = OUTPUT_DIR / f'{code}.json'
            if target_path.exists():
                try:
                    with open(target_path, encoding='utf-8') as f:
                        prev = json.load(f)
                    for k in ('adr',):
                        if k in prev and k not in data:
                            data[k] = prev[k]
                except Exception:
                    pass
            with open(target_path, 'w', encoding='utf-8') as f:
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

    # Update last_updated.json (preserve other keys like 'us' if present)
    last_updated_file = ROOT / 'data' / 'last_updated.json'
    existing = {}
    if last_updated_file.exists():
        try:
            with open(last_updated_file, encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing['tw'] = now_taipei().strftime('%Y-%m-%d %H:%M:%S+08:00')
    with open(last_updated_file, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    # Partial failures: warn but still allow commit/push of successful data.
    # Total failure: exit 1 so workflow surfaces the issue and we don't push empty results.
    if failures:
        msg = f"Failed: {', '.join(failures)}"
        print(msg)
        print(f"::warning::TW fetch partial failure ({len(failures)}/{len(targets)}): {', '.join(failures)}")
        if success == 0:
            sys.exit(1)


if __name__ == '__main__':
    main()
