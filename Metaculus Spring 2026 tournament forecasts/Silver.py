import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm

# ══════════════════════════════════════════════════════════════
# 1. PULL ALL DATA
# ══════════════════════════════════════════════════════════════
print("Fetching data...")

def get_close(ticker, start="2020-01-01"):
    raw = yf.download(ticker, start=start, progress=False)
    raw.columns = raw.columns.get_level_values(0)
    return raw["Close"].rename(ticker)

silver_raw = yf.download("SI=F", start="2020-01-01", progress=False)
silver_raw.columns = silver_raw.columns.get_level_values(0)
silver_close = silver_raw["Close"].rename("Silver")
silver_high  = silver_raw["High"].rename("High")

gold = get_close("GC=F")
vix  = get_close("^VIX")
dxy  = get_close("DX-Y.NYB")

df = pd.concat([silver_close, silver_high, gold, vix, dxy], axis=1, sort=True).dropna()
df.index = pd.to_datetime(df.index)
print(f"Combined dataset: {len(df)} trading days")

# ══════════════════════════════════════════════════════════════
# 2. GOLD/SILVER RATIO ANALYSIS
# ══════════════════════════════════════════════════════════════
df["gs_ratio"]       = df["GC=F"] / df["Silver"]
hist_avg_ratio       = df["gs_ratio"].mean()
hist_std_ratio       = df["gs_ratio"].std()
current_ratio        = df["gs_ratio"].iloc[-1]
ratio_zscore         = (current_ratio - hist_avg_ratio) / hist_std_ratio
df["ratio_zscore"]   = (df["gs_ratio"] - hist_avg_ratio) / hist_std_ratio

print(f"\n── Gold/Silver Ratio ───────────────────────────────────")
print(f"Historical avg:   {hist_avg_ratio:.1f}:1")
print(f"Current ratio:    {current_ratio:.1f}:1")
print(f"Z-score:          {ratio_zscore:.2f}")
if ratio_zscore < -1:
    print(f"Signal: Silver EXPENSIVE vs gold → bearish mean-reversion pressure")
elif ratio_zscore > 1:
    print(f"Signal: Silver CHEAP vs gold → bullish mean-reversion")
else:
    print(f"Signal: Ratio near historical average → neutral")

# ══════════════════════════════════════════════════════════════
# 3. RECENT WINDOW — last 6 months
# ══════════════════════════════════════════════════════════════
cutoff = df.index.max() - pd.DateOffset(months=6)
recent = df[df.index >= cutoff].copy()
print(f"\nRecent window: {recent.index[0].date()} → {recent.index[-1].date()} ({len(recent)} days)")

# ══════════════════════════════════════════════════════════════
# 4. LOG RETURNS
# ══════════════════════════════════════════════════════════════
recent["ret_silver"] = np.log(recent["Silver"] / recent["Silver"].shift(1))
recent["ret_gold"]   = np.log(recent["GC=F"]   / recent["GC=F"].shift(1))
recent["ret_vix"]    = np.log(recent["^VIX"]    / recent["^VIX"].shift(1))
recent["ret_dxy"]    = np.log(recent["DX-Y.NYB"]/ recent["DX-Y.NYB"].shift(1))
recent["lagged_ratio_z"] = recent["ratio_zscore"].shift(1)
recent = recent.dropna()

# ══════════════════════════════════════════════════════════════
# 5. MULTI-FACTOR REGRESSION
# ══════════════════════════════════════════════════════════════
y = recent["ret_silver"]
X = sm.add_constant(recent[["ret_gold", "ret_vix", "ret_dxy", "lagged_ratio_z"]])
reg = sm.OLS(y, X).fit()

print("\n── Multi-Factor Regression ─────────────────────────────")
print(reg.summary())

