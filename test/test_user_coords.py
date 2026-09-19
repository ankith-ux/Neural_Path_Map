import requests

origin = {"lat": 12.978643563849122, "lng": 77.60695568937379}
dest = {"lat": 12.997759888407945, "lng": 77.59640449693538}

suv_routes = requests.post("http://localhost:8000/api/route/score", json={
    "origin": origin, "destination": dest, "persona": "suv", "alpha": 0.4
}).json()["routes"]

for r in suv_routes:
    print(f"Role={r.get('route_role')} BlendedRank={r.get('blended_rank_score')} handoffs={r.get('handoff_count')}")
