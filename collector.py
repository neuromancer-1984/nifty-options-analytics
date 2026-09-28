"""python collector.py --init | --once [--date YYYY-MM-DD] | --backfill N"""
import argparse
import datetime as dt
import time
import traceback

import analysis, db, greeks, ml
import fetch_bhav as fb
from config import IST, SYMBOLS, STRIKE_BAND


def run_day(day):
    bhav = fb.load_day(day)
    ts = dt.datetime.combine(day, dt.time(15, 30), tzinfo=IST)
    for sym in SYMBOLS:
        expiry, spot, df = fb.extract(bhav, sym, day)
        df = df[(df.strike > spot * (1 - STRIKE_BAND)) & (df.strike < spot * (1 + STRIKE_BAND))]
        exp_dt = dt.datetime.combine(expiry, dt.time(15, 30), tzinfo=IST)
        T = (exp_dt - ts).total_seconds() / (365 * 24 * 3600)
        df = greeks.enrich(df, spot, T)
        m = analysis.compute_metrics(df, spot)
        sid = db.insert_snapshot(ts, sym, expiry, spot, df, m)
        print(f"{day} {sym} spot={spot} pcr={m['pcr_oi']:.2f} atm_iv={m['atm_iv']:.1f} snapshot={sid}")


def train():
    for sym in SYMBOLS:
        try:
            print("ml", sym, ml.run(sym))
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--backfill", type=int, default=0)
    a = ap.parse_args()
    if not (a.init or a.once or a.backfill):
        ap.print_help()
        raise SystemExit("Pass one of: --init, --once, --backfill N")
    today = dt.datetime.now(IST).date()
    if a.init:
        db.init_schema()
        print("schema ready")
    if a.once:
        day = dt.date.fromisoformat(a.date) if a.date else today
        try:
            run_day(day)
            train()
        except fb.NoData:
            print(f"No bhavcopy for {day} (holiday, weekend or not published yet)")
    if a.backfill:
        for n in range(a.backfill, -1, -1):
            day = today - dt.timedelta(days=n)
            if day.weekday() >= 5:
                continue
            try:
                run_day(day)
            except fb.NoData:
                print(f"{day} no data (holiday?)")
            except Exception:
                traceback.print_exc()
            time.sleep(1)
        train()