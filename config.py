from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SYMBOLS = ["NIFTY", "BANKNIFTY"]
RISK_FREE = 0.065          # approx India 91d T-bill / repo
STRIKE_BAND = 0.07         # keep strikes within +/-7% of spot
INTERVAL_MIN = 5           # collector cadence (minutes)
ML_HORIZON = 6             # predict direction 6 snapshots ahead (= 30 min)
ML_MIN_ROWS = 200          # min labelled rows before ML runs (~3 trading days)
