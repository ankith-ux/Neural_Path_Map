import osmnx as ox
# Set timeout to 300
ox.settings.timeout = 300
bbox = (13.139, 12.834, 77.748, 77.469) # north, south, east, west
try:
    print("Testing osmnx features...")
    tags = {'amenity': True, 'shop': True}
    gdf = ox.features_from_bbox(bbox, tags=tags)
    print(f"Success! Got {len(gdf)} features")
except Exception as e:
    print(f"Failed: {e}")
