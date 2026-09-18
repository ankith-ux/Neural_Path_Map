#!/usr/bin/env python3
"""
extract_safety_features.py
─────────────────────────
Augments scored_segments.geojson with the Three Pillars of Night Safety:
  1. Are people around?  (road_class, poi_density, landuse)
  2. Can you be seen?    (lit)
  3. Can you escape?     (connectivity + dead_end)

Produces: geojson/scored_segments_safe.geojson

Usage:
    python3 pipeline/extract_safety_features.py
"""

import json
import math
import re
import time
import requests
import numpy as np
from pathlib import Path
from collections import defaultdict

try:
    import osmnx as ox
    from scipy.spatial import KDTree
    from shapely.geometry import Point, shape as geo_shape
    from shapely.strtree import STRtree
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install osmnx scipy shapely")
    raise SystemExit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
GEOJSON_DIR = PROJECT_ROOT / "geojson"
DATA_DIR = PROJECT_ROOT / "data_bnglr"

INPUT_GEOJSON = GEOJSON_DIR / "scored_segments.geojson"
OUTPUT_GEOJSON = GEOJSON_DIR / "scored_segments_safe.geojson"
GRAPH_PATH = DATA_DIR / "bangalore_graph.graphml"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
BBOX = "12.834,77.469,13.139,77.748"  # south,west,north,east

# ── Road class scoring ────────────────────────────────────────────────────────
ROAD_CLASS_SCORE = {
    "motorway": 1.0, "motorway_link": 1.0,
    "trunk": 1.0, "trunk_link": 1.0,
    "primary": 1.0, "primary_link": 1.0,
    "secondary": 0.8, "secondary_link": 0.8,
    "tertiary": 0.6, "tertiary_link": 0.6,
    "residential": 0.4,
    "unclassified": 0.2,
    "living_street": 0.3,
    "service": 0.2,
}

# Hard-blocked road types at night
HARD_BLOCK_HIGHWAY = {"track", "path", "steps", "footway", "cycleway", "bridleway"}

# ── Landuse scoring ───────────────────────────────────────────────────────────
LANDUSE_SCORE = {
    "commercial": 0.3, "retail": 0.3,
    "residential": 0.2,
    "education": 0.2,
    "institutional": 0.2,
    "religious": 0.1,
    "recreation_ground": 0.0,
    "industrial": -0.2, "construction": -0.2,
    "landfill": -0.3,
}

HARD_BLOCK_LANDUSE = {"farmland", "forest", "quarry", "meadow", "orchard", "vineyard"}

# ── SUV scoring ───────────────────────────────────────────────────────────────
SUV_ROAD_CLASS_SCORE = {
    "motorway": 1.0, "motorway_link": 1.0,
    "trunk": 1.0, "trunk_link": 1.0,
    "primary": 0.9, "primary_link": 0.9,
    "secondary": 0.7, "secondary_link": 0.7,
    "tertiary": 0.5, "tertiary_link": 0.5,
    "residential": 0.2,
    "unclassified": 0.1,
    "service": 0.1,
    "living_street": 0.05,
}

SUV_SURFACE_SCORE = {
    "asphalt": 1.0, "concrete": 1.0, "paved": 1.0,
    "paving_stones": 0.8,
    "cobblestone": 0.5, "sett": 0.5,
    "compacted": 0.3, "fine_gravel": 0.3,
    "unpaved": 0.1, "ground": 0.1,
}

SUV_HARD_BLOCK_SURFACE = {"dirt", "mud", "grass", "sand"}
SUV_HARD_BLOCK_HIGHWAY = {"track", "path", "footway", "steps", "cycleway", "bridleway"}

SUV_LANE_SCORE = {1: 0.2, 2: 0.6, 3: 0.8, 4: 1.0}


def parse_metres(value):
    """Parse OSM width/height/weight tags safely."""
    if value is None:
        return None
    value = str(value).strip()
    # Handle feet/inches: 8'2" → metres
    feet_match = re.match(r"(\d+)'(\d+)\"?", value)
    if feet_match:
        feet = int(feet_match.group(1))
        inches = int(feet_match.group(2))
        return round((feet * 12 + inches) * 0.0254, 2)
    # Strip units and parse float: "2.5 m", "2.5m", "2.5"
    numeric = re.sub(r"[^\d.]", "", value)
    try:
        return float(numeric)
    except ValueError:
        return None  # unparseable → treat as no restriction


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Build road-class lookup from OSMnx graph
# ══════════════════════════════════════════════════════════════════════════════

