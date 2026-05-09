#!/usr/bin/env python3
"""Predict next-day TW open / intraday high / intraday low for headline ADR stocks.

Pipeline (per stock):
  1. Fetch ADR + SOX + USD/TWD history (yfinance), align to TW kline OHLC dates
  2. Build cleaned features per day:
       adr_local = adr_usd_change − fx_change             (FX leak removed)
       adr_alpha = adr_local − rolling_90d_β · sox_change  (sector beta removed)
       sox_change                                         (raw)
       premium_z = (premium − rolling_60d_median) / MAD   (de-drift)
  3. Event-day mask: ex-dividend (FinMind), TW limit-hit, long-gap (>3d),
     stale ADR (volume = 0). Excluded from training.
  4. Fit RidgeCV on cleaned features → 3 separate models for
     {open_gap, max_gain, max_loss} = next-day {open, high, low} vs today's close
  5. Conformal 80% prediction interval from calibration residuals
  6. Walk-forward over the last 30 trading days: refit per day → predict that
     day → compare to actual; report MAE, RMSE, coverage, hit rate
  7. Enforce consistency: high_pred ≥ open_pred ≥ low_pred (clip if violated)
  8. Write data/adr_prediction.json

Usage:
    python scripts/predict_open_high_low.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
import yfinance as yf
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
STOCKS_FILE = ROOT / 'data' / 'stocks.json'
TW_DIR = ROOT / 'data' / 'tw'
ADR_SIGNAL = ROOT / 'data' / 'adr_signal.json'
OUTPUT = ROOT / 'data' / 'adr_prediction.json'

TAIPEI = timezone(timedelta(hours=8))
LOOKBACK_DAYS = 730
WALK_FORWARD_WINDOW = 30
PREMIUM_BASELINE_WINDOW = 60
SOX_BETA_WINDOW = 90

FINMIND_BASE = 'https://api.finmindtrade.com/api/v4/data'
FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN', '')


# --- data fetch ---------------------------------------------------------

def fetch_yf(symbol, start):
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
                'v': float(row.get('Volume', 0) or 0),
            }
        except (KeyError, ValueError, TypeError):
            continue
    return out


def fetch_close_series(symbol, start):
    return {d: row['c'] for d, row in fetch_yf(symbol, start).items()}


def fetch_ex_dividend_dates(stock_id, start, end):
    """FinMind TaiwanStockDividend → set of ex-dividend dates for stock_id."""
    params = {
        'dataset': 'TaiwanStockDividend',
        'data_id': stock_id,
        'start_date': start,
        'end_date': end,
    }
    if FINMIND_TOKEN:
        params['token'] = FINMIND_TOKEN
    try:
        r = requests.get(FINMIND_BASE, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:
        print(f"  ex-div fetch fail {stock_id}: {e}", file=sys.stderr)
        return set()
    if j.get('status') != 200:
        print(f"  ex-div status {stock_id}: {j.get('msg')}", file=sys.stderr)
        return set()
    dates = set()
    for row in j.get('data', []):
        d = row.get('CashExDividendTradingDate') or row.get('cash_ex_dividend_trading_date')
        if d:
            dates.add(d)
        d2 = row.get('StockExDividendTradingDate') or row.get('stock_ex_dividend_trading_date')
        if d2:
            dates.add(d2)
    return dates


# --- rolling stats ------------------------------------------------------

def rolling_median(arr, window):
    out = np.full(len(arr), np.nan)
    for i in range(window - 1, len(arr)):
        out[i] = np.nanmedian(arr[i - window + 1: i + 1])
    return out


def rolling_mad(arr, window):
    out = np.full(len(arr), np.nan)
    for i in range(window - 1, len(arr)):
        chunk = arr[i - window + 1: i + 1]
        med = np.nanmedian(chunk)
        out[i] = np.nanmedian(np.abs(chunk - med))
    return out


def rolling_beta(y, x, window):
    out = np.full(len(y), np.nan)
    for i in range(window - 1, len(y)):
        yc = np.asarray(y[i - window + 1: i + 1], dtype=float)
        xc = np.asarray(x[i - window + 1: i + 1], dtype=float)
        mask = ~(np.isnan(yc) | np.isnan(xc))
        if mask.sum() < 5:
            continue
        yc, xc = yc[mask], xc[mask]
        var = np.var(xc)
        if var > 0:
            out[i] = np.cov(yc, xc, bias=True)[0, 1] / var
    return out


# --- date-aligned helpers -----------------------------------------------

def latest_before(date_str, sorted_dates):
    """Return latest date < date_str from sorted_dates list, or None."""
    for d in reversed(sorted_dates):
        if d < date_str:
            return d
    return None


# --- feature build ------------------------------------------------------

def build_features(tw_kline, adr_hist, sox_hist, fx_hist, ex_div_dates):
    """For each TW trading day, build cleaned features + targets aligned to T+1.

    Returns list of dicts (chronological).
    """
    tw_dates = sorted(tw_kline.keys())
    fx_keys = sorted(fx_hist.keys())
    sox_keys = sorted(sox_hist.keys())
    adr_keys = sorted(adr_hist.keys())

    rows = []
    for i, t in enumerate(tw_dates):
        tw = tw_kline[t]
        t_next = tw_dates[i + 1] if i + 1 < len(tw_dates) else None

        adr = adr_hist.get(t)
        sox = sox_hist.get(t)
        fx_t = fx_hist.get(t)
        adr_prev_d = latest_before(t, adr_keys)
        sox_prev_d = latest_before(t, sox_keys)
        fx_prev_d = latest_before(t, fx_keys)
        adr_prev = adr_hist.get(adr_prev_d) if adr_prev_d else None
        sox_prev = sox_hist.get(sox_prev_d) if sox_prev_d else None
        fx_prev = fx_hist.get(fx_prev_d) if fx_prev_d else None

        if not (adr and sox and fx_t and adr_prev and sox_prev and fx_prev):
            continue

        adr_chg_usd = (adr['c'] / adr_prev['c'] - 1) * 100 if adr_prev['c'] else None
        sox_chg = (sox / sox_prev - 1) * 100 if sox_prev else None
        fx_chg = (fx_t / fx_prev - 1) * 100 if fx_prev else None
        if adr_chg_usd is None or sox_chg is None or fx_chg is None:
            continue

        adr_local = adr_chg_usd - fx_chg
        implied = adr['c'] * fx_t  # ratio applied later in premium calc
        # Note: premium needs ratio, we compute later when we have it

        if t_next:
            tw_n = tw_kline[t_next]
            open_gap = (tw_n['o'] - tw['c']) / tw['c'] * 100
            max_gain = (tw_n['h'] - tw['c']) / tw['c'] * 100
            max_loss = (tw_n['l'] - tw['c']) / tw['c'] * 100
            calendar_gap = (datetime.strptime(t_next, '%Y-%m-%d')
                            - datetime.strptime(t, '%Y-%m-%d')).days
        else:
            open_gap = max_gain = max_loss = None
            calendar_gap = None

        # TW intraday change (used for limit-hit detection)
        tw_change_pct = None
        if i > 0:
            prev_close = tw_kline[tw_dates[i - 1]]['c']
            if prev_close:
                tw_change_pct = (tw['c'] / prev_close - 1) * 100

        rows.append({
            'date': t,
            't_next': t_next,
            'tw_close': tw['c'],
            'tw_change_pct': tw_change_pct,
            'adr_close': adr['c'],
            'adr_volume': adr.get('v', 0),
            'adr_chg_usd': adr_chg_usd,
            'fx_chg': fx_chg,
            'fx_rate': fx_t,
            'sox_chg': sox_chg,
            'adr_local': adr_local,
            'implied_no_ratio': implied,  # fill ratio later
            'open_gap': open_gap,
            'max_gain': max_gain,
            'max_loss': max_loss,
            'calendar_gap': calendar_gap,
            'is_ex_div': t in ex_div_dates,
            't_next_is_ex_div': t_next in ex_div_dates if t_next else False,
        })

    return rows


def attach_derived(rows, ratio):
    """Add premium, premium_z, sox_beta, adr_alpha to each row."""
    for r in rows:
        r['implied_tw_price'] = r['implied_no_ratio'] / ratio
        r['premium'] = (r['implied_tw_price'] - r['tw_close']) / r['tw_close'] * 100

    premium_arr = np.array([r['premium'] for r in rows], dtype=float)
    sox_arr = np.array([r['sox_chg'] for r in rows], dtype=float)
    adr_local_arr = np.array([r['adr_local'] for r in rows], dtype=float)

    prem_med = rolling_median(premium_arr, PREMIUM_BASELINE_WINDOW)
    prem_mad = rolling_mad(premium_arr, PREMIUM_BASELINE_WINDOW)
    prem_z = (premium_arr - prem_med) / np.where(prem_mad > 0, prem_mad, np.nan)

    beta = rolling_beta(adr_local_arr, sox_arr, SOX_BETA_WINDOW)
    adr_alpha = adr_local_arr - beta * sox_arr

    for i, r in enumerate(rows):
        r['premium_z'] = float(prem_z[i]) if not np.isnan(prem_z[i]) else None
        r['sox_beta'] = float(beta[i]) if not np.isnan(beta[i]) else None
        r['adr_alpha'] = float(adr_alpha[i]) if not np.isnan(adr_alpha[i]) else None


# --- event mask ---------------------------------------------------------

def is_event_day(row):
    """True if this day's ADR→TW transmission is structurally broken."""
    # Limit-up/down (TW 10% cap)
    if row.get('tw_change_pct') is not None and abs(row['tw_change_pct']) > 9.5:
        return True
    # Long calendar gap (multi-day overnight)
    if row.get('calendar_gap') and row['calendar_gap'] > 3:
        return True
    # Stale ADR (no US trading or zero volume)
    if row.get('adr_volume') == 0:
        return True
    # Today is ex-dividend (TW will gap mechanically)
    if row.get('is_ex_div'):
        return True
    # Tomorrow is ex-dividend (target gap is contaminated)
    if row.get('t_next_is_ex_div'):
        return True
    return False


