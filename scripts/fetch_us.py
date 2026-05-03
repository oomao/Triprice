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
    """Return (close, date_str) of most recent trading day, or (None, None)."""
    t = yf.Ticker(symbol)
    h = t.history(period='5d', auto_adjust=False)
    if h.empty:
        return None, None
    last = h.tail(1)
    return float(last['Close'].iloc[0]), str(last.index[0].date())


def main():
    parser = argparse.ArgumentParser(description='Fetch US ADR + FX, attach to TW JSONs.')
    parser.parse_args()

    with open(STOCKS_FILE, encoding='utf-8') as f:
        meta = json.load(f)

    # --- USD/TWD ---
    fx, fx_date = get_close('USDTWD=X')
    if fx is None:
        print('FX rate fetch failed')
        sys.exit(1)
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

        adr_close, adr_date = get_close(adr)
        if adr_close is None:
            print('  ADR close fetch failed')
            continue

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
            'close_date': adr_date,
            'ratio': ratio,
            'fx_rate': round(fx, 4),
            'implied_tw_price': round(implied, 2),
            'premium_pct': round(premium, 2),
        }

        with open(tw_file, 'w', encoding='utf-8') as f:
            json.dump(tw_data, f, ensure_ascii=False, indent=2)
        print(f"  ADR ${adr_close:.2f} -> implied {implied:.2f} (TW {tw_price:.2f}, premium {premium:+.2f}%)")
        success += 1

    print(f"\nDone: {success}/{len(meta['adr_mapping'])} ADRs processed")


if __name__ == '__main__':
    main()
