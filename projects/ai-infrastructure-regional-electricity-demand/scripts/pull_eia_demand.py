import requests
import os
import pandas as pd
import time
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")
REGIONS = ["ERCO", "PJM", "MISO"]
YEARS = list(range(2019, 2026))
BASE_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"

def pull_region_year(region, year):
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    all_records = []
    offset = 0
    page_size = 5000
    while True:
        params = {
            "api_key": API_KEY,
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": region,
            "start": start,
            "end": end,
            "length": page_size,
            "offset": offset
        }
        try:
            response = requests.get(BASE_URL, params=params, timeout=60)
            try:
                data = response.json()
            except Exception:
                print(f"  Bad response, retrying in 30s...")
                time.sleep(30)
                continue
            records = data["response"]["data"]
            all_records.extend(records)
            total = int(data["response"]["total"])
            offset += page_size
            print(f"  {region} {year}: pulled {min(offset, total)}/{total} records")
            if offset >= total:
                break
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error: {e}, retrying in 30s...")
            time.sleep(30)
    return all_records

def main():
    all_data = []
    for region in REGIONS:
        for year in YEARS:
            print(f"Pulling {region} {year}...")
            records = pull_region_year(region, year)
            all_data.extend(records)
            time.sleep(1)
    df = pd.DataFrame(all_data)
    df = df.rename(columns={
        "period": "datetime",
        "respondent": "region",
        "respondent-name": "region_name",
        "type": "data_type",
        "type-name": "data_type_name",
        "value": "mwh",
        "value-units": "units"
    })
    output_path = "data/eia_demand_2018_2025.csv"
    df.to_csv(output_path, index=False)
    print(f"\nDone. {len(df)} records saved to {output_path}")
    print(df.head())

if __name__ == "__main__":
    main()