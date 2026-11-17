# International Cost of Capital

Streamlit app comparing project cost of equity, debt, and WACC in USD and a selected country's currency.

## Features

- Industry selection using Damodaran's unlevered betas
- Country selection and tax-rate choice
- Government bond yields and BBB borrowing spread
- Manual overrides and data refresh
- All-industry comparison and CSV downloads
- Independent calculation checks

## Data Sources

- [Damodaran industry betas](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls)
- [Damodaran BBB spreads](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html)
- [OECD corporate tax statistics](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html)
- [Trading Economics government bond yields](https://tradingeconomics.com/bonds)

## Deployment

Deploy `app.py` using Streamlit Community Cloud with `requirements.txt` in the repository root.

## Calculation

Levered beta = Unlevered beta × [1 + (1 − tax rate) × debt share / (1 − debt share)]

USD cost of equity = U.S. 10-year yield + levered beta × equity risk premium

USD cost of debt = U.S. 10-year yield + BBB spread

Foreign rates use the ratio (1 + foreign government yield) / (1 + U.S. government yield).

WACC = (1 − debt share) × cost of equity + debt share × cost of debt × (1 − tax rate)

## Data Reliability

The app attempts to retrieve published data when refreshed. Some sources may block automated access. Unavailable observations are identified as dated fallbacks, and manual overrides are supported. A fetch timestamp does not necessarily indicate the underlying data publication date.

## Verification

The app includes checks for the Colombia lecture example, equal government yields, zero debt, and foreign spread override independence.