def build_road_class_lookup():
    """Build dicts: osm_way_id → highway type, and vehicle features from the GraphML."""
    print("[1/5] Loading OSMnx graph for road class lookup...")
    G = ox.load_graphml(GRAPH_PATH)

    way_highway = {}
    vehicle_features = {}  # osm_way_id → {lanes, oneway, surface, maxwidth, ...}
    dead_end_nodes = set()

    # Detect dead-end nodes (degree 1 in undirected view)
    G_undir = G.to_undirected()
    for node, deg in G_undir.degree():
        if deg == 1:
            dead_end_nodes.add(node)

    dead_end_ways = set()

    for u, v, edata in G.edges(data=True):
        osmid = edata.get("osmid", f"{u}_{v}")
        highway = edata.get("highway", "residential")
        if isinstance(highway, list):
            highway = highway[0]

        # Extract vehicle-relevant fields (single pass)
        lanes_raw = edata.get("lanes", None)
        if isinstance(lanes_raw, list):
            lanes_raw = lanes_raw[0]
        oneway = edata.get("oneway", False)
        if isinstance(oneway, str):
            oneway = oneway.lower() in ("true", "yes", "1")
        surface = edata.get("surface", None)
        if isinstance(surface, list):
            surface = surface[0]
        maxwidth = edata.get("maxwidth", None)
        maxheight = edata.get("maxheight", None)
        maxweight = edata.get("maxweight", None)
        access = edata.get("access", None)
        if isinstance(access, list):
            access = access[0]
        motor_vehicle = edata.get("motor_vehicle", None)
        if isinstance(motor_vehicle, list):
            motor_vehicle = motor_vehicle[0]

        vf = {
            "lanes": lanes_raw,
            "oneway": bool(oneway),
            "surface": surface,
            "maxwidth": maxwidth,
            "maxheight": maxheight,
            "maxweight": maxweight,
            "access": access,
            "motor_vehicle": motor_vehicle,
        }

        ids = [osmid] if not isinstance(osmid, list) else osmid
        for oid in ids:
            sid = str(oid)
            way_highway[sid] = highway
            vehicle_features[sid] = vf
            if u in dead_end_nodes or v in dead_end_nodes:
                dead_end_ways.add(sid)

    print(f"  Road class lookup: {len(way_highway)} ways")
    print(f"  Vehicle features:  {len(vehicle_features)} ways")
    print(f"  Dead-end segments: {len(dead_end_ways)} ways")
    return way_highway, dead_end_ways, vehicle_features


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Overpass queries
# ══════════════════════════════════════════════════════════════════════════════

def overpass_query(query, label):
    """Execute an Overpass query with fallback endpoints and retry."""
    print(f"  Querying Overpass for {label}...")
    headers = {"User-Agent": "Antigravity-IDE/1.0 (ankith@example.com)"}
    
    for url in OVERPASS_ENDPOINTS:
        print(f"  Trying endpoint: {url}")
        for attempt in range(2):
            try:
                resp = requests.post(url, data={"data": query}, headers=headers, timeout=300)
                resp.raise_for_status()
                data = resp.json()
                print(f"  Got {len(data.get('elements', []))} {label} elements")
                return data.get("elements", [])
            except Exception as e:
                print(f"  Attempt {attempt + 1} at {url} failed: {e}")
                if attempt < 1:
                    time.sleep(5)
    
    print(f"  WARNING: All endpoints failed to fetch {label}, continuing without it")
    return []


def fetch_overpass_data():
    """Fetch all safety-relevant data from Overpass API."""
    print("[2/5] Fetching safety data from Overpass API...")

    # 2a: Landuse polygons
    landuse_query = f"""
    [out:json][timeout:300];
    (
      way["landuse"~"commercial|retail|residential|industrial|farmland|forest|quarry|construction|meadow|orchard|landfill|education|institutional|recreation_ground|religious"]({BBOX});
      relation["landuse"~"commercial|retail|residential|industrial|farmland|forest|quarry|construction|meadow|orchard|landfill|education|institutional|recreation_ground|religious"]({BBOX});
    );
    out body;
    >;
    out skel qt;
    """
    landuse_elements = overpass_query(landuse_query, "landuse")

    # 2b: POIs (amenity + shop nodes)
    poi_query = f"""
    [out:json][timeout:300];
    (
      node["amenity"]({BBOX});
      node["shop"]({BBOX});
    );
    out body;
    """
    poi_elements = overpass_query(poi_query, "POI (amenity+shop)")

    # 2c: Lit roads
    lit_query = f"""
    [out:json][timeout:300];
    way["lit"="yes"]({BBOX});
    out body;
    """
    lit_elements = overpass_query(lit_query, "lit roads")

    # 2d: Dead-end nodes (noexit=yes)
    noexit_query = f"""
    [out:json][timeout:300];
    node["noexit"="yes"]({BBOX});
    out body;
    """
    noexit_elements = overpass_query(noexit_query, "noexit nodes")

    return landuse_elements, poi_elements, lit_elements, noexit_elements


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Process Overpass data into spatial indices
# ══════════════════════════════════════════════════════════════════════════════