# --- modeling -----------------------------------------------------------

FEATURES = ('adr_alpha', 'sox_chg', 'premium_z')


def features_of(row):
    return [row['adr_alpha'], row['sox_chg'], row['premium_z']]


def fit_ridge_conformal(rows, target):
    """Fit RidgeCV with chronological 75% train / 25% calib split.
    Returns dict {model, scaler, q80, n_train, n_calib, coef, intercept} or None."""
    eligible = [r for r in rows
                if r['adr_alpha'] is not None
                and r['premium_z'] is not None
                and r.get(target) is not None
                and not is_event_day(r)]
    if len(eligible) < 50:
        return None

    X = np.array([features_of(r) for r in eligible])
    y = np.array([r[target] for r in eligible])

    n_train = int(len(X) * 0.75)
    X_t, X_c = X[:n_train], X[n_train:]
    y_t, y_c = y[:n_train], y[n_train:]
    if len(X_c) < 10:
        return None

    scaler = StandardScaler().fit(X_t)
    Xs_t = scaler.transform(X_t)
    Xs_c = scaler.transform(X_c)
    model = RidgeCV(alphas=np.logspace(-3, 2, 20)).fit(Xs_t, y_t)
    calib_pred = model.predict(Xs_c)
    q80 = float(np.quantile(np.abs(y_c - calib_pred), 0.80))

    return {
        'model': model,
        'scaler': scaler,
        'q80': q80,
        'n_train': len(X_t),
        'n_calib': len(X_c),
        'coef': {
            'adr_alpha': float(model.coef_[0]),
            'sox_chg':   float(model.coef_[1]),
            'premium_z': float(model.coef_[2]),
        },
        'intercept': float(model.intercept_),
    }


