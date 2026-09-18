import json

print("Loading data...")
with open('/home/ankith/mahe_ws/geojson/scored_segments_safe.geojson', 'r') as f:
    data = json.load(f)

samples = {
    "1_high_score_arterial": None,
    "2_single_lane_oneway": None,
    "3_single_lane_bidirectional": None,
    "4_unclassified_inferred": None,
    "5_suv_hard_blocked": None
}

for feature in data['features']:
    props = feature.get('properties', {})
    
    # 1. High score arterial
    if samples["1_high_score_arterial"] is None and props.get("suv_score", 0) > 90 and props.get("road_class") in ["primary", "trunk"]:
        samples["1_high_score_arterial"] = props
        
    # 2. Single lane oneway
    if samples["2_single_lane_oneway"] is None and props.get("lane_count") == 1 and props.get("lane_score") == 0.6:
        samples["2_single_lane_oneway"] = props
        
    # 3. Single lane bidirectional
    if samples["3_single_lane_bidirectional"] is None and props.get("lane_count") == 1 and props.get("lane_score") == 0.2:
        samples["3_single_lane_bidirectional"] = props
        
    # 4. Unclassified inferred
    if samples["4_unclassified_inferred"] is None and props.get("road_class") == "unclassified" and props.get("lane_score") == 0.35:
        samples["4_unclassified_inferred"] = props
        
    # 5. SUV hard blocked
    if samples["5_suv_hard_blocked"] is None and props.get("suv_hard_block") is True:
        samples["5_suv_hard_blocked"] = props
        
    if all(v is not None for v in samples.values()):
        break

with open('/home/ankith/.gemini/antigravity-ide/brain/8f56719f-ab7f-48b8-8f82-cad291dd6730/sample_suv_data.json', 'w') as f:
    json.dump(samples, f, indent=2)

print("Samples saved.")
