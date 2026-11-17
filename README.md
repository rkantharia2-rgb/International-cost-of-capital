International Cost of Capital
Streamlit calculator comparing cost of equity, pretax debt cost and WACC in USD and a selected country's currency.
Deploy
Upload `app.py`, `requirements.txt`, and `README.md` to the root of a GitHub repository. Deploy `app.py` from the `main` branch in Streamlit Community Cloud.
Model
Levered beta = unlevered beta × [1 + (1 − tax rate) × debt share / (1 − debt share)]. USD cost of equity = U.S. 10-year yield + levered beta × ERP. USD debt cost = U.S. 10-year yield + BBB spread. Gross foreign equity rate = gross USD equity rate × (gross foreign government yield / gross U.S. government yield). Foreign BBB spread defaults to USD BBB spread × that same yield factor, unless manually overridden. WACC = equity share × cost of equity + debt share × pretax debt cost × (1 − project tax rate). Percent inputs are converted to decimals for calculation.
Sources and reliability
Damodaran industry unlevered betas: https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls (Industry Averages tab)
Damodaran BBB spread: https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html (large non-financial firms)
OECD corporate tax statistics: https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html
Trading Economics 10-year yields: https://tradingeconomics.com/bonds
Automatic retrieval is attempted at refresh, with cached downloads between refreshes. The source sites may block scraping or change page structure. When tax/yield retrieval fails, the app uses clearly labeled dated lecture snapshots, where available; the BBB spread falls back to illustrative 1.5%, not a current market observation. Manual overrides are supported. The fetch timestamp is not the underlying dataset publication date. This app is for coursework, not live investment advice.
Verification
Click `Run independent consistency checks`. Tests include reproduction of the lecture's Colombia example (USD WACC 8.5265%; COP WACC 16.0670%), equality with identical government yields, zero debt implying WACC = cost of equity, and foreign borrowing-spread override not affecting USD results. The all-industry table and selected project results can be downloaded as CSV.
Defaults
Software (System & Application); United States; U.S. tax rate; ERP 6.5%; debt share 30%.
