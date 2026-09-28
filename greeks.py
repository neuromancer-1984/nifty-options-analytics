import numpy as np
from scipy.special import ndtr

from config import RISK_FREE


def _d1d2(S, K, T, r, s):
    v = s * np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * s * s) * T) / v
    return d1, d1 - v


def bs_price(S, K, T, r, s, cp):
    d1, d2 = _d1d2(S, K, T, r, s)
    return cp * (S * ndtr(cp * d1) - K * np.exp(-r * T) * ndtr(cp * d2))


def implied_vol(P, S, K, T, r, cp):
    """Vectorised bisection: robust, ~60 iterations over the whole chain at once."""
    lo, hi = np.full_like(P, 1e-3), np.full_like(P, 5.0)
    for _ in range(60):
        mid = (lo + hi) / 2
        too_high = bs_price(S, K, T, r, mid, cp) > P
        hi = np.where(too_high, mid, hi)
        lo = np.where(too_high, lo, mid)
    iv = (lo + hi) / 2
    intrinsic = np.maximum(cp * (S - K * np.exp(-r * T)), 0)
    iv[(P <= intrinsic + 1e-6) | (P < 0.5)] = np.nan
    return iv


def enrich(df, spot, T, r=RISK_FREE):
    """Adds iv (in %), delta, gamma, theta (per day), vega (per 1 vol pt)."""
    T = max(T, 1e-5)
    K = df["strike"].to_numpy(float)
    cp = np.where(df["opt_type"] == "CE", 1.0, -1.0)
    P = df["ltp"].to_numpy(float)
    S = np.full_like(K, spot)
    with np.errstate(all="ignore"):
        s = implied_vol(P, S, K, T, r, cp)
        d1, d2 = _d1d2(S, K, T, r, s)
        pdf = np.exp(-0.5 * d1 ** 2) / np.sqrt(2 * np.pi)
        out = df.copy()
        out["iv"] = s * 100
        out["delta"] = cp * ndtr(cp * d1)
        out["gamma"] = pdf / (S * s * np.sqrt(T))
        out["theta"] = (-(S * pdf * s) / (2 * np.sqrt(T))
                        - cp * r * K * np.exp(-r * T) * ndtr(cp * d2)) / 365
        out["vega"] = S * pdf * np.sqrt(T) / 100
    return out
