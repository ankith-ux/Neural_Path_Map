import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os

print("Loading geojson...")
geojson_path = "geojson/scored_segments_safe.geojson"
gdf = gpd.read_file(geojson_path)

print("Filtering data...")
gdf = gdf[gdf['safety_score'].notna()]

fig, ax = plt.subplots(figsize=(16, 12), facecolor='#0f172a')
ax.set_facecolor('#0f172a')

# 1. Base network (dim)
print("Plotting base network...")
base_roads = gdf[gdf['safety_score'] < 50]
base_roads.plot(ax=ax, color='#1e293b', linewidth=0.5, zorder=1, alpha=0.5)

# 2. Arterial/Safe corridors (Yellow/Amber)
safe_roads = gdf[(gdf['safety_score'] >= 50) & (gdf['poi_density'] < 0.2)]
safe_roads.plot(ax=ax, color='#f59e0b', linewidth=1.5, zorder=2, alpha=0.7)

# 3. High POI Density Corridors (Neon Pink/Cyan)
print("Plotting POI density overlays...")
poi_roads = gdf[gdf['poi_density'] >= 0.2]
poi_roads = poi_roads.sort_values('poi_density')
poi_roads.plot(ax=ax, column='poi_density', cmap='spring', linewidth=2.5, zorder=3, alpha=0.9, vmin=0, vmax=1)

# Annotations
plt.title("Why It's Safe: Shops & Commercial Density Overlay", color='white', fontsize=20, pad=20, fontweight='bold')
ax.set_axis_off()

# Legend proxy
import matplotlib.lines as mlines
l1 = mlines.Line2D([], [], color='#f59e0b', linewidth=2, label='Arterial Corridors (Base Safety)')
l2 = mlines.Line2D([], [], color='#ff00ff', linewidth=2.5, label='High POI/Shop Density (Activity Hubs)')
l3 = mlines.Line2D([], [], color='#1e293b', linewidth=1, label='Unlit/Residential/Dead-ends')
ax.legend(handles=[l2, l1, l3], loc='upper right', facecolor='#0f172a', edgecolor='white', labelcolor='white', fontsize=12)

out_path = "safety_map_poi_overlay.png"
print(f"Saving to {out_path}...")
plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor='none', dpi=300, bbox_inches='tight')
print("Done!")
