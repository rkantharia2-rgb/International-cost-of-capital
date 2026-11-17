# International Cost of Capital — Stage 1

A Streamlit prototype reproducing the Colombia worked example from Sergio Rebelo's 2026 international valuation lecture (pages 25–28).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Model

- Levered beta: `beta_U * (1 + (1-tax) * debt_share/(1-debt_share))`
- USD cost of equity: `US_yield + levered_beta * ERP`
- USD debt cost: `US_yield + USD_BBB_spread`
- Foreign cost of equity: `(1+USD_cost_of_equity)*(1+foreign_yield)/(1+US_yield)-1`
- Foreign spread by default: `USD_spread*(1+foreign_yield)/(1+US_yield)`
- WACC: `(1-debt_share)*cost_of_equity + debt_share*cost_of_debt*(1-tax)`

## Scope

This is a deliberately limited first stage with editable **illustrative** Colombia inputs. It does not yet fetch data or offer country/industry selectors. Do not submit it as the final assignment.