def build_spatial_indices(landuse_elements, poi_elements, lit_elements, noexit_elements):
    """Build KDTree/STRtree indices for spatial lookups."""
    print("[3/5] Building spatial indices...")

    # 3a: Parse landuse polygons
    nodes_lookup = {}
    for el in landuse_elements:
        if el["type"] == "node":
            nodes_lookup[el["id"]] = (el["lon"], el["lat"])

    landuse_polys = []
    landuse_types = []
    for el in landuse_elements:
        if el["type"] == "way" and "tags" in el and "landuse" in el.get("tags", {}):
            coords = [nodes_lookup[nid] for nid in el.get("nodes", []) if nid in nodes_lookup]
            if len(coords) >= 4:
                try:
                    poly = geo_shape({"type": "Polygon", "coordinates": [coords]})
                    if poly.is_valid and poly.area > 0:
                        landuse_polys.append(poly)
                        landuse_types.append(el["tags"]["landuse"])
                except Exception:
                    continue

    landuse_tree = STRtree(landuse_polys) if landuse_polys else None
    print(f"  Landuse polygons: {len(landuse_polys)}")

    # 3b: POI KDTree
    poi_coords = []
    for el in poi_elements:
        if el["type"] == "node" and "lat" in el and "lon" in el:
            poi_coords.append([el["lat"], el["lon"]])

    poi_kdtree = KDTree(poi_coords) if poi_coords else None
    print(f"  POI nodes: {len(poi_coords)}")

    # 3c: Lit road way IDs
    lit_way_ids = set()
    for el in lit_elements:
        if el["type"] == "way":
            lit_way_ids.add(str(el["id"]))
    print(f"  Lit road ways: {len(lit_way_ids)}")

    # 3d: Noexit node coordinates
    noexit_coords = []
    for el in noexit_elements:
        if el["type"] == "node" and "lat" in el and "lon" in el:
            noexit_coords.append([el["lat"], el["lon"]])

    noexit_kdtree = KDTree(noexit_coords) if noexit_coords else None
    print(f"  Noexit nodes: {len(noexit_coords)}")

    return (landuse_tree, landuse_polys, landuse_types,
            poi_kdtree, len(poi_coords),
            lit_way_ids,
            noexit_kdtree)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Score each segment
# ══════════════════════════════════════════════════════════════════════════════

def compute_poi_density(lat, lon, poi_kdtree, total_pois, radius_deg=0.00135):
    """Count POIs within ~150m, normalize to 0-1."""
    if poi_kdtree is None:
        return 0.0
    # 150m ≈ 0.00135 degrees at Bangalore's latitude
    count = len(poi_kdtree.query_ball_point([lat, lon], radius_deg))
    # Normalize: 25+ POIs within 150m → 1.0 (Bangalore dense commercial area)
    return min(count / 25.0, 1.0)


def lookup_landuse(lat, lon, landuse_tree, landuse_polys, landuse_types):
    """Find which landuse polygon contains this point."""
    if landuse_tree is None:
        return "unknown"
    pt = Point(lon, lat)
    hits = landuse_tree.query(pt)
    for idx in hits:
        if landuse_polys[idx].contains(pt):
            return landuse_types[idx]
    return "unknown"


def is_near_noexit(lat, lon, noexit_kdtree, radius_deg=0.0005):
    """Check if within ~55m of a noexit node."""
    if noexit_kdtree is None:
        return False
    count = len(noexit_kdtree.query_ball_point([lat, lon], radius_deg))
    return count > 0


def compute_safety_score(road_class_score, poi_density, landuse_score,
                         connectivity_score, is_lit):
    """Apply the Three Pillars formula."""
    safety = (
        0.45 * road_class_score
        + 0.20 * poi_density
        + 0.15 * landuse_score  # allow negative scores to penalize
        + 0.15 * (connectivity_score / 100.0)
        + 0.05 * (1.0 if is_lit else 0.0)
    )
    return round(min(max(safety, 0.0), 1.0) * 100, 1)  # scale to 0-100


