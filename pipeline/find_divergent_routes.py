import requests
import random
import time
import json

BBOX = {
    "min_lat": 12.92,
    "max_lat": 13.02,
    "min_lng": 77.55,
    "max_lng": 77.65
}

def random_coord():
    return {
        "lat": random.uniform(BBOX["min_lat"], BBOX["max_lat"]),
        "lng": random.uniform(BBOX["min_lng"], BBOX["max_lng"])
    }

def get_route(origin, dest, persona, alpha):
    try:
        resp = requests.post("http://localhost:8000/api/route/score", json={
            "origin": origin,
            "destination": dest,
            "persona": persona,
            "alpha": alpha
        }, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("routes", [])
    except Exception:
        pass
    return []

def get_role_geometry(routes, role_prefix):
    for r in routes:
        if r.get("route_role", "").startswith(role_prefix):
            return r.get("geometry")
    if routes:
        return routes[0].get("geometry")
    return None

print("Searching for divergent routes (Fastest vs Signal vs SUV)...")

found = 0
attempts = 0

for i in range(50):
    attempts += 1
    origin = random_coord()
    dest = random_coord()
    
    # 1. Fastest
    fastest_routes = get_route(origin, dest, "default", 1.0)
    fast_geom = get_role_geometry(fastest_routes, "fastest")
    
    # 2. Signal
    signal_routes = get_route(origin, dest, "default", 0.0)
    sig_geom = get_role_geometry(signal_routes, "best_signal")
    
    # 3. SUV
    suv_routes = get_route(origin, dest, "suv", 0.4)
    suv_geom = get_role_geometry(suv_routes, "suv_optimal")
    
    if not fast_geom or not sig_geom or not suv_geom:
        continue
        
    if fast_geom != sig_geom and fast_geom != suv_geom and sig_geom != suv_geom:
        print("\n=== BINGO! FOUND 3 COMPLETELY DIFFERENT ROUTES ===")
        print(f"Origin: {origin['lat']}, {origin['lng']}")
        print(f"Destination: {dest['lat']}, {dest['lng']}")
        
        # let's also print the scores
        def get_score(routes, role, key):
            for r in routes:
                if r.get("route_role", "").startswith(role):
                    return r.get(key)
            return routes[0].get(key) if routes else None
            
        print(f"Fastest route SUV score: {get_score(fastest_routes, 'fastest', 'suv_score')} - Duration: {get_score(fastest_routes, 'fastest', 'duration_seconds')}s")
        print(f"Signal route SUV score: {get_score(signal_routes, 'best_signal', 'suv_score')} - Duration: {get_score(signal_routes, 'best_signal', 'duration_seconds')}s")
        print(f"SUV route SUV score: {get_score(suv_routes, 'suv_optimal', 'suv_score')} - Duration: {get_score(suv_routes, 'suv_optimal', 'duration_seconds')}s")
        
        found += 1
        break

if not found:
    print("Could not find a perfect 3-way split.")