def predict_with(fitted, feature_row):
    if any(feature_row.get(f) is None for f in FEATURES):
        return None
    X = np.array([features_of(feature_row)])
    Xs = fitted['scaler'].transform(X)
    pt = float(fitted['model'].predict(Xs)[0])
    return {
        'point_pct': pt,
        'lo80_pct': pt - fitted['q80'],
        'hi80_pct': pt + fitted['q80'],
    }


def walk_forward(rows, target, window=WALK_FORWARD_WINDOW):
    """For each of the last `window` eligible days, retrain on prior data,
    predict that day, compare to actual."""
    eligible = [(i, r) for i, r in enumerate(rows)
                if r['adr_alpha'] is not None
                and r['premium_z'] is not None
                and r.get(target) is not None
                and not is_event_day(r)]
    if len(eligible) < 80:
        return []

    out = []
    start = max(50, len(eligible) - window)
    for j in range(start, len(eligible)):
        train = [r for _, r in eligible[:j]]
        if len(train) < 50:
            continue
        X = np.array([features_of(r) for r in train])
        y = np.array([r[target] for r in train])
        nt = int(len(X) * 0.75)
        X_t, X_c = X[:nt], X[nt:]
        y_t, y_c = y[:nt], y[nt:]
        if len(X_c) < 10:
            continue
        scaler = StandardScaler().fit(X_t)
        Xs_t = scaler.transform(X_t)
        Xs_c = scaler.transform(X_c)
        model = RidgeCV(alphas=np.logspace(-3, 2, 15)).fit(Xs_t, y_t)
        calib_pred = model.predict(Xs_c)
        q80 = float(np.quantile(np.abs(y_c - calib_pred), 0.80))

        _, today_row = eligible[j]
        Xs_today = scaler.transform(np.array([features_of(today_row)]))
        pt = float(model.predict(Xs_today)[0])
        actual = today_row[target]
        out.append({
            'date': today_row['date'],
            'predicted_pct': round(pt, 3),
            'actual_pct': round(actual, 3),
            'error_pct': round(pt - actual, 3),
            'lo80_pct': round(pt - q80, 3),
            'hi80_pct': round(pt + q80, 3),
            'in_interval': abs(pt - actual) <= q80,
            'hit_direction': (pt >= 0) == (actual >= 0),
        })
    return out