print("\n── Factor Significance (p < 0.05 = significant) ───────")
for factor in ["ret_gold", "ret_vix", "ret_dxy", "lagged_ratio_z"]:
    p   = reg.pvalues[factor]
    b   = reg.params[factor]
    sig = "✓ SIGNIFICANT" if p < 0.05 else "✗ not significant"
    print(f"  {factor:<22} β={b:+.4f}  p={p:.3f}  {sig}")

# Only use significant factors
sig_factors = [f for f in ["ret_gold", "ret_vix", "ret_dxy", "lagged_ratio_z"]
               if reg.pvalues[f] < 0.05]
print(f"\nUsing significant factors: {sig_factors}")

alpha     = reg.params["const"]
resid_std = reg.resid.std()

# ══════════════════════════════════════════════════════════════
# 6. MACRO-ADJUSTED DRIFT
#    Use 30-day average for factor expectations — more stable
#    than 5-day which amplifies short-term noise
# ══════════════════════════════════════════════════════════════
gold_drift = recent["ret_gold"].tail(30).mean()
vix_drift  = recent["ret_vix"].tail(30).mean()
dxy_drift  = recent["ret_dxy"].tail(30).mean()
current_ratio_z = recent["lagged_ratio_z"].iloc[-1]

factor_vals = {
    "ret_gold":       gold_drift,
    "ret_vix":        vix_drift,
    "ret_dxy":        dxy_drift,
    "lagged_ratio_z": current_ratio_z
}

mu_adjusted = alpha + sum(reg.params[f] * factor_vals[f] for f in sig_factors)

# Cap drift at 0.4%/day — still very aggressive historically
# (0.4%/day = ~100% annualized) but prevents compounding explosion
DRIFT_CAP = 0.004
mu_final = np.clip(mu_adjusted, -DRIFT_CAP, DRIFT_CAP)

current_price = recent["Silver"].iloc[-1]
current_gold  = recent["GC=F"].iloc[-1]
current_vix   = recent["^VIX"].iloc[-1]
current_dxy   = recent["DX-Y.NYB"].iloc[-1]
mu_raw        = recent["ret_silver"].mean()

print(f"\n── Current Conditions ──────────────────────────────────")
print(f"Silver:               ${current_price:.2f}")
print(f"Gold:                 ${current_gold:.2f}")
print(f"Gold/Silver ratio:    {current_ratio:.1f}:1  (hist avg {hist_avg_ratio:.1f}:1)")
print(f"Ratio z-score:        {ratio_zscore:.2f}  {'← silver expensive vs gold' if ratio_zscore < 0 else '← silver cheap vs gold'}")
print(f"VIX:                  {current_vix:.1f}")
print(f"DXY:                  {current_dxy:.2f}")
print(f"\nRaw daily drift:      {mu_raw*100:.3f}%")
print(f"Macro-adjusted drift: {mu_adjusted*100:.3f}%")
if abs(mu_adjusted) > DRIFT_CAP:
    print(f"Drift capped at:      {mu_final*100:.3f}%  (cap applied)")
print(f"Residual volatility:  {resid_std*100:.2f}%")

# ══════════════════════════════════════════════════════════════
# 7. QUALITATIVE SCENARIO ASSESSMENT
#    Informs our interpretation — does NOT modify drift
# ══════════════════════════════════════════════════════════════
print(f"\n── Qualitative Scenario Assessment ─────────────────────")

bull, bear = [], []

if ratio_zscore < -1.5:
    bear.append(f"Ratio z={ratio_zscore:.1f}: silver very expensive vs gold → mean reversion risk")
elif ratio_zscore > 1.0:
    bull.append(f"Ratio z={ratio_zscore:.1f}: silver cheap vs gold → upside room")

if current_vix > 25:
    bull.append(f"VIX={current_vix:.1f} elevated → strong safe haven demand")
elif current_vix > 18:
    bull.append(f"VIX={current_vix:.1f} moderately elevated → some safe haven bid")
