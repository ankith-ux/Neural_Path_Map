import json
import math

print("Loading geojson...")
with open("geojson/scored_segments_safe.geojson") as f:
    data = json.load(f)

print("Injecting mock data...")
for feature in data["features"]:
    props = feature["properties"]
    
    # Get rough center of segment
    coords = feature["geometry"]["coordinates"]
    if isinstance(coords[0], list):
        lon = sum(c[0] for c in coords) / len(coords)
        lat = sum(c[1] for c in coords) / len(coords)
    else:
        lon, lat = coords[0], coords[1]
        
    # Default
    lu_score = 0.0
    props["landuse"] = "unknown"
    poi = 0.0
    
    # Distance to Central (Koramangala/Indiranagar ~ 12.95, 77.62)
    dist_central = math.hypot(lat - 12.95, lon - 77.62)
    if dist_central < 0.04:
        lu_score = 0.3
        props["landuse"] = "commercial"
        poi = 0.8 * (1 - dist_central/0.04)
        
    # Distance to Peenya (Industrial ~ 13.03, 77.51)
    dist_peenya = math.hypot(lat - 13.03, lon - 77.51)
    if dist_peenya < 0.03:
        lu_score = -0.2
        props["landuse"] = "industrial"
        poi = 0.1
        
    # Distance to Whitefield (IT/Industrial ~ 12.96, 77.71)
    dist_whitefield = math.hypot(lat - 12.96, lon - 77.71)
    if dist_whitefield < 0.03:
        if lat > 12.97: # Upper whitefield
            lu_score = -0.2
            props["landuse"] = "industrial"
        else:
            lu_score = 0.3
            props["landuse"] = "commercial"
        poi = 0.4
        
    # Distance to Bellandur/ORR (12.93, 77.68)
    dist_bellandur = math.hypot(lat - 12.93, lon - 77.68)
    if dist_bellandur < 0.02:
        lu_score = 0.3
        props["landuse"] = "commercial"
        poi = 0.5
        
    # Parks (Cubbon Park: 12.975, 77.59)
    dist_cubbon = math.hypot(lat - 12.975, lon - 77.59)
    if dist_cubbon < 0.01:
        lu_score = 0.0
        props["landuse"] = "recreation_ground"
        poi = 0.05
        
    props["landuse_score"] = round(lu_score, 2)
    props["poi_density"] = round(poi, 3)
    
    # Recalculate safety score
    rc_score = props.get("road_class_score", 0.0)
    connectivity = float(props.get("composite_score", 50))
    is_lit = props.get("is_lit", False)
    is_dead_end = props.get("is_dead_end", False)
    hard_block = props.get("safety_hard_block", False)
    
    if hard_block:
        safety_score = 0.0
    else:
        safety = (
            0.45 * rc_score
            + 0.20 * poi
            + 0.15 * lu_score
            + 0.15 * (connectivity / 100.0)
            + 0.05 * (1.0 if is_lit else 0.0)
        )
        safety_score = round(min(max(safety, 0.0), 1.0) * 100, 1)
        if is_dead_end:
            safety_score = round(safety_score * 0.6, 1)
            
    props["safety_score"] = safety_score

print("Saving geojson...")
with open("geojson/scored_segments_safe.geojson", "w") as f:
    json.dump(data, f)
print("Done!")
