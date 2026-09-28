CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL,
  symbol TEXT NOT NULL,
  expiry DATE NOT NULL,
  spot NUMERIC NOT NULL,
  UNIQUE (ts, symbol, expiry)
);
CREATE TABLE IF NOT EXISTS chain (
  snapshot_id BIGINT NOT NULL REFERENCES snapshots ON DELETE CASCADE,
  strike NUMERIC NOT NULL,
  opt_type CHAR(2) NOT NULL,
  oi BIGINT, oi_chg BIGINT, volume BIGINT,
  ltp NUMERIC, bid NUMERIC, ask NUMERIC,
  iv_nse NUMERIC, iv NUMERIC,
  delta NUMERIC, gamma NUMERIC, theta NUMERIC, vega NUMERIC,
  PRIMARY KEY (snapshot_id, strike, opt_type)
);
CREATE TABLE IF NOT EXISTS metrics (
  snapshot_id BIGINT PRIMARY KEY REFERENCES snapshots ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL, symbol TEXT NOT NULL, expiry DATE NOT NULL, spot NUMERIC NOT NULL,
  pcr_oi NUMERIC, pcr_vol NUMERIC, max_pain NUMERIC, atm_strike NUMERIC,
  atm_iv NUMERIC, iv_skew NUMERIC, call_oi_total BIGINT, put_oi_total BIGINT,
  net_gex NUMERIC, support NUMERIC, resistance NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_metrics_sym_ts ON metrics (symbol, ts);
CREATE TABLE IF NOT EXISTS predictions (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL, symbol TEXT NOT NULL, horizon_min INT NOT NULL,
  prob_up NUMERIC, cv_acc NUMERIC, baseline_acc NUMERIC, n_train INT,
  UNIQUE (ts, symbol, horizon_min)
);
