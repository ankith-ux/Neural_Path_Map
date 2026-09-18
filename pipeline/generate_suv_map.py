import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection
import numpy as np

print("Loading GeoJSON...")
with open('/home/ankith/mahe_ws/geojson/scored_segments_safe.geojson', 'r') as f:
    data = json.load(f)

lines = []
colors = []
widths = []

print("Processing geometries...")
for feature in data['features']:
    props = feature.get('properties', {})
    geom = feature.get('geometry', {})
    if not geom or geom.get('type') != 'LineString':
        continue
        
    coords = geom.get('coordinates', [])
    if len(coords) < 2:
        continue
        
    suv_score = props.get('suv_score', 0)
    suv_hard_block = props.get('suv_hard_block', False)
    
    # Store line segments (x,y)
    lines.append(coords)
    
    if suv_hard_block:
        colors.append((1.0, 0.0, 0.0, 0.4)) # Red for hard blocked
        widths.append(0.5)
    else:
        # Normalize score 0-100 to 0-1
        norm_score = max(0, min(1, suv_score / 100.0))
        # Colormap: low score = dark/purple, high score = bright/yellow
        colors.append(plt.cm.plasma(norm_score))
        widths.append(0.5 + (norm_score * 1.5)) # Thicker lines for better SUV roads

print("Plotting map...")
fig, ax = plt.subplots(figsize=(20, 20), facecolor='black')
ax.set_facecolor('black')

lc = LineCollection(lines, colors=colors, linewidths=widths, alpha=0.8)
ax.add_collection(lc)

ax.autoscale()
ax.set_aspect('equal')
plt.axis('off')

out_path = '/home/ankith/.gemini/antigravity-ide/brain/8f56719f-ab7f-48b8-8f82-cad291dd6730/suv_map.png'
print(f"Saving to {out_path}...")
plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='black')
plt.close()
print("Done!")