def compute_suv_score(highway, vf, connectivity_score):
    """
    Compute SUV suitability score for a segment.
    Returns (suv_score: float 0-100, suv_hard_block: bool,
             lane_count: int, lane_score: float, surface: str, surface_score: float).
    """
    # ── Hard blocks ──
    suv_hard_block = False

    # Highway type hard block
    if highway in SUV_HARD_BLOCK_HIGHWAY:
        suv_hard_block = True

    # Access restrictions
    access = vf.get("access")
    if access in ("no", "private"):
        suv_hard_block = True
    motor_vehicle = vf.get("motor_vehicle")
    if motor_vehicle == "no":
        suv_hard_block = True

    # Physical restrictions (parsed safely)
    mw = parse_metres(vf.get("maxwidth"))
    if mw is not None and mw < 2.5:
        suv_hard_block = True
    mh = parse_metres(vf.get("maxheight"))
    if mh is not None and mh < 2.2:
        suv_hard_block = True
    mwt = parse_metres(vf.get("maxweight"))
    if mwt is not None and mwt < 2.5:
        suv_hard_block = True

    # Surface hard block
    surface_raw = vf.get("surface")
    if isinstance(surface_raw, str) and surface_raw.lower() in SUV_HARD_BLOCK_SURFACE:
        suv_hard_block = True

    if suv_hard_block:
        return (0.0, True, 0, 0.0, surface_raw or "unknown", 0.0)

    # ── Road class score ──
    rc_score = SUV_ROAD_CLASS_SCORE.get(highway, 0.1)

    # ── Lane score (with oneway fix) ──
    lanes_raw = vf.get("lanes")
    oneway = vf.get("oneway", False)

    if lanes_raw is not None:
        try:
            lane_count = int(float(str(lanes_raw)))
        except (ValueError, TypeError):
            lane_count = None
    else:
        lane_count = None

    # Infer lanes from road class when missing
    if lane_count is None:
        if highway in ("motorway", "trunk"):
            lane_count = 4
        elif highway in ("primary",):
            lane_count = 3
        elif highway in ("secondary", "tertiary"):
            lane_count = 2
        else:
            lane_count = 1

    # Unclassified roads: use distinct score instead of harsh 1-lane penalty
    if highway == "unclassified" and lanes_raw is None:
        lane_score = 0.35
    elif lane_count == 1:
        lane_score = 0.6 if oneway else 0.2  # Oneway fix
    elif lane_count >= 4:
        lane_score = 1.0
    else:
        lane_score = SUV_LANE_SCORE.get(lane_count, 0.6)

    # ── Surface score ──
    if surface_raw is not None:
        surface_str = str(surface_raw).lower().strip()
        surface_score = SUV_SURFACE_SCORE.get(surface_str, 0.4)
    else:
        # Infer from road class
        surface_str = "inferred"
        if highway in ("motorway", "trunk", "primary", "secondary"):
            surface_score = 1.0
        elif highway in ("tertiary", "residential"):
            surface_score = 0.8
        else:
            surface_score = 0.4

    # ── Connectivity score ──
    conn_norm = connectivity_score / 100.0

    # ── Composite ──
    suv = (
        0.35 * rc_score
        + 0.30 * lane_score
        + 0.20 * surface_score
        + 0.15 * conn_norm
    )
    suv_score = round(min(max(suv, 0.0), 1.0) * 100, 1)

    return (suv_score, False, lane_count, round(lane_score, 2),
            surface_str, round(surface_score, 2))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Main — augment scored_segments.geojson
# ══════════════════════════════════════════════════════════════════════════════

