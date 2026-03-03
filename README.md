# AI Infrastructure & Regional Electricity Demand
### A Causal Forecasting Framework for the U.S. Power Grid

**Alan Lamb | Lambcast Applied Economics | M.S. Applied Economics, University of Maryland | 2026**

---

## Research Question
Do large data center interconnection requests causally shift regional electricity load growth — and can we build a model that forecasts future grid stress from the existing investment pipeline?

## Methods
- **Causal identification:** Difference-in-differences with event study design
- **Treatment variable:** Utility interconnection queue filings (legally binding, precise dates and MW ratings)
- **Forecasting:** XGBoost with causal estimate as feature, benchmarked against ARIMA and Prophet baselines
- **Scale:** PySpark for feature engineering on 100M+ row EIA hourly dataset

## Geographic Scope
Three major U.S. electricity markets covering ~70% of national load:
- **PJM** — Mid-Atlantic/Midwest (largest data center market in the world)
- **ERCOT** — Texas (fastest growing data center market)
- **MISO** — Southeast/Midwest (emerging growth corridor)

## Data Sources
| Dataset | Source |
|---|---|
| EIA Form 930 hourly demand | eia.gov/opendata |
| PJM interconnection queue 2008–2020 | UMD Economics Dept. (NSF-funded) |
| PJM live queue 2020–2025 | gridstatus.io |
| ERCOT large load queue | ERCOT public portal |
| MISO queue | MISO public API |
| NOAA weather (HDD/CDD) | NCEI Climate Data Online |
| BEA regional GDP | BEA regional accounts |

## Project Status
- [x] Phase 1: Data infrastructure and exploratory analysis
- [ ] Phase 2: DiD causal identification
- [ ] Phase 3: Event study and robustness checks
- [ ] Phase 4: Forecasting model and Hex dashboard

## Tool Stack
Python, SQL, BigQuery, PySpark, Stata, Hex

## Publication
Results and writeups published at [lambcast.net](https://lambcast.net)