import requests

origin = {"lat": 12.978643563849122, "lng": 77.60695568937379}
dest = {"lat": 12.997759888407945, "lng": 77.59640449693538}

default_routes = requests.post("http://localhost:8000/api/route/score", json={
    "origin": origin, "destination": dest, "persona": "default", "alpha": 0.0
}).json()["routes"]

for r in default_routes:
    print(f"Role={r.get('route_role')} Conn_Score={r.get('connectivity_score')} BlendedRank={r.get('blended_rank_score')} handoffs={r.get('handoff_count')}")