def main():
    t_start = time.time()

    # Load existing scored segments
    print(f"Loading {INPUT_GEOJSON}...")
    with open(INPUT_GEOJSON) as f:
        geojson = json.load(f)

    features = geojson["features"]
    print(f"  {len(features)} segments loaded")

    # Step 1: Road class + vehicle features from graph
    way_highway, dead_end_ways, vehicle_features = build_road_class_lookup()

    # Step 2: Overpass data
    landuse_elements, poi_elements, lit_elements, noexit_elements = fetch_overpass_data()

    # Step 3: Spatial indices
    (landuse_tree, landuse_polys, landuse_types,
     poi_kdtree, total_pois,
     lit_way_ids,
     noexit_kdtree) = build_spatial_indices(
        landuse_elements, poi_elements, lit_elements, noexit_elements
    )

    # Step 4: Score each segment
    print(f"[4/5] Computing safety scores for {len(features)} segments...")
    stats = defaultdict(int)

    for i, feature in enumerate(features):
        props = feature["properties"]
        way_id = str(props["osm_way_id"])

        # Get midpoint from geometry
        coords = feature["geometry"]["coordinates"]
        if coords:
            mid = coords[len(coords) // 2]
            lon, lat = mid[0], mid[1]
        else:
            lon, lat = 77.59, 12.97

        # ── Pillar 1: Are people around? ──
        highway = way_highway.get(way_id, "residential")
        rc_score = ROAD_CLASS_SCORE.get(highway, 0.2)
        poi_density = compute_poi_density(lat, lon, poi_kdtree, total_pois)
        landuse = lookup_landuse(lat, lon, landuse_tree, landuse_polys, landuse_types)
        lu_score = LANDUSE_SCORE.get(landuse, 0.0)

        # ── Pillar 2: Can you be seen? ──
        is_lit = way_id in lit_way_ids

        # ── Pillar 3: Can you escape? ──
        connectivity = float(props.get("composite_score", 50))
        is_dead_end = (way_id in dead_end_ways) or is_near_noexit(lat, lon, noexit_kdtree)

        # ── Hard blocks ──
        hard_block = False
        if highway in HARD_BLOCK_HIGHWAY:
            hard_block = True
            stats["hard_block_highway"] += 1
        if landuse in HARD_BLOCK_LANDUSE:
            hard_block = True
            stats["hard_block_landuse"] += 1

        # ── Final score ──
        if hard_block:
            safety_score = 0.0
        else:
            safety_score = compute_safety_score(
                rc_score, poi_density, lu_score, connectivity, is_lit
            )
            # Soft penalty for dead ends instead of hard block
            if is_dead_end:
                safety_score = round(safety_score * 0.6, 1)

        # ── SUV score ──
        vf = vehicle_features.get(way_id, {})
        (suv_score_val, suv_hb, lane_count, lane_score_val,
         surface_val, surface_score_val) = compute_suv_score(
            highway, vf, connectivity
        )

        # Add new properties (preserving ALL existing ones)
        props["road_class"] = highway
        props["road_class_score"] = round(rc_score, 2)
        props["poi_density"] = round(poi_density, 3)
        props["landuse"] = landuse
        props["landuse_score"] = round(lu_score, 2)
        props["is_lit"] = is_lit
        props["is_dead_end"] = is_dead_end
        props["safety_score"] = safety_score
        props["safety_hard_block"] = hard_block
        # SUV fields
        props["lane_count"] = lane_count
        props["lane_score"] = lane_score_val
        props["surface"] = surface_val
        props["surface_score"] = surface_score_val
        props["suv_score"] = suv_score_val
        props["suv_hard_block"] = suv_hb

        if is_lit:
            stats["lit"] += 1
        if is_dead_end:
            stats["dead_end"] += 1
        if suv_hb:
            stats["suv_hard_block"] += 1

        if (i + 1) % 50000 == 0:
            print(f"  Processed {i + 1}/{len(features)}...")

    # Step 5: Save
    print(f"[5/5] Saving to {OUTPUT_GEOJSON}...")
    with open(OUTPUT_GEOJSON, "w") as f:
        json.dump(geojson, f)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"Done in {elapsed:.1f}s")
    print(f"  Total segments:       {len(features)}")
    print(f"  Lit roads:            {stats['lit']}")
    print(f"  Dead ends:            {stats['dead_end']}")
    print(f"  Hard-blocked (road):  {stats['hard_block_highway']}")
    print(f"  Hard-blocked (land):  {stats['hard_block_landuse']}")
    print(f"  Hard-blocked (dead):  {stats['hard_block_dead_end']}")
    print(f"  SUV hard-blocked:     {stats['suv_hard_block']}")

    # SUV distribution
    suv_scores = [f["properties"]["suv_score"] for f in features if not f["properties"].get("suv_hard_block")]
    if suv_scores:
        print(f"\n  SUV score distribution (non-blocked):")
        print(f"    min={min(suv_scores):.1f}  mean={np.mean(suv_scores):.1f}  "
              f"median={np.median(suv_scores):.1f}  max={max(suv_scores):.1f}")

    # Quick distribution
    scores = [f["properties"]["safety_score"] for f in features if not f["properties"]["safety_hard_block"]]
    if scores:
        print(f"\n  Safety score distribution (non-blocked):")
        print(f"    min={min(scores):.1f}  mean={np.mean(scores):.1f}  "
              f"median={np.median(scores):.1f}  max={max(scores):.1f}")

    print(f"\nOutput: {OUTPUT_GEOJSON}")


if __name__ == "__main__":
    main()
