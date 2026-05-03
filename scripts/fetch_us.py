#!/usr/bin/env python3
"""Fetch US ADR closing prices + USD/TWD rate, attach ADR comparison to TW JSON.

Reads adr_mapping from data/stocks.json, gets latest ADR close + FX from yfinance,
computes implied TW price + premium %, writes back into data/tw/{tw_code}.json.

Run AFTER fetch_tw.py (needs the per-stock TW JSONs to exist).

Usage:
    python scripts/fetch_us.py
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
STOCKS_FILE = ROOT / 'data' / 'stocks.json'
TW_DIR = ROOT / 'data' / 'tw'
FX_FILE = ROOT / 'data' / 'fx.json'

TAIPEI = timezone(timedelta(hours=8))


def get_close(symbol: str):
    """Return dict {close, close_date, change, change_pct} or None."""
    t = yf.Ticker(symbol)
    h = t.history(period='5d', auto_adjust=False)
    if h.empty:
        return None
    closes = [float(c) for c in h['Close'].tolist()]
    dates = [str(d.date()) for d in h.index]
    last = closes[-1]
    prev = closes[-2] if len(closes) > 1 else None
    if prev:
        change = round(last - prev, 2)
        change_pct = round((last - prev) / prev * 100, 2)
    else:
        change = 0.0
        change_pct = 0.0
    return {
        'close': round(last, 4),
        'close_date': dates[-1],
        'change': change,
        'change_pct': change_pct,
    }


def main():
    parser = argparse.ArgumentParser(description='Fetch US ADR + FX, attach to TW JSONs.')
    parser.parse_args()

    with open(STOCKS_FILE, encoding='utf-8') as f:
        meta = json.load(f)

    # --- USD/TWD ---
    fx_info = get_close('USDTWD=X')
    if fx_info is None:
        print('FX rate fetch failed')
        sys.exit(1)
    fx = fx_info['close']
    fx_date = fx_info['close_date']
    print(f"USD/TWD = {fx:.3f} ({fx_date})")
    with open(FX_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'usd_twd': round(fx, 4),
            'date': fx_date,
            'updated': datetime.now(TAIPEI).strftime('%Y-%m-%d %H:%M:%S+08:00'),
        }, f, ensure_ascii=False, indent=2)

    # --- ADR data ---
    success = 0
    for adr, info in meta['adr_mapping'].items():
        tw_code = info['tw_code']
        ratio = info['ratio']
        tw_file = TW_DIR / f'{tw_code}.json'
        print(f"[{adr}] -> {tw_code}")

        if not tw_file.exists():
            print(f"  TW data missing ({tw_file.name}), skip")
            continue

        adr_info = get_close(adr)
        if adr_info is None:
            print('  ADR close fetch failed')
            continue
        adr_close = adr_info['close']

        with open(tw_file, encoding='utf-8') as f:
            tw_data = json.load(f)
        tw_price = tw_data.get('current_price')
        if not tw_price:
            print('  TW price missing, skip')
            continue

        implied = adr_close * fx / ratio
        premium = (implied - tw_price) / tw_price * 100

        tw_data['adr'] = {
            'symbol': adr,
            'close': round(adr_close, 2),
            'close_date': adr_info['close_date'],
            'change': adr_info['change'],
            'change_pct': adr_info['change_pct'],
            'ratio': ratio,
            'fx_rate': round(fx, 4),
            'implied_tw_price': round(implied, 2),
            'premium_pct': round(premium, 2),
        }

        with open(tw_file, 'w', encoding='utf-8') as f:
            json.dump(tw_data, f, ensure_ascii=False, indent=2)
        print(f"  ADR ${adr_close:.2f} ({adr_info['change']:+.2f}, {adr_info['change_pct']:+.2f}%) -> implied {implied:.2f} (TW {tw_price:.2f}, premium {premium:+.2f}%)")
        success += 1

    print(f"\nDone: {success}/{len(meta['adr_mapping'])} ADRs processed")

    # Update last_updated.json (preserve 'tw' if present)
    last_updated_file = ROOT / 'data' / 'last_updated.json'
    existing = {}
    if last_updated_file.exists():
        try:
            with open(last_updated_file, encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing['us'] = datetime.now(TAIPEI).strftime('%Y-%m-%d %H:%M:%S+08:00')
    with open(last_updated_file, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
