import io
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", layout="wide")
st.title("International Cost of Capital")
st.caption("Stage 2 · Industry betas from Aswath Damodaran · Colombia lecture example")

BETA_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_industries():
    response = requests.get(BETA_URL, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    raw = pd.read_excel(io.BytesIO(response.content), sheet_name="Industry Averages", header=None, engine="xlrd")
    header_index = None
    for i in range(min(25, len(raw))):
        row = [str(x).strip().lower() for x in raw.iloc[i].tolist()]
        if any("industry name" in x for x in row) and any("unlevered beta" in x for x in row):
            header_index = i
            break
    if header_index is None:
        raise ValueError("Could not identify the industry/beta columns in Damodaran's spreadsheet.")
    header = [str(x).strip() for x in raw.iloc[header_index].tolist()]
    industry_col = next(i for i, x in enumerate(header) if "industry name" in x.lower())
    beta_col = next(i for i, x in enumerate(header) if "unlevered beta" in x.lower() and "cash" not in x.lower())
    table = raw.iloc[header_index + 1:, [industry_col, beta_col]].copy()
    table.columns = ["Industry", "Unlevered beta"]
    table["Unlevered beta"] = pd.to_numeric(table["Unlevered beta"], errors="coerce")
    table = table.dropna().copy()
    table["Industry"] = table["Industry"].astype(str).str.strip()
    table = table[(table["Industry"] != "") & (table["Unlevered beta"] >= 0)]
    table = table.drop_duplicates("Industry").sort_values("Industry")
    if len(table) < 20:
        raise ValueError("The downloaded industry table is unexpectedly small.")
    return table.reset_index(drop=True), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


with st.sidebar:
    st.header("Project assumptions")
    if st.button("Refresh industry data"):
        fetch_industries.clear()
        st.rerun()

try:
    industries, fetched_at = fetch_industries()
    names = industries["Industry"].tolist()
    preferred = "Software (System & Application)"
    default_index = names.index(preferred) if preferred in names else next(
        (i for i, n in enumerate(names) if "software" in n.lower()), 0
    )
    with st.sidebar:
        industry = st.selectbox("Industry", names, index=default_index)
    beta_fetched = float(industries.set_index("Industry").loc[industry, "Unlevered beta"])
    st.success(f"Industry betas loaded from Damodaran (fetched {fetched_at}).")
except Exception as exc:
    industry = "Software (System & Application)"
    beta_fetched = 0.80
    st.warning("Live industry download unavailable. Beta is an illustrative placeholder (0.80), not verified live data. Enable the manual beta override or retry refresh.")
    st.caption(f"Fetch detail: {exc}")

with st.sidebar:
    beta_override = st.toggle("Override unlevered beta", value=False)
    beta_manual = st.number_input("Manual unlevered beta", min_value=0.0, value=0.80, step=0.05,
                                  disabled=not beta_override)
    beta_u = beta_manual if beta_override else beta_fetched
    st.caption(f"Beta used: {beta_u:.4f}" + (" (manual)" if beta_override else " (downloaded or fallback)"))
    debt_pct = st.slider("Debt financing (%)", 0, 95, 30)
    tax_pct = st.number_input("Project corporate tax rate (%)", min_value=0.0, max_value=100.0, value=35.0, step=0.5)
    erp_pct = st.number_input("Equity risk premium (%)", min_value=0.0, value=6.5, step=0.25)
    us_yield_pct = st.number_input("US 10-year yield (%)", value=4.0, step=0.1)
    foreign_yield_pct = st.number_input("Colombia 10-year yield (%)", value=12.0, step=0.1)
    usd_spread_pct = st.number_input("USD BBB borrowing spread (percentage points)", min_value=0.0, value=1.5, step=0.1)
    foreign_override = st.toggle("Override COP borrowing spread", value=False)
    foreign_spread_pct = st.number_input("COP borrowing spread (percentage points)", min_value=0.0,
                                          value=1.5, step=0.1, disabled=not foreign_override)


def calculate(beta_u, d, tax, erp, rf_us, rf_foreign, spread_us, spread_foreign=None):
    beta_e = beta_u * (1 + (1 - tax) * d / (1 - d))
    re_us = rf_us + beta_e * erp
    rd_us = rf_us + spread_us
    factor = (1 + rf_foreign) / (1 + rf_us)
    re_foreign = (1 + re_us) * factor - 1
    spread_f = spread_us * factor if spread_foreign is None else spread_foreign
    rd_foreign = rf_foreign + spread_f
    wacc_us = (1 - d) * re_us + d * rd_us * (1 - tax)
    wacc_foreign = (1 - d) * re_foreign + d * rd_foreign * (1 - tax)
    return dict(beta_e=beta_e, re_us=re_us, rd_us=rd_us, re_foreign=re_foreign,
                rd_foreign=rd_foreign, spread_foreign=spread_f, wacc_us=wacc_us,
                wacc_foreign=wacc_foreign, factor=factor)

r = calculate(beta_u, debt_pct / 100, tax_pct / 100, erp_pct / 100,
              us_yield_pct / 100, foreign_yield_pct / 100, usd_spread_pct / 100,
              foreign_spread_pct / 100 if foreign_override else None)

st.subheader("Results")
a, b = st.columns(2)
with a:
    st.markdown("### United States (USD)")
    st.metric("Cost of equity", f"{100 * r['re_us']:.4f}%")
    st.metric("Pretax cost of debt", f"{100 * r['rd_us']:.4f}%")
    st.metric("WACC", f"{100 * r['wacc_us']:.4f}%")
with b:
    st.markdown("### Colombia (COP)")
    st.metric("Cost of equity", f"{100 * r['re_foreign']:.4f}%")
    st.metric("Pretax cost of debt", f"{100 * r['rd_foreign']:.4f}%")
    st.metric("WACC", f"{100 * r['wacc_foreign']:.4f}%")

with st.expander("Show formulas and intermediate calculations"):
    st.latex(r"\beta_E=\beta_U\left[1+(1-T)\frac{d}{1-d}\right]")
    st.write(f"Levered beta: {r['beta_e']:.6f}")
    st.latex(r"R_{e,USD}=R_{f,USD}+\beta_E ERP")
    st.latex(r"1+R_{e,COP}=(1+R_{e,USD})\frac{1+R_{f,COP}}{1+R_{f,USD}}")
    st.latex(r"s_{COP}=s_{USD}\frac{1+R_{f,COP}}{1+R_{f,USD}}\quad\mathrm{(unless\ overridden)}")
    st.write(f"Yield conversion factor: {r['factor']:.7f}; COP spread: {100*r['spread_foreign']:.4f}%")
    st.latex(r"WACC=(1-d)R_e+dR_d(1-T)")

st.caption("Source for industry beta: [Damodaran U.S. industry betas](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls). Other inputs are illustrative lecture values at this stage, not current market data.")
