import datetime as dt
import time

import pandas as pd
import requests

BASE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": BASE + "/option-chain",
}


class NSE:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self._warm()

    def _warm(self):
        self.s.get(BASE + "/option-chain", timeout=20)  # sets cookies

    def _get(self, path, params):
        for i in range(4):
            try:
                r = self.s.get(BASE + path, params=params, timeout=20)
                if r.status_code == 200:
                    return r.json()
            except (requests.RequestException, ValueError):
                pass
            time.sleep(2 * (i + 1))
            self._warm()
        raise RuntimeError(f"NSE request failed: {path} {params}")

    def nearest_expiry(self, symbol):
        j = self._get("/api/option-chain-contract-info", {"symbol": symbol})
        today = dt.date.today()
        dates = sorted(dt.datetime.strptime(d, "%d-%b-%Y").date() for d in j["expiryDates"])
        return next(d for d in dates if d >= today)

    def chain(self, symbol, expiry: dt.date):
        j = self._get("/api/option-chain-v3", {
            "type": "Indices", "symbol": symbol, "expiry": expiry.strftime("%d-%b-%Y")})
        rec = j["records"]
        spot = rec.get("underlyingValue")
        rows = []
        for d in rec["data"]:
            for t in ("CE", "PE"):
                x = d.get(t)
                if not x:
                    continue
                spot = spot or x.get("underlyingValue")
                rows.append(dict(
                    strike=d["strikePrice"], opt_type=t,
                    oi=x.get("openInterest", 0), oi_chg=x.get("changeinOpenInterest", 0),
                    volume=x.get("totalTradedVolume", 0), ltp=x.get("lastPrice", 0),
                    bid=x.get("bidprice", 0), ask=x.get("askPrice", 0),
                    iv_nse=x.get("impliedVolatility", 0)))
        if not rows or not spot:
            raise RuntimeError("Empty chain (market closed or payload changed)")
        return float(spot), pd.DataFrame(rows)