def summarize_walk_forward(records):
    if not records:
        return None
    n = len(records)
    errs = np.array([r['error_pct'] for r in records])
    widths = np.array([r['hi80_pct'] - r['lo80_pct'] for r in records])
    return {
        'n': n,
        'mae_pct':  round(float(np.mean(np.abs(errs))), 3),
        'rmse_pct': round(float(np.sqrt(np.mean(errs**2))), 3),
        'bias_pct': round(float(np.mean(errs)), 3),
        'coverage_pct':            round(sum(r['in_interval']    for r in records) / n * 100, 1),
        'hit_rate_pct':            round(sum(r['hit_direction']  for r in records) / n * 100, 1),
        'avg_interval_width_pct':  round(float(np.mean(widths)), 3),
    }


# --- consistency clip ---------------------------------------------------

def enforce_consistency(predictions):
    """Ensure max_gain >= open_gap >= max_loss for both point and interval bounds.
    Mutates in place. Returns True if any clip was applied."""
    clipped = False
    if 'max_gain' in predictions and 'open_gap' in predictions:
        if predictions['max_gain']['point_pct'] < predictions['open_gap']['point_pct']:
            predictions['max_gain']['point_pct'] = predictions['open_gap']['point_pct']
            clipped = True
    if 'open_gap' in predictions and 'max_loss' in predictions:
        if predictions['open_gap']['point_pct'] < predictions['max_loss']['point_pct']:
            predictions['max_loss']['point_pct'] = predictions['open_gap']['point_pct']
            clipped = True
    # Also enforce on interval ENDPOINTS (high.lo >= open.lo, low.hi <= open.hi)
    if 'max_gain' in predictions and 'open_gap' in predictions:
        if predictions['max_gain']['hi80_pct'] < predictions['open_gap']['hi80_pct']:
            predictions['max_gain']['hi80_pct'] = predictions['open_gap']['hi80_pct']
            clipped = True
    if 'open_gap' in predictions and 'max_loss' in predictions:
        if predictions['max_loss']['lo80_pct'] > predictions['open_gap']['lo80_pct']:
            predictions['max_loss']['lo80_pct'] = predictions['open_gap']['lo80_pct']
            clipped = True
    return clipped


