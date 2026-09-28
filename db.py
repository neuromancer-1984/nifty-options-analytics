import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

CHAIN_COLS = ["strike", "opt_type", "oi", "oi_chg", "volume", "ltp", "bid", "ask",
              "iv_nse", "iv", "delta", "gamma", "theta", "vega"]
METRIC_COLS = ["pcr_oi", "pcr_vol", "max_pain", "atm_strike", "atm_iv", "iv_skew",
               "call_oi_total", "put_oi_total", "net_gex", "support", "resistance"]


def db_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    import streamlit as st
    return st.secrets["DATABASE_URL"]


def engine():
    return create_engine(db_url(), pool_pre_ping=True)


def _clean(v):
    if v is None or pd.isna(v):
        return None
    return v.item() if hasattr(v, "item") else v


def init_schema():
    with psycopg2.connect(db_url()) as c, c.cursor() as cur:
        cur.execute(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())


def insert_snapshot(ts, symbol, expiry, spot, chain_df, metrics):
    with psycopg2.connect(db_url()) as c, c.cursor() as cur:
        cur.execute("DELETE FROM snapshots WHERE symbol=%s AND (ts AT TIME ZONE 'Asia/Kolkata')::date=%s",
            (symbol, ts.date()))
        cur.execute("""INSERT INTO snapshots (ts, symbol, expiry, spot) VALUES (%s,%s,%s,%s)
                       ON CONFLICT DO NOTHING RETURNING snapshot_id""", (ts, symbol, expiry, spot))
        row = cur.fetchone()
        if not row:
            return None
        sid = row[0]
        rows = [(sid, *[_clean(v) for v in r]) for r in chain_df[CHAIN_COLS].itertuples(index=False)]
        execute_values(cur, f"INSERT INTO chain (snapshot_id, {','.join(CHAIN_COLS)}) VALUES %s", rows)
        cur.execute(
            f"INSERT INTO metrics (snapshot_id, ts, symbol, expiry, spot, {','.join(METRIC_COLS)}) "
            f"VALUES (%s,%s,%s,%s,%s,{','.join(['%s'] * len(METRIC_COLS))})",
            (sid, ts, symbol, expiry, spot, *[_clean(metrics[k]) for k in METRIC_COLS]))
        return sid


def insert_prediction(ts, symbol, horizon_min, prob_up, cv_acc, baseline_acc, n_train):
    with psycopg2.connect(db_url()) as c, c.cursor() as cur:
        cur.execute("""INSERT INTO predictions (ts, symbol, horizon_min, prob_up, cv_acc, baseline_acc, n_train)
                       VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (ts, symbol, horizon_min, prob_up, cv_acc, baseline_acc, n_train))
