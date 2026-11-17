import io
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", layout="wide")
st.title("International Cost of Capital")
st.caption("Stage 3 · Select a country, tax rate and 10-year government yields")

# Tax fallback is from Professor Rebelo's 2026 lecture, slide 550.
# Never label fallback rates as live OECD downloads.
TAX_FALLBACK = {"United States":25.5,"Colombia":35.0,"Canada":26.0,"United Kingdom":25.0,
 "Germany":30.1,"France":36.1,"Japan":29.7,"Australia":30.0,"India":25.2,
 "Mexico":30.0,"Poland":19.0,"Switzerland":19.5,"China":25.0,"Ireland":12.5,
 "Brazil":34.0,"Netherlands":25.8,"Italy":27.8,"Spain":25.0,"Sweden":20.6,
 "Norway":22.0,"Denmark":22.0,"South Korea":27.5,"Portugal":29.5,"Singapore":17.0}
# Lecture snapshot, dated Nov 6, 2026, NOT live yields.
YIELD_FALLBACK = {"United States":4.9,"Colombia":12.8,"Canada":3.7,"United Kingdom":5.2,
 "Germany":3.3,"France":4.8,"Japan":2.6,"Australia":5.0,"India":7.2,
 "Mexico":9.1,"Poland":6.2,"Switzerland":0.4,"China":1.6,"Portugal":3.7}
TE_SLUGS = {"United States":"united-states","United Kingdom":"united-kingdom",
 "South Korea":"south-korea"}
OECD_URL = "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html"
BONDS_URL = "https://tradingeconomics.com/bonds"

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_oecd_tax_table():
    # OECD 2024 table has complex multi-row headers; only accept clearly identified
    # country/rate columns. If layout changes, fail safely rather than guess.
    tables = pd.read_html(OECD_URL)
    found = {}
    for df in tables:
        if len(df) < 10: continue
        df.columns = [" ".join(map(str, c)) if isinstance(c,tuple) else str(c) for c in df.columns]
        cols = list(df.columns)
        name_cols = [c for c in cols if any(w in c.lower() for w in ('jurisdiction','country','economy'))]
        rate_cols = [c for c in cols if 'combined' in c.lower() and ('rate' in c.lower() or 'statutory' in c.lower())]
        if not name_cols or not rate_cols: continue
        for _, row in df.iterrows():
            name = str(row[name_cols[0]]).strip()
            raw = str(row[rate_cols[0]]).replace('%','').strip()
            try: val = float(raw)
            except ValueError: continue
            if name in TAX_FALLBACK and 0 <= val <= 60: found[name] = val
    if len(found) < 5: raise ValueError('OECD table layout did not yield enough verified country/rate pairs')
    return found, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_te_yields():
    # Trading Economics publishes a country/yield table at /bonds.
    # Parse named columns rather than assume the first number is the yield.
    response = requests.get(BONDS_URL,timeout=25,headers={'User-Agent':'Mozilla/5.0'})
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    found = {}
    for df in tables:
        df.columns = [' '.join(map(str,c)) if isinstance(c,tuple) else str(c) for c in df.columns]
        cols = list(df.columns)
        bond_cols = [c for c in cols if 'bond' in c.lower() or 'country' in c.lower()]
        yield_cols = [c for c in cols if c.lower().strip() in ('yield','last','price')]
        if not bond_cols or not yield_cols: continue
        for _, row in df.iterrows():
            label = str(row[bond_cols[0]]).strip()
            for country in TAX_FALLBACK:
                if country.lower() in label.lower() and ('10y' in label.lower() or '10-year' in label.lower() or '10 year' in label.lower()):
                    try: val=float(str(row[yield_cols[0]]).replace('%','').replace(',',''))
                    except ValueError: continue
                    if -5 < val < 50: found[country] = val
    if 'United States' not in found: raise ValueError('Could not verify US 10-year yield from Trading Economics table')
    return found, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

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
    if st.button("Refresh source data"):
        fetch_industries.clear()
        fetch_oecd_tax_table.clear()
        fetch_te_yields.clear()
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
    country = st.selectbox("Target country", sorted(TAX_FALLBACK), index=sorted(TAX_FALLBACK).index("United States"))
    tax_basis = st.radio("Project tax rate", ["United States", "Selected country"], horizontal=True)

try:
    live_taxes, tax_fetched = fetch_oecd_tax_table()
    tax_error = None
except Exception as exc:
    live_taxes, tax_fetched, tax_error = {}, None, str(exc)
try:
    live_yields, yield_fetched = fetch_te_yields()
    yield_error = None
except Exception as exc:
    live_yields, yield_fetched, yield_error = {}, None, str(exc)

