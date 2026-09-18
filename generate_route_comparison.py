import requests
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import shape, LineString
import time

print("Waiting for backend...")
time.sleep(5)

payload = {
    "origin": {"lat": 13.01, "lng": 77.55}, # Malleshwaram/Yeshwanthpur area
    "destination": {"lat": 12.93, "lng": 77.62}, # Koramangala
    "alpha": 0.5,
    "carrier": "composite",
    "persona": "safe"
}

print("Fetching routes...")
res = requests.post("http://localhost:8000/api/route/score", json=payload)
data = res.json()
routes = data.get("routes", [])

if len(routes) < 2:
    print("Not enough alternative routes returned. Please try different coordinates.")
    exit(1)

routes_by_time = sorted(routes, key=lambda x: x["osrm_duration_seconds"])
fastest = routes_by_time[0]

routes_by_safety = sorted(routes, key=lambda x: x["safety_score"], reverse=True)
safest = routes_by_safety[0]

if fastest["route_id"] == safest["route_id"]:
    print("Fastest route is also safest route! Let's pick the least safe route for comparison.")
    safest = fastest
    fastest = routes_by_safety[-1]

f_geom = shape(fastest["geometry"])
s_geom = shape(safest["geometry"])

print(f"Fastest -> Time: {fastest['osrm_duration_seconds']/60:.1f}m, Safety: {fastest['safety_score']}")
print(f"Safest  -> Time: {safest['osrm_duration_seconds']/60:.1f}m, Safety: {safest['safety_score']}")

print("Plotting map...")
geojson_path = "geojson/scored_segments_safe.geojson"
gdf = gpd.read_file(geojson_path)
gdf = gdf[gdf['safety_score'].notna()]

# Define bounding box for the map based on the routes
minx = min(f_geom.bounds[0], s_geom.bounds[0]) - 0.02
miny = min(f_geom.bounds[1], s_geom.bounds[1]) - 0.02
maxx = max(f_geom.bounds[2], s_geom.bounds[2]) + 0.02
maxy = max(f_geom.bounds[3], s_geom.bounds[3]) + 0.02

# Filter GDF to bounding box to speed up plotting and zoom in
gdf_zoomed = gdf.cx[minx:maxx, miny:maxy]

fig, ax = plt.subplots(figsize=(12, 12), facecolor='#0f172a')
ax.set_facecolor('#0f172a')

# Base roads
base_roads = gdf_zoomed[gdf_zoomed['safety_score'] < 50]
base_roads.plot(ax=ax, color='#1e293b', linewidth=0.5, zorder=1, alpha=0.5)

# Safe roads
safe_roads = gdf_zoomed[gdf_zoomed['safety_score'] >= 50]
safe_roads.plot(ax=ax, column='safety_score', cmap='inferno', linewidth=1.5, zorder=2, alpha=0.4, vmin=0, vmax=100)

# Plot routes
gpd.GeoSeries([f_geom]).plot(ax=ax, color='#dc2626', linewidth=4, zorder=4, linestyle='dashed', label='Fastest Route')
gpd.GeoSeries([s_geom]).plot(ax=ax, color='#10b981', linewidth=5, zorder=5, label='Safest Route')

# Plot start and end
start_pt = gpd.GeoSeries([shape({"type": "Point", "coordinates": [77.55, 13.01]})])
end_pt = gpd.GeoSeries([shape({"type": "Point", "coordinates": [77.62, 12.93]})])
start_pt.plot(ax=ax, color='white', markersize=100, zorder=6, marker='o')
end_pt.plot(ax=ax, color='white', markersize=100, zorder=6, marker='X')

ax.set_xlim(minx, maxx)
ax.set_ylim(miny, maxy)

plt.title("Safest Route vs Fastest Route Comparison", color='white', fontsize=20, pad=20, fontweight='bold')
ax.set_axis_off()

import matplotlib.lines as mlines
l1 = mlines.Line2D([], [], color='#dc2626', linewidth=4, linestyle='dashed', 
                   label=f"Fastest Route ({fastest['osrm_duration_seconds']/60:.0f} mins | {fastest['distance_meters']/1000:.1f} km)\nSafety Score: {fastest['safety_score']}")
l2 = mlines.Line2D([], [], color='#10b981', linewidth=5, 
                   label=f"Safest Route ({safest['osrm_duration_seconds']/60:.0f} mins | {safest['distance_meters']/1000:.1f} km)\nSafety Score: {safest['safety_score']}")
ax.legend(handles=[l2, l1], loc='lower right', facecolor='#0f172a', edgecolor='white', labelcolor='white', fontsize=12)

out_path = "route_comparison.png"
print(f"Saving to {out_path}...")
plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor='none', dpi=300, bbox_inches='tight')
print("Done!")
