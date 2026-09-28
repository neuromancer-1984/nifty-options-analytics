"""Direction classifier: will spot be higher ML_HORIZON snapshots from now?
Features come from options-chain metrics (PCR, IV, skew, GEX, max-pain/support/resistance distance).
Evaluated with walk-forward CV against a majority-class baseline. Expect modest edge; report honestly."""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import db
from config import INTERVAL_MIN, ML_HORIZON, ML_MIN_ROWS

ML_HORIZON = 1        # next trading day
ML_MIN_ROWS = 40      # ~2 months of daily snapshots

FEATS = ["pcr_oi", "pcr_vol", "atm_iv", "iv_skew", "gex_n", "mp_dist", "sup_dist", "res_dist",
         "d_pcr", "d_iv", "ret_1", "ret_3"]


def build(symbol):
    m = pd.read_sql("SELECT * FROM metrics WHERE symbol=%(s)s ORDER BY ts",
                    db.engine(), params={"s": symbol}, parse_dates=["ts"])
    for c in m.columns.difference(["ts", "symbol", "expiry"]):
        m[c] = pd.to_numeric(m[c], errors="coerce")
    m["gex_n"] = m.net_gex / (m.call_oi_total + m.put_oi_total)
    m["mp_dist"] = (m.spot - m.max_pain) / m.spot
    m["sup_dist"] = (m.spot - m.support) / m.spot
    m["res_dist"] = (m.resistance - m.spot) / m.spot
    m["d_pcr"], m["d_iv"] = m.pcr_oi.diff(), m.atm_iv.diff()
    m["ret_1"], m["ret_3"] = m.spot.pct_change(1), m.spot.pct_change(3)
    ist = m.ts.dt.tz_convert("Asia/Kolkata")
    m["tod"] = ist.dt.hour + ist.dt.minute / 60
    m["fut_spot"] = m.spot.shift(-ML_HORIZON)
    gap = m.ts.shift(-ML_HORIZON) - m.ts
    m["y"] = np.where(gap <= pd.Timedelta(days=5),
                      (m.fut_spot > m.spot).astype(float), np.nan)
    return m


def run(symbol):
    m = build(symbol)
    latest = m.iloc[[-1]]
    train = m.dropna(subset=FEATS + ["y"])
    if len(train) < ML_MIN_ROWS or latest[FEATS].isna().any(axis=None):
        return None
    X, y = train[FEATS], train.y.astype(int)
    model = make_pipeline(StandardScaler(),
                          GradientBoostingClassifier(n_estimators=150, max_depth=3,
                                                     learning_rate=0.05, subsample=0.8, random_state=0))
    cv = cross_val_score(model, X, y, cv=TimeSeriesSplit(5), scoring="accuracy").mean()
    baseline = max(y.mean(), 1 - y.mean())
    model.fit(X, y)
    p = float(model.predict_proba(latest[FEATS])[0, 1])
    db.insert_prediction(latest.ts.iloc[0].to_pydatetime(), symbol, ML_HORIZON * 1440,
                         p, float(cv), float(baseline), int(len(train)))
    return p, cv, baseline


if __name__ == "__main__":
    from config import SYMBOLS
    for s in SYMBOLS:
        print(s, run(s))
