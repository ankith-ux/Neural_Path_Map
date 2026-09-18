import requests
import random
import time

def find_diverging():
    # Bangalore bounds roughly: 12.85 to 13.10 lat, 77.50 to 77.70 lon
    
    attempts = 0
    while attempts < 50:
        attempts += 1
        lat1 = round(random.uniform(12.88, 13.05), 4)
        lon1 = round(random.uniform(77.52, 77.68), 4)
        lat2 = round(random.uniform(12.88, 13.05), 4)
        lon2 = round(random.uniform(77.52, 77.68), 4)
        
        # Ensure they are somewhat far apart (at least 0.05 degrees ~ 5km)
        if abs(lat1 - lat2) + abs(lon1 - lon2) < 0.05:
            continue
            
        payload = {
            "origin": {"lat": lat1, "lng": lon1},
            "destination": {"lat": lat2, "lng": lon2},
            "alpha": 0.5,
            "carrier": "composite",
            "persona": "safe_commute" # Requests 4 alternatives in main.py
        }
        
        try:
            res = requests.post("http://localhost:8000/api/route/score", json=payload, timeout=5)
            data = res.json()
            routes = data.get("routes", [])
            
            if len(routes) >= 3:
                # Find fastest
                fastest = min(routes, key=lambda x: x["osrm_duration_seconds"])
                # Find best signal
                best_signal = max(routes, key=lambda x: x["connectivity_score"])
                # Find safest
                safest = max(routes, key=lambda x: x["safety_score"])
                
                f_id = fastest["route_id"]
                sig_id = best_signal["route_id"]
                safe_id = safest["route_id"]
                
                # Check if all 3 are distinct routes
                if f_id != sig_id and f_id != safe_id and sig_id != safe_id:
                    print(f"✅ FOUND PERFECT COORDINATES!")
                    print(f"Origin: [{lon1}, {lat1}]")
                    print(f"Destination: [{lon2}, {lat2}]")
                    print(f"  Fastest: {f_id} ({fastest['osrm_duration_seconds']}s)")
                    print(f"  Signal:  {sig_id} (Score: {best_signal['connectivity_score']})")
                    print(f"  Safest:  {safe_id} (Score: {safest['safety_score']})")
                    return
        except Exception as e:
            pass
            
    print("Could not find a naturally diverging 3-way route in 50 attempts.")

find_diverging()
