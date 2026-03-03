import pandas as pd
import matplotlib.pyplot as plt
import os

df = pd.read_csv("data/eia_demand_2018_2025.csv")

print("Shape:", df.shape)
print("\nColumns:", df.columns.tolist())
print("\nSample:\n", df.head(3))
print("\nUnique regions:", df["region"].unique())
print("Unique data types:", df["data_type_name"].unique())

demand = df[df["data_type_name"] == "Demand"].copy()
print(f"\nAfter filter: {len(demand):,} rows")

demand["period"] = pd.to_datetime(demand["datetime"])
demand["year"] = demand["period"].dt.year
demand["month"] = demand["period"].dt.month
demand = demand[demand["mwh"] < 500000].copy()

annual = (
    demand
    .groupby(["region", "year"])["mwh"]
    .mean()
    .reset_index()
    .rename(columns={"mwh": "avg_demand_mwh"})
)

print("\nAnnual averages:\n", annual.head(9))

os.makedirs("outputs", exist_ok=True)

fig, ax = plt.subplots(figsize=(10, 6))

colors = {"ERCO": "#E87722", "PJM": "#005EB8", "MISO": "#2CA02C"}

for region, group in annual.groupby("region"):
    ax.plot(
        group["year"],
        group["avg_demand_mwh"],
        marker="o",
        label=region,
        color=colors.get(region, "gray"),
        linewidth=2
    )

ax.set_title("Average Hourly Electricity Demand by Region (2019-2025)", fontsize=14)
ax.set_xlabel("Year")
ax.set_ylabel("Avg Hourly Demand (MWh)")
ax.legend(title="Balancing Authority")
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("outputs/demand_by_region.png", dpi=150)
plt.show()
print("\nChart saved to outputs/demand_by_region.png")