chosen_tax_country = "United States" if tax_basis == "United States" else country
tax_auto = live_taxes.get(chosen_tax_country, TAX_FALLBACK.get(chosen_tax_country))
tax_origin = ("OECD 2024 webpage, fetched " + tax_fetched) if chosen_tax_country in live_taxes else "2026 lecture snapshot (not live OECD)"
us_yield_auto = live_yields.get("United States", YIELD_FALLBACK.get("United States"))
foreign_yield_auto = live_yields.get(country, YIELD_FALLBACK.get(country))

with st.sidebar:
    beta_override = st.toggle("Override unlevered beta", value=False)
    beta_manual = st.number_input("Manual unlevered beta", min_value=0.0, value=0.80, step=0.05,
                                  disabled=not beta_override)
    beta_u = beta_manual if beta_override else beta_fetched
    st.caption(f"Beta used: {beta_u:.4f}" + (" (manual)" if beta_override else " (downloaded or fallback)"))
    debt_pct = st.slider("Debt financing (%)", 0, 95, 30)
    tax_override = st.toggle("Override corporate tax rate")
    tax_pct = st.number_input("Project corporate tax rate (%)", min_value=0.0, max_value=100.0,
                              value=float(tax_auto or 25.5), step=0.1, disabled=not tax_override,
                              key=f"tax_{chosen_tax_country}") if tax_override else tax_auto
    st.caption(f"Tax source: {'manual' if tax_override else tax_origin}")
    erp_pct = st.number_input("Equity risk premium (%)", min_value=0.0, value=6.5, step=0.25)
    us_override = st.toggle("Override U.S. yield")
    us_yield_pct = st.number_input("US 10-year yield (%)", value=float(us_yield_auto or 4.9), step=0.1, disabled=not us_override) if us_override else us_yield_auto
    foreign_override_yield = st.toggle("Override selected-country yield")
    foreign_yield_pct = (st.number_input(f"{country} 10-year yield (%)", value=float(foreign_yield_auto or 4.9), step=0.1, key=f"yield_{country}")
                         if foreign_override_yield else foreign_yield_auto)
    st.caption("Yield source: Trading Economics live table where available; otherwise Nov 6, 2026 lecture snapshot. Missing values require manual override.")
    usd_spread_pct = st.number_input("USD BBB borrowing spread (percentage points)", min_value=0.0, value=1.5, step=0.1)
    foreign_override = st.toggle("Override selected-country borrowing spread", value=False)
    foreign_spread_pct = st.number_input("Selected-country borrowing spread (percentage points)", min_value=0.0,
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

if tax_pct is None or us_yield_pct is None or foreign_yield_pct is None:
    st.error("A required source value is unavailable. Enable its manual override in the sidebar to continue.")
    st.stop()

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
    st.markdown(f"### {country} (local currency)")
    st.metric("Cost of equity", f"{100 * r['re_foreign']:.4f}%")
    st.metric("Pretax cost of debt", f"{100 * r['rd_foreign']:.4f}%")
    st.metric("WACC", f"{100 * r['wacc_foreign']:.4f}%")

with st.expander("Show formulas and intermediate calculations"):
    st.latex(r"\beta_E=\beta_U\left[1+(1-T)\frac{d}{1-d}\right]")
    st.write(f"Levered beta: {r['beta_e']:.6f}")
    st.latex(r"R_{e,USD}=R_{f,USD}+\beta_E ERP")
    st.latex(r"1+R_{e,*}=(1+R_{e,USD})\frac{1+R_{f,*}}{1+R_{f,USD}}")
    st.latex(r"s_*=s_{USD}\frac{1+R_{f,*}}{1+R_{f,USD}}\quad\mathrm{(unless\ overridden)}")
    st.write(f"Yield conversion factor: {r['factor']:.7f}; Foreign spread: {100*r['spread_foreign']:.4f}%")
    st.latex(r"WACC=(1-d)R_e+dR_d(1-T)")

st.subheader("Data provenance")
st.write(f"Tax: {tax_origin}. U.S. yield: {'Trading Economics fetched '+yield_fetched if 'United States' in live_yields else 'lecture snapshot Nov 6, 2026'}. "
         f"{country} yield: {'Trading Economics fetched '+yield_fetched if country in live_yields else 'lecture snapshot Nov 6, 2026' if country in YIELD_FALLBACK else 'manual'}.")
if tax_error: st.warning(f"OECD live extraction unavailable: {tax_error}. Tax uses clearly labeled lecture fallback where available.")
if yield_error: st.warning(f"Trading Economics live extraction unavailable: {yield_error}. Yields use dated lecture fallback where available.")
st.caption("Source for industry beta: [Damodaran U.S. industry betas](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls). BBB spread remains an illustrative lecture value (1.5%) until the next stage; override manually as needed.")
