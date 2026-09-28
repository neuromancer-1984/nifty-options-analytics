import datetime as dt
import io
import zipfile

import pandas as pd
import requests

URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d}_F_0000.csv.zip"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


class NoData(Exception):
    pass


def load_day(day: dt.date) -> pd.DataFrame:
    r = requests.get(URL.format(d=day.strftime("%Y%m%d")), headers=HEAD, timeout=60)
    if r.status_code == 404:
        raise NoData(str(day))
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        return pd.read_csv(z.open(z.namelist()[0]))


def extract(bhav, symbol, day):
    d = bhav[(bhav.FinInstrmTp == "IDO") & (bhav.TckrSymb == symbol)].copy()
    if d.empty:
        raise NoData(f"{symbol} {day}")
    d["exp"] = pd.to_datetime(d.XpryDt).dt.date
    expiry = min(e for e in d.exp.unique() if e >= day)
    d = d[d.exp == expiry]
    spot = float(d.UndrlygPric.dropna().iloc[0])
    out = pd.DataFrame(dict(
        strike=d.StrkPric.astype(float), opt_type=d.OptnTp,
        oi=d.OpnIntrst.fillna(0).astype(int), oi_chg=d.ChngInOpnIntrst.fillna(0).astype(int),
        volume=d.TtlTradgVol.fillna(0).astype(int), ltp=d.SttlmPric.astype(float),
        bid=0.0, ask=0.0, iv_nse=0.0))
    return expiry, spot, out