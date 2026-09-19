import requests
import json
payload = {
    "origin": {"lat": 12.9600, "lng": 77.6400},
    "destination": {"lat": 12.9300, "lng": 77.6200},
    "alpha": 0.0,
    "carrier": "composite",
    "persona": "safe"
}
try:
    res = requests.post("http://localhost:8000/api/route/score", json=payload)
    data = res.json()
    print(f"Got {len(data.get('routes', []))} routes.")
    if data.get('routes'):
        geom = data['routes'][0].get('geometry')
        print(f"Geometry type: {type(geom)}")
        if isinstance(geom, dict):
            print(f"GeoJSON keys: {geom.keys()}")
        elif isinstance(geom, str):
            print("It's a polyline string.")
except Exception as e:
    print(e)