# --- main ---------------------------------------------------------------

def process_stock(tw_code, adr_sym, ratio, tw_meta, tw_kline,
                  adr_hist, sox_hist, fx_hist, ex_div_dates,
                  today_signal, fx_today, sox_today_close):
    name = tw_meta.get('name', tw_code)

    rows = build_features(tw_kline, adr_hist, sox_hist, fx_hist, ex_div_dates)
    if not rows:
        return None
    attach_derived(rows, ratio)

    # Replace last row with live "today" if signal is fresher than last kline
    sig_date = today_signal.get('tw_close_date') if today_signal else None
    if sig_date and rows[-1]['date'] != sig_date and today_signal:
        prev = rows[-1]
        adr_chg_usd = today_signal.get('adr_change_pct', 0)
        tw_change_pct = today_signal.get('tw_change_pct', 0)
        # Find prev FX (last entry in fx_hist before today)
        fx_keys = sorted(fx_hist.keys())
        prev_fx_d = latest_before(sig_date, fx_keys) or fx_keys[-1]
        prev_fx = fx_hist[prev_fx_d]
        fx_chg = (fx_today / prev_fx - 1) * 100 if prev_fx else 0.0
        adr_local = adr_chg_usd - fx_chg
        implied = today_signal['adr_close'] * fx_today / ratio
        premium = (implied - today_signal['tw_price']) / today_signal['tw_price'] * 100

        # Recompute premium_z from last 60 historical premiums
        recent_prem = np.array([r['premium'] for r in rows[-PREMIUM_BASELINE_WINDOW:]],
                               dtype=float)
        if len(recent_prem) >= 30:
            med = float(np.median(recent_prem))
            mad = float(np.median(np.abs(recent_prem - med)))
            premium_z = (premium - med) / mad if mad > 0 else 0.0
        else:
            premium_z = None

        # SOX change today
        sox_keys = sorted(sox_hist.keys())
        prev_sox_d = latest_before(sig_date, sox_keys) or sox_keys[-1]
        prev_sox = sox_hist[prev_sox_d]
        sox_chg_today = (sox_today_close / prev_sox - 1) * 100 if prev_sox else 0.0

        beta = prev['sox_beta'] if prev['sox_beta'] is not None else 1.0
        adr_alpha = adr_local - beta * sox_chg_today

        today_row = {
            'date': sig_date,
            't_next': None,
            'tw_close': today_signal['tw_price'],
            'tw_change_pct': tw_change_pct,
            'adr_close': today_signal['adr_close'],
            'adr_volume': today_signal.get('adr_volume', 1),
            'adr_chg_usd': adr_chg_usd,
            'fx_chg': fx_chg,
            'fx_rate': fx_today,
            'sox_chg': sox_chg_today,
            'adr_local': adr_local,
            'implied_tw_price': implied,
            'premium': premium,
            'premium_z': premium_z,
            'sox_beta': beta,
            'adr_alpha': adr_alpha,
            'open_gap': None,
            'max_gain': None,
            'max_loss': None,
            'calendar_gap': None,
            'is_ex_div': sig_date in ex_div_dates,
            't_next_is_ex_div': False,
        }
        rows.append(today_row)

    # HNHPF stale detection (Hon Hai only)
    last_row = rows[-1]
    hnhpf_stale = False
    if adr_sym == 'HNHPF':
        # Stale if today's volume = 0 OR close didn't change vs prev
        prev_adr = adr_hist.get(latest_before(last_row['date'], sorted(adr_hist.keys())))
        if last_row.get('adr_volume', 0) == 0:
            hnhpf_stale = True
        elif prev_adr and last_row['adr_close'] == prev_adr['c']:
            hnhpf_stale = True

    # Fit models for each target
    fitted = {}
    walk_records = {}
    for tgt in ('open_gap', 'max_gain', 'max_loss'):
        f = fit_ridge_conformal(rows, tgt)
        if f:
            fitted[tgt] = f
            walk_records[tgt] = walk_forward(rows, tgt)

    if not fitted:
        return None

    # Predict today
    predictions = {}
    for tgt, f in fitted.items():
        p = predict_with(f, last_row)
        if p:
            tw_close = last_row['tw_close']
            p['point_price'] = round(tw_close * (1 + p['point_pct'] / 100), 2)
            p['lo80_price']  = round(tw_close * (1 + p['lo80_pct'] / 100), 2)
            p['hi80_price']  = round(tw_close * (1 + p['hi80_pct'] / 100), 2)
            p['crosses_zero'] = p['lo80_pct'] < 0 < p['hi80_pct']
            p['point_pct'] = round(p['point_pct'], 3)
            p['lo80_pct']  = round(p['lo80_pct'], 3)
            p['hi80_pct']  = round(p['hi80_pct'], 3)
            predictions[tgt] = p

    consistency_violated = enforce_consistency(predictions)
    # Re-derive prices after any clip
    for tgt, p in predictions.items():
        tw_close = last_row['tw_close']
        p['point_price'] = round(tw_close * (1 + p['point_pct'] / 100), 2)
        p['lo80_price']  = round(tw_close * (1 + p['lo80_pct'] / 100), 2)
        p['hi80_price']  = round(tw_close * (1 + p['hi80_pct'] / 100), 2)
        p['point_pct'] = round(p['point_pct'], 3)
        p['lo80_pct']  = round(p['lo80_pct'], 3)
        p['hi80_pct']  = round(p['hi80_pct'], 3)

    out = {
        'name': name,
        'adr': adr_sym,
        'ratio': ratio,
        'tw_close': last_row['tw_close'],
        'tw_close_date': last_row['date'],
        'adr_close': last_row.get('adr_close'),
        'adr_close_date': last_row['date'],
        'fx_rate': last_row.get('fx_rate'),
        'implied_tw_price': round(last_row.get('implied_tw_price', 0), 2)
                            if last_row.get('implied_tw_price') else None,
        'signals_cleaned': {
            'adr_alpha_pct': round(last_row['adr_alpha'], 3) if last_row['adr_alpha'] is not None else None,
            'sox_chg_pct':   round(last_row['sox_chg'], 3),
            'sox_beta':      round(last_row['sox_beta'], 3) if last_row['sox_beta'] is not None else None,
            'premium_z':     round(last_row['premium_z'], 3) if last_row['premium_z'] is not None else None,
            'premium_raw_pct': round(last_row['premium'], 3),
            'fx_chg_pct':    round(last_row['fx_chg'], 3),
            'adr_chg_usd_pct': round(last_row['adr_chg_usd'], 3),
            'is_event_day':  is_event_day(last_row),
            'is_ex_div':     last_row.get('is_ex_div', False),
            'hnhpf_stale':   hnhpf_stale,
        },
        'predictions': predictions,
        'consistency_violated': consistency_violated,
        'model_quality': {
            tgt: {
                'n_train': fitted[tgt]['n_train'],
                'n_calib': fitted[tgt]['n_calib'],
                'q80_pct': round(fitted[tgt]['q80'], 3),
                'coef':    {k: round(v, 4) for k, v in fitted[tgt]['coef'].items()},
                'intercept': round(fitted[tgt]['intercept'], 4),
            } for tgt in fitted
        },
        'walk_forward_30d': {
            tgt: {
                'summary': summarize_walk_forward(walk_records[tgt]),
                'daily': walk_records[tgt],
            } for tgt in walk_records
        },
    }
    return out


