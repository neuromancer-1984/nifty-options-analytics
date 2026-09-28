import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from sqlalchemy import text

import db

st.set_page_config(page_title="Options Chain Analytics", layout="wide")


@st.cache_resource
def eng():
    return db.engine()


@st.cache_data(ttl=60)
def q(sql, **p):
    df = pd.read_sql(text(sql), eng(), params=p)
    for c in df.columns:
        if df[c].dtype == object:
            try:
                df[c] = pd.to_numeric(df[c])
            except (ValueError, TypeError):
                pass
    return df


sym = st.sidebar.selectbox("Index", ["NIFTY", "BANKNIFTY"])
snaps = q("SELECT snapshot_id, ts, expiry FROM snapshots WHERE symbol=:s ORDER BY ts DESC LIMIT 600", s=sym)
if snaps.empty:
    st.info("No data yet. Run `python collector.py --once` during market hours.")
    st.stop()
snaps["label"] = pd.to_datetime(snaps.ts, utc=True).dt.tz_convert("Asia/Kolkata").dt.strftime("%d %b %H:%M")
pick = st.sidebar.selectbox("Snapshot", snaps.label.tolist(), index=0)
sid = int(snaps.loc[snaps.label == pick, "snapshot_id"].iloc[0])

chain = q("SELECT * FROM chain WHERE snapshot_id=:i", i=sid).sort_values("strike")
m = q("SELECT * FROM metrics WHERE snapshot_id=:i", i=sid).iloc[0]
hist = q("SELECT * FROM metrics WHERE symbol=:s AND ts >= now() - interval '180 days' ORDER BY ts", s=sym)
hist["ts"] = pd.to_datetime(hist.ts, utc=True).dt.tz_convert("Asia/Kolkata")
ce, pe = chain[chain.opt_type == "CE"], chain[chain.opt_type == "PE"]
spot = float(m.spot)

st.title(f"{sym} Options Chain Analytics")
st.caption(f"Expiry {m.expiry} | snapshot {pick} IST")
c = st.columns(6)
c[0].metric("Spot", f"{spot:,.1f}")
c[1].metric("PCR (OI)", f"{m.pcr_oi:.2f}")
c[2].metric("Max pain", f"{m.max_pain:,.0f}")
c[3].metric("ATM IV", f"{m.atm_iv:.1f}%")
c[4].metric("Support (max put OI)", f"{m.support:,.0f}")
c[5].metric("Resistance (max call OI)", f"{m.resistance:,.0f}")

t1, t2, t3, t4, t5 = st.tabs(["Open Interest", "Volatility", "Greeks & GEX", "Trends", "ML Forecast"])

with t1:
    f = go.Figure([go.Bar(x=ce.strike, y=ce.oi, name="Call OI", marker_color="#ef5350"),
                   go.Bar(x=pe.strike, y=pe.oi, name="Put OI", marker_color="#26a69a")])
    f.add_vline(x=spot, line_dash="dash", annotation_text="spot")
    f.update_layout(barmode="group", title="OI by strike", height=420)
    st.plotly_chart(f, use_container_width=True)
    f = go.Figure([go.Bar(x=ce.strike, y=ce.oi_chg, name="Call ΔOI", marker_color="#ef5350"),
                   go.Bar(x=pe.strike, y=pe.oi_chg, name="Put ΔOI", marker_color="#26a69a")])
    f.update_layout(barmode="group", title="Change in OI (day) by strike", height=380)
    st.plotly_chart(f, use_container_width=True)

with t2:
    f = go.Figure([go.Scatter(x=ce.strike, y=ce.iv, name="Call IV", mode="lines+markers"),
                   go.Scatter(x=pe.strike, y=pe.iv, name="Put IV", mode="lines+markers")])
    f.add_vline(x=spot, line_dash="dash")
    f.update_layout(title="IV smile (computed via Black-Scholes, %)", height=400)
    st.plotly_chart(f, use_container_width=True)
    f = make_subplots(specs=[[{"secondary_y": True}]])
    f.add_trace(go.Scatter(x=hist.ts, y=hist.atm_iv, name="ATM IV"), secondary_y=False)
    f.add_trace(go.Scatter(x=hist.ts, y=hist.iv_skew, name="Put-Call skew"), secondary_y=True)
    f.update_layout(title="ATM IV and skew over time", height=380)
    st.plotly_chart(f, use_container_width=True)

with t3:
    g = st.selectbox("Greek", ["delta", "gamma", "theta", "vega"])
    f = go.Figure([go.Scatter(x=ce.strike, y=ce[g], name=f"Call {g}"),
                   go.Scatter(x=pe.strike, y=pe[g], name=f"Put {g}")])
    f.add_vline(x=spot, line_dash="dash")
    f.update_layout(height=380, title=f"{g} by strike")
    st.plotly_chart(f, use_container_width=True)
    gex = (ce.set_index("strike").gamma * ce.set_index("strike").oi
           - pe.set_index("strike").gamma * pe.set_index("strike").oi).fillna(0) * spot ** 2 * 0.01
    f = go.Figure(go.Bar(x=gex.index, y=gex.values, marker_color=["#26a69a" if v > 0 else "#ef5350" for v in gex.values]))
    f.update_layout(title="Gamma exposure by strike (assumes dealers long calls / short puts)", height=380)
    st.plotly_chart(f, use_container_width=True)

with t4:
    f = make_subplots(rows=2, cols=1, shared_xaxes=True, specs=[[{}], [{"secondary_y": True}]])
    f.add_trace(go.Scatter(x=hist.ts, y=hist.spot, name="Spot"), row=1, col=1)
    f.add_trace(go.Scatter(x=hist.ts, y=hist.max_pain, name="Max pain"), row=1, col=1)
    f.add_trace(go.Scatter(x=hist.ts, y=hist.pcr_oi, name="PCR (OI)"), row=2, col=1)
    f.add_trace(go.Scatter(x=hist.ts, y=hist.pcr_vol, name="PCR (Vol)"), row=2, col=1)
    f.update_layout(height=600, title="Spot, max pain and PCR (last 7 days)")
    st.plotly_chart(f, use_container_width=True)

with t5:
    pr = q("SELECT * FROM predictions WHERE symbol=:s ORDER BY ts DESC LIMIT 200", s=sym)
    if pr.empty:
        st.info("Model activates after ~3 trading days of collected snapshots.")
    else:
        last = pr.iloc[0]
        a, b, c2 = st.columns(3)
        a.metric(f"P(up next trading day)", f"{float(last.prob_up):.0%}")
        b.metric("Walk-forward CV accuracy", f"{float(last.cv_acc):.1%}")
        c2.metric("Majority-class baseline", f"{float(last.baseline_acc):.1%}")
        st.caption("Gradient boosting on PCR, IV, skew, GEX, max-pain/support/resistance distances. "
                   "If CV accuracy is not above baseline, treat the signal as noise. Not financial advice.")
        pr["ts"] = pd.to_datetime(pr.ts, utc=True).dt.tz_convert("Asia/Kolkata")
        st.plotly_chart(go.Figure(go.Scatter(x=pr.ts, y=pr.prob_up.astype(float))).update_layout(
            title="P(up) history", height=350), use_container_width=True)
