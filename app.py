import io
import re
from bs4 import BeautifulSoup
import numpy as np
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", layout="wide")
st.title("International Cost of Capital")
st.caption("International calculator · live-source attempts, dated fallbacks and independent checks")

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
    """OECD SDMX official data endpoint; 2026 standard statutory CIT, general government."""
    codes = {"United States":"USA","Canada":"CAN","United Kingdom":"GBR","Germany":"DEU",
             "France":"FRA","Japan":"JPN","Australia":"AUS","Mexico":"MEX",
             "Poland":"POL","Switzerland":"CHE","Ireland":"IRL","Netherlands":"NLD",
             "Italy":"ITA","Spain":"ESP","Sweden":"SWE","Norway":"NOR",
             "Denmark":"DNK","South Korea":"KOR","Portugal":"PRT","Colombia":"COL"}
    # Official OECD Data Explorer API uses /rest/data (not /rest/v1/data).
    # Query shape is based on the dataset's own Developer API query builder.
    url = ("https://sdmx.oecd.org/public/rest/data/"
           "OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.A..ST..S13...?"
           "startPeriod=2025&dimensionAtObservation=AllDimensions&format=csvfile")
    response = requests.get(url, headers={"Accept":"text/csv", "User-Agent":"Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text))
    required = {"REF_AREA", "TIME_PERIOD", "OBS_VALUE"}
    if not required.issubset(frame.columns):
        raise ValueError(f"OECD columns changed: {list(frame.columns)[:12]}")
    frame = frame[frame["REF_AREA"].isin(codes.values())].copy()
    frame["OBS_VALUE"] = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")
    frame["TIME_PERIOD"] = pd.to_numeric(frame["TIME_PERIOD"], errors="coerce")
    frame = frame.dropna(subset=["OBS_VALUE", "TIME_PERIOD"])
    # Only accept one observation per country-year; otherwise the rate type is ambiguous.
    latest = frame["TIME_PERIOD"].max()
    frame = frame[frame["TIME_PERIOD"] == latest]
    if frame["REF_AREA"].duplicated().any():
        raise ValueError("OECD returned multiple tax measures per country; refusing ambiguous rates")
    reverse = {v:k for k,v in codes.items()}
    found = {reverse[r.REF_AREA]:float(r.OBS_VALUE) for r in frame.itertuples()
             if r.REF_AREA in reverse and 0 <= float(r.OBS_VALUE) <= 60}
    if "United States" not in found:
        raise ValueError("OECD response did not include US statutory rate")
    return found, f"OECD observation {int(latest)}; fetched {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_te_yields():
    """Extract 10Y yields from Trading Economics individual government bond pages.
    Fail closed on pages without a verifiable labelled quote.
    """
    found = {}
    for country in TAX_FALLBACK:
        slug = TE_SLUGS.get(country, country.lower().replace(' ', '-'))
        url = f'https://tradingeconomics.com/{slug}/government-bond-yield'
        try:
            response = requests.get(url, timeout=12, headers={'User-Agent':'Mozilla/5.0 (compatible; educational research)'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.get_text(' ', strip=True) if soup.title else ''
            if '10 year' not in title.lower() and '10-year' not in title.lower():
                continue
            # TE page's first summary card: heading 'Actual' followed by numeric quote.
            actual = soup.find(string=re.compile(r'^\s*Actual\s*$', re.I))
            if actual is None: continue
            container = actual.parent
            value = None
            for parent in [container, container.parent, container.parent.parent if container.parent else None]:
                if parent is None: continue
                txt = parent.get_text(' ', strip=True)
                match = re.search(r'\bActual\s+(-?\d{1,2}\.\d{1,5})\b', txt, re.I)
                if match:
                    value = float(match.group(1)); break
            if value is not None and -5 < value < 50:
                found[country] = value
        except (requests.RequestException, ValueError, AttributeError):
            continue
    if 'United States' not in found:
        raise ValueError('Could not extract a verified US 10-year yield from Trading Economics')
    return found, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

RATINGS_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_bbb_spread():
    """Parse large non-financial firms Baa2/BBB row (first spread column)."""
    response = requests.get(RATINGS_URL, timeout=25, headers={'User-Agent':'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    for row in soup.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in row.find_all(['td','th'])]
        for i, cell in enumerate(cells):
            if re.search(r'\bBaa2\s*/\s*BBB\b', cell, re.I) and i + 1 < len(cells):
                match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*%\s*', cells[i+1])
                if match:
                    value = float(match.group(1))
                    if 0 < value < 15:
                        return value, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    raise ValueError('Baa2/BBB spread row was not found in Damodaran table')

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
        fetch_bbb_spread.clear()
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
tax_origin = ("OECD SDMX API, fetched " + tax_fetched) if chosen_tax_country in live_taxes else "2026 lecture snapshot (not live OECD)"
us_yield_auto = live_yields.get("United States", YIELD_FALLBACK.get("United States"))
foreign_yield_auto = live_yields.get(country, YIELD_FALLBACK.get(country))

try:
    bbb_auto, bbb_fetched = fetch_bbb_spread()
    bbb_error = None
except Exception as exc:
    bbb_auto, bbb_fetched, bbb_error = 1.5, None, str(exc)

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
    usd_spread_override = st.toggle("Override USD BBB borrowing spread", value=False)
    usd_spread_pct = st.number_input("USD BBB borrowing spread (percentage points)", min_value=0.0,
                                     value=float(bbb_auto if bbb_auto is not None else 1.5), step=0.1,
                                     disabled=not usd_spread_override) if usd_spread_override else bbb_auto
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

if tax_pct is None or us_yield_pct is None or foreign_yield_pct is None or usd_spread_pct is None:
    st.error("A required source value is unavailable. Enable its manual override in the sidebar to continue. In particular, enter the current BBB spread from Damodaran if automatic retrieval fails.")
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
st.markdown("Sources: [Damodaran industry betas](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) · [Damodaran BBB spread](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) · [OECD tax rates](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html) · [Trading Economics bonds](https://tradingeconomics.com/bonds)")
st.write(f"USD BBB spread: {'manual override' if usd_spread_override else 'Damodaran fetched '+bbb_fetched if bbb_fetched else 'illustrative fallback (1.5%, not current)'}. Foreign spread: {'manual override' if foreign_override else 'calculated by government-yield ratio'}.")
if bbb_error: st.warning(f"Damodaran BBB extraction unavailable: {bbb_error}. An illustrative 1.5% fallback is used and labeled; enter the published spread using the manual override for a current result.")

st.subheader("All-industry comparison")
if 'industries' in globals():
    rows = []
    for _, item in industries.iterrows():
        rr = calculate(float(item['Unlevered beta']), debt_pct/100, tax_pct/100,
                       erp_pct/100, us_yield_pct/100, foreign_yield_pct/100,
                       usd_spread_pct/100, foreign_spread_pct/100 if foreign_override else None)
        rows.append({'Industry':item['Industry'], 'Unlevered beta':float(item['Unlevered beta']),
                     'Levered beta':rr['beta_e'], 'USD equity cost (%)':100*rr['re_us'],
                     'USD debt cost (%)':100*rr['rd_us'], 'USD WACC (%)':100*rr['wacc_us'],
                     f'{country} equity cost (%)':100*rr['re_foreign'],
                     f'{country} debt cost (%)':100*rr['rd_foreign'],
                     f'{country} WACC (%)':100*rr['wacc_foreign']})
    comparison = pd.DataFrame(rows)
    st.dataframe(comparison, use_container_width=True, hide_index=True)
    st.download_button("Download all-industry results (CSV)", comparison.to_csv(index=False).encode('utf-8'),
                       'international_cost_of_capital_industries.csv', 'text/csv')
    st.download_button("Download selected project results (CSV)",
                       pd.DataFrame([{'Industry':industry,'Country':country,'Tax basis':chosen_tax_country,
                        'Tax rate (%)':tax_pct,'Debt share (%)':debt_pct,'ERP (%)':erp_pct,
                        'US yield (%)':us_yield_pct,'Foreign yield (%)':foreign_yield_pct,
                        'USD BBB spread (%)':usd_spread_pct, 'Foreign BBB spread (%)':100*r['spread_foreign'],
                        'USD cost of equity (%)':100*r['re_us'],'Foreign cost of equity (%)':100*r['re_foreign'],
                        'USD cost of debt (%)':100*r['rd_us'],'Foreign cost of debt (%)':100*r['rd_foreign'],
                        'USD WACC (%)':100*r['wacc_us'],'Foreign WACC (%)':100*r['wacc_foreign']}]).to_csv(index=False).encode('utf-8'),
                        'international_cost_of_capital_selected.csv','text/csv')
else:
    st.warning('All-industry comparison requires a successful Damodaran beta download.')

st.subheader("Verification checks")
if st.button("Run independent consistency checks"):
    baseline = calculate(.8,.3,.35,.065,.04,.12,.015)
    equal = calculate(.8,.3,.35,.065,.04,.04,.015)
    no_debt = calculate(.8,0,.35,.065,.04,.12,.015)
    altered = calculate(.8,.3,.35,.065,.04,.12,.015,.05)
    tests = {
        'Lecture Colombia: USD WACC ≈ 8.5265%': abs(baseline['wacc_us']-.085265)<1e-6,
        'Lecture Colombia: COP WACC ≈ 16.0670%': abs(baseline['wacc_foreign']-.160670)<1e-6,
        'Equal yields → equal equity, debt and WACC': all(abs(equal[a]-equal[b])<1e-12 for a,b in [('re_us','re_foreign'),('rd_us','rd_foreign'),('wacc_us','wacc_foreign')]),
        'Zero debt → WACC equals cost of equity in each currency': abs(no_debt['wacc_us']-no_debt['re_us'])<1e-12 and abs(no_debt['wacc_foreign']-no_debt['re_foreign'])<1e-12,
        'Foreign spread override does not change USD results': all(abs(baseline[k]-altered[k])<1e-12 for k in ('re_us','rd_us','wacc_us')),
    }
    for label, passed in tests.items():
        (st.success if passed else st.error)(f"{'PASS' if passed else 'FAIL'} — {label}")
    st.caption('Tests use independently specified illustrative inputs, not live market data.')

st.info('Model assumptions: U.S. industry beta proxies project operating risk; debt beta is zero; a single project tax rate and target debt share apply to both currencies; no extra country equity premium; government 10-year yields proxy risk-free rates; currency conversion uses gross-rate ratio (relative PPP/equal real rates).')
