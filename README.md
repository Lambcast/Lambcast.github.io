# AI Infrastructure & Regional Electricity Demand
### A Forecasting Framework for U.S. Grid Stress

**Alan Lamb | Lambcast Applied Economics | M.S. Applied Economics, University of Maryland | 2026**

---

## Research Question
How much has data center investment driven regional electricity demand growth — and can we build a model that forecasts future grid stress from the existing investment pipeline?

## Methods
- **Identification:** Four-layer strategy producing a credible estimated range across methods
  - Panel regression with wild cluster bootstrap inference (Stata `boottest`)
  - Synthetic control — ERCOT as treated unit, treatment date from Bai-Perron structural break test
  - DiD with low-exposure controls — ISONE and NYISO as cleaner donor pool
  - Narrative validation — known data center energizations overlaid on synthetic control gap
- **Treatment variable:** Generation interconnection queue filings (LBL Queued Up 2024 + UMD PJM queue)
- **Forecasting:** XGBoost benchmarked against ARIMA and Prophet, queue pipeline as primary feature set

## Key Early Finding
ERCOT electricity demand grew approximately 27% from 2019 to 2025. PJM and MISO remained essentially flat. ERCOT interconnection queue filings reached 97 GW in 2024 — the largest year on record.

## Geographic Scope
Three major U.S. electricity markets covering ~70% of national load:
- **PJM** — Mid-Atlantic/Midwest (largest data center market in the world)
- **ERCOT** — Texas (fastest growing data center market)
- **MISO** — Southeast/Midwest (emerging growth corridor)

## Data Sources
| Dataset | Source | Status |
|---|---|---|
| EIA Form 930 hourly demand | eia.gov/opendata | ✅ 184,102 rows (2019–2025) |
| UMD PJM Queue 2008–2024 | UMD Economics (NSF-funded) | ✅ In hand |
| LBL Queued Up 2024 | Lawrence Berkeley National Lab | ✅ In hand |
| Analysis panel | Built from above | ✅ 252 rows, 3 BAs × 84 months |
| NOAA weather (HDD/CDD) | NCEI Climate Data Online | Pending |
| BEA regional GDP | BEA regional accounts | Pending |
| ERCOT/PJM/MISO large load queue | Public portals | ❌ Not available — documented as policy finding |

## Project Status
- [x] Phase 1: Data infrastructure, exploratory analysis, analysis panel built
- [ ] Phase 2: Four-layer identification strategy
- [ ] Phase 3: Forecasting model and benchmarking
- [ ] Phase 4: Hex dashboard and SSRN working paper

## Tool Stack
Python, Stata, SQL, BigQuery, PySpark, Hex

## Publication
Results and writeups published at [lambcast.net](https://lambcast.net)
