import requests
import json
payload = {
    "origin": {"lat": 13.01, "lng": 77.55},
    "destination": {"lat": 12.93, "lng": 77.62},
    "alpha": 0.5,
    "carrier": "composite",
    "persona": "safe"
}
res = requests.post("http://localhost:8000/api/route/score", json=payload)
data = res.json()
if "routes" in data and len(data["routes"]) > 0:
    print(data["routes"][0].keys())
else:
    print("No routes or error", data)