def main():
    with open(STOCKS_FILE, encoding='utf-8') as f:
        meta = json.load(f)
    with open(ADR_SIGNAL, encoding='utf-8') as f:
        signal = json.load(f)

    today_by_code = {a['tw_code']: a for a in signal['adrs']}
    fx_today = signal.get('fx_rate')
    sox_today_close = signal.get('sox', {}).get('close')

    headline = [(info['tw_code'], adr_sym, info)
                for adr_sym, info in meta['adr_mapping'].items()
                if info.get('dashboard')]

    start = (datetime.now(TAIPEI) - timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    end = datetime.now(TAIPEI).strftime('%Y-%m-%d')
    print(f"Lookback start: {start}", file=sys.stderr)

    print('Fetching SOX + USD/TWD history...', file=sys.stderr)
    sox_hist = fetch_close_series('^SOX', start)
    fx_hist = fetch_close_series('USDTWD=X', start)
    print(f"  SOX: {len(sox_hist)} days · FX: {len(fx_hist)} days", file=sys.stderr)

    stocks_out = {}
    for tw_code, adr_sym, info in headline:
        ratio = info['ratio']
        tw_meta = meta['tw_stocks'].get(tw_code, {})
        tw_file = TW_DIR / f'{tw_code}.json'
        if not tw_file.exists():
            print(f"[{tw_code}] no kline", file=sys.stderr)
            continue
        with open(tw_file, encoding='utf-8') as f:
            tw_data = json.load(f)
        tw_kline = {row['d']: row for row in tw_data.get('kline', [])}
        if not tw_kline:
            continue

        kline_start = sorted(tw_kline.keys())[0]
        adr_start = (datetime.strptime(kline_start, '%Y-%m-%d')
                     - timedelta(days=10)).strftime('%Y-%m-%d')
        print(f"[{tw_code} {tw_meta.get('name', '')}] fetching ADR {adr_sym}...",
              file=sys.stderr)
        adr_hist = fetch_yf(adr_sym, adr_start)
        print(f"  ADR days: {len(adr_hist)}", file=sys.stderr)

        ex_div_dates = fetch_ex_dividend_dates(tw_code, kline_start, end)
        print(f"  ex-div dates: {len(ex_div_dates)}", file=sys.stderr)

        sig = today_by_code.get(tw_code)
        result = process_stock(tw_code, adr_sym, ratio, tw_meta, tw_kline,
                               adr_hist, sox_hist, fx_hist, ex_div_dates,
                               sig, fx_today, sox_today_close)
        if result:
            stocks_out[tw_code] = result
            wf = result.get('walk_forward_30d', {}).get('open_gap', {}).get('summary', {})
            print(f"  {tw_meta.get('name', tw_code)} 開盤: "
                  f"MAE {wf.get('mae_pct')}% · cov {wf.get('coverage_pct')}% · "
                  f"hit {wf.get('hit_rate_pct')}%", file=sys.stderr)

    payload = {
        'updated': datetime.now(TAIPEI).strftime('%Y-%m-%d %H:%M:%S+08:00'),
        'method': 'Ridge + Conformal 80% interval',
        'lookback_days': LOOKBACK_DAYS,
        'walk_forward_window_days': WALK_FORWARD_WINDOW,
        'features_explained': {
            'adr_alpha': 'ADR USD return − FX change − rolling 90d β · SOX change（剝離 FX 與 sector beta 的純個股 alpha）',
            'sox_chg':   'SOX 指數當日漲跌 %',
            'premium_z': '(今日溢價 − 60d rolling median) / MAD（去掉結構性溢價偏移）',
        },
        'targets_explained': {
            'open_gap': '隔日 TW 開盤 vs 今日 TW 收盤（%）',
            'max_gain': '隔日 TW 盤中最高 vs 今日收盤（%）',
            'max_loss': '隔日 TW 盤中最低 vs 今日收盤（%）',
        },
        'stocks': stocks_out,
    }
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {OUTPUT}", file=sys.stderr)


if __name__ == '__main__':
    main()
