import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

CHAIN_COLS = ["strike", "opt_type", "oi", "oi_chg", "volume", "ltp", "bid", "ask",
              "iv_nse", "iv", "delta", "gamma", "theta", "vega"]
METRIC_COLS = ["pcr_oi", "pcr_vol", "max_pain", "atm_strike", "atm_iv", "iv_skew",
               "call_oi_total", "put_oi_total", "net_gex", "support", "resistance"]


def db_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        import streamlit as st
        url = st.secrets["DATABASE_URL"]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(db_url(), pool_pre_ping=True)
    return _engine


def _clean(v):
    if v is None or pd.isna(v):
        return None
    return v.item() if hasattr(v, "item") else v


def init_schema():
    sql = open(os.path.join(os.path.dirname(__file__), "schema.sql")).read()
    with engine().begin() as c:
        for stmt in filter(None, (s.strip() for s in sql.split(";"))):
            c.execute(text(stmt))


def insert_snapshot(ts, symbol, expiry, spot, chain_df, metrics):
    with engine().begin() as c:
        row = c.execute(text("""INSERT INTO snapshots (ts, symbol, expiry, spot)
                                 VALUES (:ts,:symbol,:expiry,:spot)
                                 ON CONFLICT DO NOTHING RETURNING snapshot_id"""),
                        dict(ts=ts, symbol=symbol, expiry=expiry, spot=spot)).fetchone()
        if not row:
            return None
        sid = row[0]
        rows = [dict(sid=sid, **{k: _clean(v) for k, v in zip(CHAIN_COLS, r)})
                for r in chain_df[CHAIN_COLS].itertuples(index=False)]
        c.execute(text(f"""INSERT INTO chain (snapshot_id, {','.join(CHAIN_COLS)})
                           VALUES (:sid, {','.join(':' + k for k in CHAIN_COLS)})"""), rows)
        c.execute(text(f"""INSERT INTO metrics (snapshot_id, ts, symbol, expiry, spot, {','.join(METRIC_COLS)})
                           VALUES (:sid,:ts,:symbol,:expiry,:spot,
                                   {','.join(':' + k for k in METRIC_COLS)})"""),
                  dict(sid=sid, ts=ts, symbol=symbol, expiry=expiry, spot=spot,
                       **{k: _clean(metrics[k]) for k in METRIC_COLS}))
        return sid


def insert_prediction(ts, symbol, horizon_min, prob_up, cv_acc, baseline_acc, n_train):
    with engine().begin() as c:
        c.execute(text("""INSERT INTO predictions (ts, symbol, horizon_min, prob_up, cv_acc, baseline_acc, n_train)
                          VALUES (:ts,:symbol,:h,:p,:cv,:b,:n) ON CONFLICT DO NOTHING"""),
                  dict(ts=ts, symbol=symbol, h=horizon_min, p=prob_up, cv=cv_acc, b=baseline_acc, n=n_train))