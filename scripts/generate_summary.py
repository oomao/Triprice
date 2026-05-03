#!/usr/bin/env python3
"""Generate concise per-stock summary text using Anthropic Claude API.

Reads each data/tw/{code}.json, builds a compact factual prompt from the
estimation/valuation fields, calls Claude, and writes the result back as
the `summary` field. Skips stocks where the underlying numbers haven't
changed since the last run (fingerprint check) to save API spend.

Env:
    ANTHROPIC_API_KEY  required
    SUMMARY_MODEL      optional (default: claude-haiku-4-5-20251001)

Usage:
    python scripts/generate_summary.py                     # all stocks
    python scripts/generate_summary.py 2330 0050           # specific
    python scripts/generate_summary.py --force             # ignore fingerprint
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TW_DIR = ROOT / 'data' / 'tw'

API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
MODEL = os.environ.get('SUMMARY_MODEL', 'claude-haiku-4-5-20251001')
TAIPEI = timezone(timedelta(hours=8))

PROMPT_VERSION = 'v1'  # bump if the prompt template changes — invalidates fingerprints


def fingerprint(d: dict) -> str:
    """Hash the data subset that influences the summary, plus prompt version.
    If this hash matches the stored one, no need to regenerate."""
    payload = {
        'v': PROMPT_VERSION,
        'price': d.get('current_price'),
        'change_pct': d.get('change_pct'),
        'eps_ttm': d.get('eps_ttm'),
        'dividend_used': d.get('dividend_used'),
        'valuation_yield': d.get('valuation_yield'),
        'valuation_pe': d.get('valuation_pe'),
        'yield_stats_avg': (d.get('yield_stats') or {}).get('avg'),
        'pe_stats_avg': (d.get('pe_stats') or {}).get('avg'),
        'last_eps_yoy': (d.get('eps_quarterly') or [{}])[0].get('yoy') if d.get('eps_quarterly') else None,
        'adr_premium_pct': (d.get('adr') or {}).get('premium_pct'),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def position_pct(price, bands):
    if not price or not bands:
        return None
    cheap, expensive = bands.get('cheap'), bands.get('expensive')
    if cheap is None or expensive is None or expensive == cheap:
        return None
    return round(((price - cheap) / (expensive - cheap)) * 100)


def build_prompt(d: dict) -> str:
    """Return the user message — compact, factual, no editorial."""
    parts = []
    parts.append(f"代號 {d.get('code')} {d.get('name') or ''}")
    parts.append(f"現價 {d.get('current_price')} 元")
    if d.get('change_pct') is not None:
        parts.append(f"今日漲跌 {d['change_pct']:+.2f}%")
    if d.get('eps_ttm') is not None:
        parts.append(f"近 4 季 EPS 合計 {d['eps_ttm']}")
    if d.get('dividend_used'):
        parts.append(f"最新年度現金股利 {d['dividend_used']}")

    yv = d.get('valuation_yield')
    if yv:
        pos = position_pct(d.get('current_price'), yv)
        line = f"殖利率法估值 便宜 {yv['cheap']} / 合理 {yv['fair']} / 昂貴 {yv['expensive']}"
        if pos is not None:
            line += f"（目前位置 {pos}%）"
        parts.append(line)

    pv = d.get('valuation_pe')
    if pv:
        pos = position_pct(d.get('current_price'), pv)
        line = f"PE 法估值 便宜 {pv['cheap']} / 合理 {pv['fair']} / 昂貴 {pv['expensive']}"
        if pos is not None:
            line += f"（目前位置 {pos}%）"
        parts.append(line)

    if d.get('eps_quarterly'):
        latest = d['eps_quarterly'][0]
        if latest.get('yoy') is not None:
            parts.append(f"最新季度 EPS YoY {latest['yoy'] * 100:+.1f}%")

    adr = d.get('adr')
    if adr and adr.get('premium_pct') is not None:
        parts.append(f"ADR 溢價 {adr['premium_pct']:+.2f}%")

    return ' | '.join(parts)


SYSTEM_PROMPT = """你是台股資料整理助理。你的任務是把使用者提供的客觀資料壓縮成 2-3 句的繁體中文摘要。

嚴格規則：
1. 只能根據使用者提供的資料寫，不能編造、不能引用未提供的數字
2. 不能給投資建議、不能用「建議買進/賣出/持有」等字眼
3. 不能用情緒誇張用語（暴漲、噴出、神級、絕佳⋯）
4. 用平實敘述，類似一段事實摘要
5. 整段不超過 120 字
6. 結構：第一句點出公司類型/估值狀態（用 PE 法為主），第二句點出 1 個值得注意的觀察（EPS 趨勢、殖利率、ADR 溢價等），可選第三句補充風險提示
7. 不要寫前言、不要寫結語，直接出摘要本文"""


def call_claude(user_text: str) -> str:
    """Call Anthropic Messages API. Returns the model's reply text."""
    if not API_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY not set')
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': MODEL,
            'max_tokens': 400,
            'system': SYSTEM_PROMPT,
            'messages': [{'role': 'user', 'content': user_text}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    j = resp.json()
    blocks = j.get('content', [])
    text = ''.join(b.get('text', '') for b in blocks if b.get('type') == 'text').strip()
    return text


def process(code: str, force: bool = False) -> bool:
    path = TW_DIR / f'{code}.json'
    if not path.exists():
        print(f"  [{code}] missing JSON, skip")
        return False
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    fp = fingerprint(d)
    existing = d.get('summary') or {}
    if not force and existing.get('fingerprint') == fp and existing.get('text'):
        print(f"  [{code}] fingerprint match, skip")
        return False
    prompt = build_prompt(d)
    try:
        text = call_claude(prompt)
    except Exception as e:
        print(f"  [{code}] FAILED {e}")
        return False
    if not text:
        print(f"  [{code}] empty response, skip")
        return False
    d['summary'] = {
        'text': text,
        'generated_at': datetime.now(TAIPEI).strftime('%Y-%m-%d %H:%M:%S+08:00'),
        'model': MODEL,
        'fingerprint': fp,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"  [{code}] {text[:60]}...")
    return True


def main():
    parser = argparse.ArgumentParser(description='Generate per-stock summaries via Anthropic API.')
    parser.add_argument('codes', nargs='*')
    parser.add_argument('--force', action='store_true', help='Regenerate even if fingerprint matches.')
    parser.add_argument('--throttle', type=float, default=0.5, help='Seconds between API calls.')
    args = parser.parse_args()

    if not API_KEY:
        print('ANTHROPIC_API_KEY not set — cannot proceed.')
        sys.exit(1)

    if args.codes:
        targets = args.codes
    else:
        targets = [p.stem for p in sorted(TW_DIR.glob('*.json'))]

    print(f"Generating summaries for {len(targets)} stocks (model: {MODEL})...")
    n_updated = 0
    for code in targets:
        try:
            if process(code, force=args.force):
                n_updated += 1
                time.sleep(args.throttle)
        except Exception as e:
            print(f"  [{code}] uncaught: {e}")
    print(f"\nUpdated {n_updated}/{len(targets)} summaries.")


if __name__ == '__main__':
    main()
