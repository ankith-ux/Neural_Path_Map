import json

INPUT_GEOJSON = "geojson/scored_segments_safe.geojson"

with open(INPUT_GEOJSON) as f:
    data = json.load(f)

for feature in data["features"]:
    props = feature["properties"]
    
    # Re-derive raw values
    rc_score = props.get("road_class_score", 0.0)
    
    # Old poi_density = min(count / 10.0, 1.0). If it's < 1.0, we know the exact count!
    # If it's 1.0, count >= 10. We can just multiply by 10 and divide by 25.
    old_poi = props.get("poi_density", 0.0)
    count = old_poi * 10.0
    new_poi = min(count / 25.0, 1.0)
    props["poi_density"] = round(new_poi, 3)
    
    lu_score = props.get("landuse_score", 0.0)
    is_lit = props.get("is_lit", False)
    connectivity = float(props.get("composite_score", 50))
    is_dead_end = props.get("is_dead_end", False)
    
    # Hard blocks
    hard_block = False
    if props.get("road_class") in {"track", "path", "steps", "footway", "cycleway", "bridleway"}:
        hard_block = True
    if props.get("landuse") in {"farmland", "forest", "quarry", "meadow", "orchard", "vineyard"}:
        hard_block = True
    # WE REMOVED DEAD END HARD BLOCK HERE
    
    if hard_block:
        safety_score = 0.0
    else:
        safety = (
            0.45 * rc_score
            + 0.20 * new_poi
            + 0.15 * lu_score  # No flooring!
            + 0.15 * (connectivity / 100.0)
            + 0.05 * (1.0 if is_lit else 0.0)
        )
        safety_score = round(min(max(safety, 0.0), 1.0) * 100, 1)
        
        # Soft penalty for dead ends
        if is_dead_end:
            safety_score = round(safety_score * 0.6, 1)
            
    props["safety_score"] = safety_score
    props["safety_hard_block"] = hard_block

with open(INPUT_GEOJSON, "w") as f:
    json.dump(data, f)
    
print("Updated scored_segments_safe.geojson in-place successfully!")
