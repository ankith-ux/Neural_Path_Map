import json

with open("geojson/scored_segments_safe.geojson") as f:
    features = json.load(f)["features"]

# Check if any stored landuse_score is negative
negative_landuse = [
    f["properties"]["landuse_score"] 
    for f in features 
    if f["properties"].get("landuse_score", 0) < 0
]
print(f"Segments with negative landuse_score stored: {len(negative_landuse)}")
print(f"Sample values: {negative_landuse[:5]}")
