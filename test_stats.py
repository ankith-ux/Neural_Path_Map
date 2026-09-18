import json
import numpy as np

with open("geojson/scored_segments_safe.geojson") as f:
    features = json.load(f)["features"]

props = [f["properties"] for f in features if not f["properties"].get("safety_hard_block")]

print("road_class_score  mean:", np.mean([p.get("road_class_score", 0) for p in props]))
print("poi_density       mean:", np.mean([p.get("poi_density", 0) for p in props]))
print("landuse_score     mean:", np.mean([p.get("landuse_score", 0) for p in props]))
print("lit %            :", sum(1 for p in props if p.get("is_lit")) / len(props) * 100)
