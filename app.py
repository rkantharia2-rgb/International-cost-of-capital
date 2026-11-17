import streamlit as st

st.set_page_config(page_title="International Cost of Capital", layout="wide")
st.title("International Cost of Capital")
st.caption("Stage 1 · Reproduce the Colombia example from Professor Rebelo's lecture")

with st.sidebar:
    st.header("Project assumptions")
    beta_u = st.number_input("Unlevered industry beta", min_value=0.0, value=0.80, step=0.05)
    debt_pct = st.slider("Debt financing (%)", 0, 95, 30)
    tax_pct = st.number_input("Project corporate tax rate (%)", min_value=0.0, max_value=100.0, value=35.0, step=0.5)
    erp_pct = st.number_input("Equity risk premium (%)", min_value=0.0, value=6.5, step=0.25)
    us_yield_pct = st.number_input("US 10-year yield (%)", value=4.0, step=0.1)
    foreign_yield_pct = st.number_input("Colombia 10-year yield (%)", value=12.0, step=0.1)
    usd_spread_pct = st.number_input("USD BBB borrowing spread (percentage points)", min_value=0.0, value=1.5, step=0.1)
    foreign_override = st.toggle("Override COP borrowing spread", value=False)
    foreign_spread_pct = st.number_input("COP borrowing spread (percentage points)", min_value=0.0, value=1.5, step=0.1, disabled=not foreign_override)

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
col1, col2 = st.columns(2)
for col, label, suffix in [(col1, "United States (USD)", "us"), (col2, "Colombia (COP)", "foreign")]:
    with col:
        st.markdown(f"### {label}")
        st.metric("Cost of equity", f"{r[f're_{suffix}']:.4%}")
        st.metric("Pretax cost of debt", f"{r[f'rd_{suffix}']:.4%}")
        st.metric("WACC", f"{r[f'wacc_{suffix}']:.4%}")

with st.expander("Show formulas and intermediate calculations", expanded=True):
    st.latex(r"\beta_E=\beta_U\left[1+(1-T)\frac{d}{1-d}\right]")
    st.write(f"Levered beta: **{r['beta_e']:.6f}**")
    st.latex(r"R_{e,USD}=R_{f,USD}+\beta_E ERP")
    st.latex(r"1+R_{e,COP}=(1+R_{e,USD})\frac{1+R_{f,COP}}{1+R_{f,USD}}")
    st.latex(r"s_{COP}=s_{USD}\frac{1+R_{f,COP}}{1+R_{f,USD}}\quad\text{(unless overridden)}")
    st.write(f"Yield conversion factor: **{r['factor']:.7f}**; COP spread: **{r['spread_foreign']:.4%}**")
    st.latex(r"WACC=(1-d)R_e+dR_d(1-T)")

st.info("Stage 1 uses illustrative lecture inputs, not live market data. Next: country and industry selectors, source retrieval, and refresh controls.")
