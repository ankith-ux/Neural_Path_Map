import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os

print("Loading geojson...")
geojson_path = "geojson/scored_segments_safe.geojson"
gdf = gpd.read_file(geojson_path)

print("Filtering and styling data...")
# Filter out roads with missing safety scores
gdf = gdf[gdf['safety_score'].notna()]

# Create a figure
fig, ax = plt.subplots(figsize=(16, 12), facecolor='#0f172a')
ax.set_facecolor('#0f172a')

# Define a custom colormap: Dark Red -> Orange -> Bright Amber/Yellow -> Bright Green
colors = ['#7f1d1d', '#dc2626', '#d97706', '#f59e0b', '#10b981']
n_bins = 100
cmap_name = 'safety_amber'
custom_cmap = mcolors.LinearSegmentedColormap.from_list(cmap_name, colors, N=n_bins)

# Plot low safety roads first (zorder lower)
low_safety = gdf[gdf['safety_score'] < 40]
low_safety.plot(ax=ax, color='#1e293b', linewidth=0.5, zorder=1, alpha=0.5)

# Plot higher safety roads with the colormap
high_safety = gdf[gdf['safety_score'] >= 40]
high_safety = high_safety.sort_values('safety_score') # plot highest scores on top

print("Plotting map...")
plot = high_safety.plot(
    ax=ax,
    column='safety_score',
    cmap=custom_cmap,
    linewidth=1.5,
    zorder=2,
    alpha=0.9,
    vmin=40,
    vmax=100
)

# Hard blocks
hard_blocks = gdf[gdf['safety_hard_block'] == True]
if not hard_blocks.empty:
    hard_blocks.plot(ax=ax, color='#ef4444', linewidth=1.5, zorder=3, linestyle='dashed')

# Add title and formatting
plt.title("Safest Paths and Areas in Bangalore", color='white', fontsize=20, pad=20, fontweight='bold')
ax.set_axis_off()

# Add annotations explaining the safety scoring
annotations = [
    (77.59, 13.07, "NH44 / Bellary Rd\nPrimary Arterial Corridor\n(High Base Score)"),
    (77.68, 12.93, "Outer Ring Road\nHeavy Connectivity\n& Mixed Use"),
    (77.63, 12.96, "Koramangala/Indiranagar\nDense Retail & Shops\n(High POI Density)"),
    (77.51, 13.03, "Peenya\nIndustrial Zone\n(-20% Safety Penalty)"),
    (77.595, 12.975, "Cubbon Park\nRecreation Landuse\n(Low Density Void)")
]

for lon, lat, text in annotations:
    ax.annotate(
        text,
        xy=(lon, lat),
        xytext=(15, 15),
        textcoords="offset points",
        color='white',
        fontsize=10,
        fontweight='bold',
        bbox=dict(boxstyle="round,pad=0.5", fc="#1e293b", ec="#f59e0b", lw=1.5, alpha=0.9),
        arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.2", color="#f59e0b", lw=1.5)
    )

# Save the figure
out_path = "safety_map.png"
print(f"Saving to {out_path}...")
plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor='none', dpi=300, bbox_inches='tight')
print("Done!")