else:
    bear.append(f"VIX={current_vix:.1f} low → limited fear-driven buying")

if current_dxy < 100:
    bull.append(f"DXY={current_dxy:.1f} weak dollar → tailwind for silver")
elif current_dxy > 105:
    bear.append(f"DXY={current_dxy:.1f} strong dollar → headwind for silver")

bull.append("China export controls active → physical supply constrained")
bull.append("US Critical Minerals designation → strategic stockpiling demand")
bull.append("AI/EV/solar structural demand → price-insensitive industrial buyers")
bear.append("Solar manufacturers cutting silver intensity -7% YoY")
bear.append("Parabolic 6-month move → elevated mean-reversion risk")
bear.append("Supply deficit already priced in by sophisticated buyers")

print("  BULLISH:")
for b in bull: print(f"    + {b}")
print("  BEARISH:")
for b in bear: print(f"    - {b}")

net = len(bull) - len(bear)
print(f"\n  Net: {len(bull)} bullish vs {len(bear)} bearish factors")
print(f"  Interpretation: {'moderately bullish' if net > 0 else 'mixed/uncertain'}")
print(f"  Note: scenario is qualitative — drift already reflects macro via regression")

# ══════════════════════════════════════════════════════════════
# 8. MONTE CARLO
# ══════════════════════════════════════════════════════════════
np.random.seed(42)
n_sims    = 10000
today     = df.index.max()
april_end = pd.Timestamp("2026-04-30")
n_days    = int((april_end - today).days * 252 / 365)
print(f"\nTrading days to April 30: {n_days}")
print(f"Final drift used:         {mu_final*100:.3f}%/day")

sim_returns = np.random.normal(mu_final, resid_std, size=(n_days, n_sims))
paths = np.zeros((n_days + 1, n_sims))
paths[0] = current_price
for t in range(1, n_days + 1):
    paths[t] = paths[t-1] * np.exp(sim_returns[t-1])

dates = pd.date_range(start=today, periods=n_days + 1, freq="B")
april_mask = (dates.month == 4) & (dates.year == 2026)
april_paths = paths[april_mask, :]
if april_paths.shape[0] == 0:
    april_paths = paths

april_highs = april_paths.max(axis=0)

# Winsorize at 5th/95th
p5  = np.percentile(april_highs, 5)
p95 = np.percentile(april_highs, 95)
april_highs_w = april_highs[(april_highs >= p5) & (april_highs <= p95)]

mc_median = np.median(april_highs_w)
mc_mean   = april_highs_w.mean()
mc_p10    = np.percentile(april_highs_w, 10)
mc_p25    = np.percentile(april_highs_w, 25)
mc_p75    = np.percentile(april_highs_w, 75)
mc_p90    = np.percentile(april_highs_w, 90)

print(f"\n── Monte Carlo Results ─────────────────────────────────")
print(f"Mean April high:     ${mc_mean:.2f}")
print(f"Median April high:   ${mc_median:.2f}")
print(f"10th pct (downside): ${mc_p10:.2f}")
print(f"25th percentile:     ${mc_p25:.2f}")
print(f"75th percentile:     ${mc_p75:.2f}")
print(f"90th pct (upside):   ${mc_p90:.2f}")

# ══════════════════════════════════════════════════════════════
# 9. FINAL ENSEMBLE
#    70% MC | 20% WLS trend | 10% community prior
# ══════════════════════════════════════════════════════════════
community = 95.2

monthly = df[["Silver","High"]].resample("ME").agg(
    avg_close=("Silver","mean"),
    monthly_high=("High","max")
).dropna()
n = len(monthly)
decay = np.exp(-np.log(2)/12 * np.arange(n)[::-1])
decay = decay / decay.sum() * n
wls_model    = sm.WLS(monthly["monthly_high"].values,
                      sm.add_constant(np.arange(n)),
                      weights=decay).fit()
