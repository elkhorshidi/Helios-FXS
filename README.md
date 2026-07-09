# FX Declaration Decision Dashboard

Production-ready Streamlit MVP for choosing the lowest-cost daily route for Iranian export obligation settlement. The app calculates active settlement routes for every origin currency, ranks them by total cost, and generates a Persian daily recommendation report.

## Excel Workbook Role

The workbook `docs/fx_declaration_decision_model_percent_v5_daily_rate_input.xlsx` is the approved business logic prototype and validation benchmark. It was inspected for sheet structure, fees, daily AED-based rates, route conditions, Persian labels, Daily_Report output, narrative format, and History structure.

The Streamlit app does not depend on Excel at runtime. The approved formulas were reimplemented directly in Python.

Inspected sheets:

- `Daily_Rate_Input`: paste-friendly market rate input.
- `Daily_Rates`: normalized rates for Tether, Tehran, Istanbul, Sulaymaniyah, and Dubai.
- `Fees_Settings`: default fees and manual override pattern.
- `Conversion_Matrix`: conversion cost formulas.
- `Route_Comparison`: active route logic for a selected origin.
- `Daily_Report`: all-origin daily decision output.
- `History`: saved daily snapshots.
- `Notes`: formula documentation and business rules.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

`app.py` is the main Streamlit entry point.

## Streamlit Community Cloud Deployment

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, choose **New app**.
3. Select the GitHub repository and branch.
4. Set **Main file path** to `app.py`.
5. Leave the app command as the default; Streamlit will install `requirements.txt` and run:

```bash
streamlit run app.py
```

No local absolute paths are required. The app uses relative project files only, and the SQLite data directory is created automatically when needed.

Important persistence note: local SQLite files on Streamlit Community Cloud are not guaranteed to persist across app restarts, redeploys, or container replacement. The built-in `data/history.db` storage is suitable for MVP demos and local use; use an external database for durable production history.

## Architecture

- `app.py`: Streamlit UI, pages, downloads, charts, and save workflow.
- `calculation_engine.py`: route formulas, active-route logic, ranking, and Excel reference comparison.
- `customer_report.py`: client-facing customer report data mapping plus PNG/PDF rendering.
- `report_generator.py`: Persian narrative generation.
- `validation.py`: market-rate validation and paste parsing.
- `storage.py`: SQLite persistence in `data/history.db`, created automatically when needed.
- `tests/`: pytest coverage for calculations and narrative behavior.

## Customer Report Exports

The `گزارش مشتری` page creates a single client-facing recommendation card for one selected origin currency. It uses the existing approved calculation output and does not duplicate business logic.

Exports are generated server-side:

- PNG: rendered with Pillow.
- PDF: rendered with ReportLab.
- RTL/Persian shaping: handled with `arabic-reshaper` and `python-bidi`.

Persian text rendering uses the bundled Vazirmatn font files in `assets/fonts/`. Vazirmatn is distributed under the SIL Open Font License; the license text is included at `assets/fonts/OFL.txt`. No local machine font paths are required.

## Core Formulas

All percentages are stored internally as decimals. For example, `0.70%` is `0.007`.

### NO_FX_DECLARATION

Persian label: `اظهارنامه بدون ارز`

Total cost:

```text
conversion cost from origin currency to USD Tehran + no-FX declaration fee
```

USD origin conversion:

```text
(Tehran Sell - Origin Buy) / Origin Buy
```

Workbook validation note: when the USD origin market is already the destination market, the Excel prototype treats conversion cost as `0.00%`. The Python engine follows that benchmark behavior.

AED_Dubai conversion:

```text
(Tehran Sell - Tehran Buy) / Tehran Buy
```

### DUBAI_FX_DECLARATION

Persian label: `اظهارنامه با ارز از مسیر دوبی`

Total cost:

```text
conversion cost from origin currency to USD Dubai + Dubai transfer/import fee
```

USD origin conversion:

```text
(Dubai Sell - Origin Buy) / Origin Buy
```

Workbook validation note: same-market USD conversions are `0.00%`; AED_Dubai remains non-zero when converting to USD Dubai.

AED_Dubai conversion:

```text
(Dubai Sell - Dubai Buy) / Dubai Buy
```

AED_Dubai conversion to USD Dubai is intentionally not zero.

### ISTANBUL_DIRECT

Persian label: `اظهارنامه با ارز مستقیم استانبول`

This route is active only for `USD_Istanbul`.

```text
total cost = Istanbul direct supplier fee
```

## Default Inputs

Default fees:

- No-FX declaration fee: `0.70%`
- Dubai transfer/import fee: `0.50%`
- Istanbul direct supplier fee: `1.50%`
- Sample amount: `$1,000,000`

Example AED-based rates from the Excel benchmark:

| Date | Market | Buy | Sell |
| --- | --- | ---: | ---: |
| 1405/04/17 | Tether | 3.670 | 3.677 |
| 1405/04/17 | Tehran | 3.660 | 3.670 |
| 1405/04/17 | Istanbul | 3.677 | 3.683 |
| 1405/04/17 | Sulaymaniyah | 3.686 | 3.694 |
| 1405/04/17 | Dubai | 3.670 | 3.688 |

## Example Outputs

Representative Python outputs match the Excel `Daily_Report` benchmark:

| Origin | Best Route | Best Cost % | Second Best % |
| --- | --- | ---: | ---: |
| USD_Tehran | اظهارنامه بدون ارز | 0.70% | 1.27% |
| USD_Istanbul | اظهارنامه بدون ارز | 0.51% | 0.80% |
| USD_Sulaymaniyah | اظهارنامه بدون ارز | 0.27% | 0.55% |
| USD_Tether | اظهارنامه بدون ارز | 0.70% | 0.99% |
| AED_Dubai | اظهارنامه بدون ارز | 0.97% | 0.99% |

Negative conversion costs are described in Persian as the client `سر می‌گیرد`.

## Database Structure

SQLite is stored at `data/history.db`. The `data/` directory is created automatically if it does not exist.

- `report_runs`: one saved report run per date/version, with sample amount, fees JSON, rates JSON, and timestamp.
- `decision_rows`: one output row per origin currency, including best route, second-best route, all route cost columns, savings, recommendation text, and route cost JSON.

Duplicate saves for the same report date are blocked unless the user explicitly chooses to replace the latest version.

On Streamlit Community Cloud, this local SQLite file should be treated as ephemeral. It may be reset when the app restarts or redeploys.

## Missing Rate Handling

Missing or invalid rates are never interpreted as zero. The calculation engine skips invalid market rows, marks affected routes as `ریت موجود نیست`, excludes those routes from ranking, and keeps the UI free of stack traces, NaN, and Infinity values.

If no route can be calculated for an origin currency, `Best Route` is shown as `داده کافی نیست`, cost fields remain blank, and the Persian narrative explains that the required market rates are incomplete. If only one route is available, it is selected as the best route and no saving-vs-next value is calculated.

## Testing

```bash
pytest
```

Tests validate:

- all five origin currencies,
- positive conversion cost,
- negative conversion benefit language,
- AED_Dubai non-zero Dubai conversion,
- inactive Istanbul Direct route for non-Istanbul origins,
- single-active-route narrative behavior.
