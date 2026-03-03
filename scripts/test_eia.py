import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")

url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
params = {
    "api_key": API_KEY,
    "frequency": "hourly",
    "data[0]": "value",
    "facets[respondent][]": "ERCO",
    "start": "2024-01-01",
    "end": "2024-01-07",
    "length": 10
}

response = requests.get(url, params=params)
data = response.json()

# Print clean summary
records = data["response"]["data"]
print(f"Total records available: {data['response']['total']}")
print(f"Records returned: {len(records)}\n")
for r in records[:5]:
    print(f"{r['period']}  |  {r['type-name']:<30}  |  {r['value']} {r['value-units']}")