wls_forecast = wls_model.predict(np.array([[1, n+2]]))[0]

ensemble = 0.70*mc_mean + 0.20*wls_forecast + 0.10*community

print(f"\n── Final Forecast ──────────────────────────────────────")
print(f"Monte Carlo mean:    ${mc_mean:.2f}   (weight 70%)")
print(f"WLS trend:           ${wls_forecast:.2f}   (weight 20%)")
print(f"Community prior:     ${community:.2f}    (weight 10%)")
print(f"────────────────────────────────────────────────────")
print(f"ENSEMBLE FORECAST:   ${ensemble:.2f}")
print(f"90% RANGE:           ${mc_p10:.2f} – ${mc_p90:.2f}")
print(f"\n★ METACULUS SUBMISSION:")
print(f"  Central estimate:  ${ensemble:.0f}")
print(f"  Lower bound:       ${mc_p10:.0f}  (10th pct — covers reversion scenario)")
print(f"  Upper bound:       ${mc_p90:.0f}  (90th pct — covers continued momentum)")
print(f"  Community says $95.2 — your model says ${ensemble:.0f}")

# ══════════════════════════════════════════════════════════════
# 10. PLOT
# ══════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

ax1 = axes[0]
monthly_plot = df[["Silver","High"]].resample("ME").agg(
    monthly_high=("High","max")).dropna()
ax1.plot(monthly_plot.index, monthly_plot["monthly_high"], "o-",
         color="#2E86AB", linewidth=2, markersize=5,
         label="Monthly High (Actual)")
wls_trend = wls_model.predict(sm.add_constant(np.arange(n)))
ax1.plot(monthly.index, wls_trend, "-", color="#F4A261",
         linewidth=2, label="Exp-Weighted Trend (WLS)")
apr_date = pd.Timestamp("2026-04-30")
ax1.scatter([apr_date], [ensemble], color="#E84855",
            s=150, zorder=5, label=f"Ensemble: ${ensemble:.2f}")
ax1.vlines(apr_date, mc_p10, mc_p90, colors="#E84855",
           linewidth=3, label=f"90% range: ${mc_p10:.0f}–${mc_p90:.0f}")
ax1.axhline(community, color="#9B59B6", linestyle=":",
            linewidth=1.5, label=f"Community: ${community}")
ax1.axvline(cutoff, color="#AAB8C2", linestyle="--",
            linewidth=1, alpha=0.5, label="6-month window")
ax1.set_title("Silver – April 2026 High Forecast\n(Macro-Adjusted Monte Carlo, Drift Capped)",
              fontsize=11, fontweight="bold")
ax1.set_xlabel("Month")
ax1.set_ylabel("Price per Troy Ounce (USD)")
ax1.legend(fontsize=8)
ax1.grid(True, alpha=0.3)

ax2 = axes[1]
ax2.hist(april_highs_w, bins=60, color="#2E86AB",
         alpha=0.7, edgecolor="white", linewidth=0.3)
ax2.axvline(mc_median, color="#E84855", linewidth=2,
            label=f"MC Median: ${mc_median:.2f}")
ax2.axvline(community, color="#9B59B6", linewidth=2,
            linestyle="--", label=f"Community: ${community}")
ax2.axvline(mc_p10, color="#F4A261", linewidth=1.5,
            linestyle=":", label=f"10th pct: ${mc_p10:.0f}")
ax2.axvline(mc_p90, color="#F4A261", linewidth=1.5,
            linestyle=":", label=f"90th pct: ${mc_p90:.0f}")
ax2.set_title("Monte Carlo Distribution – April 2026 High\n(Macro-Adjusted, Drift Capped, Winsorized)",
              fontsize=11, fontweight="bold")
ax2.set_xlabel("April High Price (USD)")
ax2.set_ylabel("Frequency")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("silver_forecast_v5.png", dpi=150)
plt.show()
print("\nSaved: silver_forecast_v5.png")