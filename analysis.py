import numpy as np


def _iv_near(t, target):
    t = t.dropna(subset=["iv"])
    if t.empty:
        return np.nan
    return float(t["iv"].iloc[np.abs(t.index.to_numpy(float) - target).argmin()])


def compute_metrics(df, spot):
    ce = df[df.opt_type == "CE"].set_index("strike")
    pe = df[df.opt_type == "PE"].set_index("strike")
    strikes = np.array(sorted(df.strike.unique()), dtype=float)
    coi = ce.oi.reindex(strikes).fillna(0).to_numpy(float)
    poi = pe.oi.reindex(strikes).fillna(0).to_numpy(float)
    pain = [(coi * np.maximum(k - strikes, 0)).sum() + (poi * np.maximum(strikes - k, 0)).sum()
            for k in strikes]
    atm = strikes[np.abs(strikes - spot).argmin()]
    cg, pg = (ce.gamma * ce.oi).sum(), (pe.gamma * pe.oi).sum()
    return dict(
        pcr_oi=float(poi.sum() / coi.sum()) if coi.sum() else None,
        pcr_vol=float(pe.volume.sum() / ce.volume.sum()) if ce.volume.sum() else None,
        max_pain=float(strikes[int(np.argmin(pain))]),
        atm_strike=float(atm),
        atm_iv=float(np.nanmean([_iv_near(ce, spot), _iv_near(pe, spot)])),
        iv_skew=float(_iv_near(pe, spot * 0.97) - _iv_near(ce, spot * 1.03)),
        call_oi_total=int(coi.sum()), put_oi_total=int(poi.sum()),
        net_gex=float((cg - pg) * spot ** 2 * 0.01),
        support=float(strikes[int(poi.argmax())]),
        resistance=float(strikes[int(coi.argmax())]),
    )
