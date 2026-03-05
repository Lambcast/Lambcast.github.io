"""
explore_eia.py
--------------
Exploratory analysis of EIA Form 930 hourly demand data.
Produces charts for Website Post 1 and paper descriptive section.

Run from project root: python scripts/explore_eia.py
Output saved to: outputs/
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

os.makedirs("outputs", exist_ok=True)

print("Loading EIA demand data...")
df = pd.read_csv("data/eia_demand_2018_2025.csv")

df["datetime"] = pd.to_datetime(df["datetime"])
df = df[df["data_type"] == "D"].copy()
df = df[df["mwh"] < 500000].copy()
df["year"]  = df["datetime"].dt.year
df["month"] = df["datetime"].dt.to_period("M")

print(f"  Loaded {len(df):,} demand records across {df['region'].nunique()} regions.")
print(f"  Date range: {df['datetime'].min()} → {df['datetime'].max()}")
print()

COLORS = {
    "PJM":  "#1F3864",
    "ERCO": "#2E75B6",
    "MISO": "#70AD47",
}

LABELS = {
    "PJM":  "PJM (Mid-Atlantic / Midwest)",
    "ERCO": "ERCOT (Texas)",
    "MISO": "MISO (Southeast / Midwest)",
}

# Chart 1: Annual average hourly demand by region
annual_avg = (
    df.groupby(["year", "region"])["mwh"]
    .mean()
    .reset_index()
    .rename(columns={"mwh": "avg_hourly_demand_mwh"})
)

fig, ax = plt.subplots(figsize=(10, 6))

for region, grp in annual_avg.groupby("region"):
    ax.plot(
        grp["year"], grp["avg_hourly_demand_mwh"],
        marker="o", linewidth=2.5, markersize=6,
        color=COLORS.get(region, "gray"),
        label=LABELS.get(region, region),
    )

ax.set_title("Annual Average Hourly Electricity Demand by Region\nPJM, ERCOT, MISO  |  2019–2025", fontsize=13, pad=12)
ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel("Average Hourly Demand (MWh)", fontsize=11)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax.legend(fontsize=10)
ax.grid(axis="y", linestyle="--", alpha=0.5)
ax.set_xticks(annual_avg["year"].unique())

plt.tight_layout()
plt.savefig("outputs/demand_annual_avg_by_region.png", dpi=150, bbox_inches="tight")
plt.close()
print("✅ Chart 1 saved: outputs/demand_annual_avg_by_region.png")

# Chart 2: Indexed demand growth (2019 = 100)
base_year = 2019
base = annual_avg[annual_avg["year"] == base_year].set_index("region")["avg_hourly_demand_mwh"]

annual_avg["indexed"] = annual_avg.apply(
    lambda row: (row["avg_hourly_demand_mwh"] / base.get(row["region"], float("nan"))) * 100,
    axis=1
)

fig, ax = plt.subplots(figsize=(10, 6))

for region, grp in annual_avg.groupby("region"):
    ax.plot(
        grp["year"], grp["indexed"],
        marker="o", linewidth=2.5, markersize=6,
        color=COLORS.get(region, "gray"),
        label=LABELS.get(region, region),
    )

ax.axhline(100, color="black", linestyle="--", linewidth=1, alpha=0.4, label=f"Baseline ({base_year} = 100)")
ax.set_title(f"Indexed Electricity Demand Growth by Region\nPJM, ERCOT, MISO  |  {base_year} = 100", fontsize=13, pad=12)
ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel(f"Demand Index ({base_year} = 100)", fontsize=11)
ax.legend(fontsize=10)
ax.grid(axis="y", linestyle="--", alpha=0.5)
ax.set_xticks(annual_avg["year"].unique())

plt.tight_layout()
plt.savefig("outputs/demand_indexed_growth.png", dpi=150, bbox_inches="tight")
plt.close()
print("✅ Chart 2 saved: outputs/demand_indexed_growth.png")

# Chart 3: Monthly demand
monthly_avg = (
    df.groupby(["month", "region"])["mwh"]
    .mean()
    .reset_index()
)
monthly_avg["month_dt"] = monthly_avg["month"].dt.to_timestamp()

fig, ax = plt.subplots(figsize=(12, 6))

for region, grp in monthly_avg.groupby("region"):
    ax.plot(
        grp["month_dt"], grp["mwh"],
        linewidth=1.5, alpha=0.85,
        color=COLORS.get(region, "gray"),
        label=LABELS.get(region, region),
    )

ax.set_title("Monthly Average Hourly Demand by Region\nPJM, ERCOT, MISO  |  2019–2025", fontsize=13, pad=12)
ax.set_xlabel("Month", fontsize=11)
ax.set_ylabel("Average Hourly Demand (MWh)", fontsize=11)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax.legend(fontsize=10)
ax.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
plt.savefig("outputs/demand_monthly_by_region.png", dpi=150, bbox_inches="tight")
plt.close()
print("✅ Chart 3 saved: outputs/demand_monthly_by_region.png")

print("\n── Summary Statistics by Region ──────────────────────────────────────")
summary = (
    df.groupby("region")["mwh"]
    .agg(["count", "mean", "min", "max"])
    .rename(columns={"count": "n_hours", "mean": "avg_mwh", "min": "min_mwh", "max": "max_mwh"})
)
print(summary.to_string())
print()
print("── Annual Average Demand ──────────────────────────────────────────────")
print(annual_avg.pivot(index="year", columns="region", values="avg_hourly_demand_mwh").to_string())
print()
print("Done. All outputs saved to outputs/")