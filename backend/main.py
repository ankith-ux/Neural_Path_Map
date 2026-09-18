"""
backend/main.py
FastAPI application entry point for the Connectivity Intelligence Platform.

USAGE:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    POST /api/route/score       — Score routes between origin/destination
    POST /api/route/rerank      — Re-rank cached routes with new alpha
    GET  /api/heat/tiles        — H3 heatmap tiles for carrier
    GET  /api/segment/{id}/explain — Natural language segment explanation
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ──────────────────────────────────────────────────────────────────────────────
# APP CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Connectivity Intelligence Platform",
    description="Predict. Prepare. Never drop.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE (loaded at startup)
# ──────────────────────────────────────────────────────────────────────────────

SEGMENT_DICT = {}       # osm_way_id -> properties dict
H3_TILES = {}           # carrier -> {h3_id -> {score, confidence, center}}
GRAPH = None            # OSMnx graph (optional)

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent

# Let `uvicorn backend.main:app` and `cd backend && uvicorn main:app` both work.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _resolve_existing_path(env_var: str, *candidates: str) -> Optional[Path]:
    """Return the first existing path, allowing env var overrides for local setups."""
    override = os.getenv(env_var)
    if override:
        override_path = Path(override).expanduser()
        if override_path.exists():
            return override_path

    for candidate in candidates:
        candidate_path = BASE_DIR / candidate
        if candidate_path.exists():
            return candidate_path

    return None


GEOJSON_PATH = _resolve_existing_path(
    "SCORED_SEGMENTS_PATH",
    "geojson/scored_segments_safe.geojson",
    "geojson/scored_segments.geojson",
    "geojson/bangalore_scored_segments.geojson",
    "scored_segments.geojson",
    "data/output/bangalore_scored_segments.geojson",
    "data/output/scored_segments.geojson",
)
GRAPH_PATH = _resolve_existing_path(
    "GRAPH_PATH",
    "geojson/bangalore_graph.graphml",
    "data/bangalore_graph.graphml",
    "bangalore_graph.graphml",
    "data/processed/bangalore_graph.graphml",
)


# ──────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────────────────────────────────────

class LatLng(BaseModel):
    lat: float
    lng: float

class RouteScoreRequest(BaseModel):
    origin: LatLng
    destination: LatLng
    alpha: float = 0.5
    carrier: str = "composite"
    persona: str = "it_shuttle"
    timestamp: Optional[str] = None
    weather_scenario: Optional[str] = None

class RerankRequest(BaseModel):
    route_cache_key: str
    alpha: float = 0.5

class TelemetryReport(BaseModel):
    osm_way_id: str
    signal_score: float
    ttl_seconds: int = 3600

# ──────────────────────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────────────────────

def precompute_h3_tiles(geojson: dict) -> dict:
    """Precompute H3 resolution 8 tiles per carrier from scored GeoJSON."""
    try:
        import h3
    except ImportError:
        # Fallback: generate tiles from segment midpoints
        return _fallback_h3_tiles(geojson)

    tiles = {}  # carrier -> {h3_id -> {scores: [], lats: [], lons: []}}

    for feature in geojson.get("features", []):
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        if not coords:
            continue

        # Use midpoint of segment
        mid_idx = len(coords) // 2
        lon, lat = coords[mid_idx][0], coords[mid_idx][1]

        h3_id = h3.latlng_to_cell(lat, lon, 8)

        for carrier in ["jio", "airtel", "vi", "bsnl", "composite"]:
            if carrier == "composite":
                score = props.get("composite_score", 50)
            else:
                score = props.get(f"{carrier}_score", 50)

            if carrier not in tiles:
                tiles[carrier] = {}
            if h3_id not in tiles[carrier]:
                tiles[carrier][h3_id] = {
                    "scores": [], "confidences": [],
                    "lat": lat, "lon": lon,
                }
            tiles[carrier][h3_id]["scores"].append(score)
            tiles[carrier][h3_id]["confidences"].append(
                props.get("confidence", 0.5)
            )

    # Average scores per tile
    result = {}
    for carrier, carrier_tiles in tiles.items():
        result[carrier] = {}
        for h3_id, data in carrier_tiles.items():
            result[carrier][h3_id] = {
                "h3_id": h3_id,
                "center": [data["lat"], data["lon"]],
                "score": round(sum(data["scores"]) / len(data["scores"]), 1),
                "confidence": round(
                    sum(data["confidences"]) / len(data["confidences"]), 3
                ),
            }

    return result


def _fallback_h3_tiles(geojson: dict) -> dict:
    """Fallback H3-like tile generation when h3 library unavailable."""
    tiles = {}
    grid_res = 0.004  # ~460m at Bangalore latitude (matches H3 res 8)

    for feature in geojson.get("features", []):
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        if not coords:
            continue

        mid_idx = len(coords) // 2
        lon, lat = coords[mid_idx][0], coords[mid_idx][1]

        # Quantize to grid
        grid_lat = round(lat / grid_res) * grid_res
        grid_lon = round(lon / grid_res) * grid_res
        tile_id = f"{grid_lat:.4f}_{grid_lon:.4f}"

        for carrier in ["jio", "airtel", "vi", "bsnl", "composite"]:
            score = props.get(
                f"{carrier}_score" if carrier != "composite"
                else "composite_score", 50
            )

            if carrier not in tiles:
                tiles[carrier] = {}
            if tile_id not in tiles[carrier]:
                tiles[carrier][tile_id] = {
                    "scores": [], "confidences": [],
                    "lat": grid_lat, "lon": grid_lon,
                }
            tiles[carrier][tile_id]["scores"].append(score)
            tiles[carrier][tile_id]["confidences"].append(
                props.get("confidence", 0.5)
            )

    result = {}
    for carrier, carrier_tiles in tiles.items():
        result[carrier] = {}
        for tile_id, data in carrier_tiles.items():
            result[carrier][tile_id] = {
                "h3_id": tile_id,
                "center": [data["lat"], data["lon"]],
                "score": round(sum(data["scores"]) / len(data["scores"]), 1),
                "confidence": round(
                    sum(data["confidences"]) / len(data["confidences"]), 3
                ),
            }

    return result


@app.on_event("startup")
async def startup():
    global SEGMENT_DICT, H3_TILES, GRAPH

    print(f"[STARTUP] Loading data from {GEOJSON_PATH or 'not found'}...")

    # Load scored GeoJSON into memory dict for O(1) lookup
    if GEOJSON_PATH and GEOJSON_PATH.exists():
        with GEOJSON_PATH.open() as f:
            geojson = json.load(f)
        for feature in geojson.get("features", []):
            way_id = str(feature["properties"]["osm_way_id"])
            props = dict(feature["properties"])
            props["osm_way_id"] = way_id
            # Also store midpoint from geometry
            coords = feature["geometry"]["coordinates"]
            if coords:
                mid = coords[len(coords) // 2]
                props["midpoint_lon"] = mid[0]
                props["midpoint_lat"] = mid[1]
            SEGMENT_DICT[way_id] = props

        # Precompute H3 tiles
        H3_TILES = precompute_h3_tiles(geojson)

        # Build spatial grid index for deterministic segment matching
        from router import build_spatial_index
        build_spatial_index(SEGMENT_DICT)

        print(f"[STARTUP] Loaded {len(SEGMENT_DICT)} segments, "
              f"{sum(len(v) for v in H3_TILES.values())} H3 tiles")
    else:
        print("[STARTUP] WARNING: scored segments GeoJSON not found.")
        print("[STARTUP] Set SCORED_SEGMENTS_PATH or place scored_segments.geojson in geojson/ or workspace root.")

    # Load graph (optional, for OSRM fallback routing)
    if GRAPH_PATH and GRAPH_PATH.exists():
        try:
            import osmnx as ox
            GRAPH = ox.load_graphml(GRAPH_PATH)
            print(f"[STARTUP] Graph loaded: {len(GRAPH.nodes)} nodes")
        except Exception as e:
            print(f"[STARTUP] Could not load graph: {e}")
    else:
        print(f"[STARTUP] Graph not found — OSRM routing only")


@app.on_event("shutdown")
async def shutdown():
    pass

# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/api/route/score")
async def route_score(req: RouteScoreRequest):
    """Score routes between origin and destination."""
    from config import BAND_NAMES, LOCAL_TIMEZONE
    from scorer import get_weather_multipliers, get_active_conditions, resolve_request_time
    from router import (
        get_osrm_routes, map_route_to_segments, score_route,
        compute_blended_rank, apply_persona_constraints,
        check_destination_dead_zone,
    )
    from cache import route_cache_key, cache_routes

    t_start = time.time()

    request_time = resolve_request_time(req.timestamp)
    monitored_conditions = get_active_conditions(request_time)

    # Get weather (called once per request — SPEC_SDD §4.7)
    weather_multipliers, storm_active, precip, weather_meta = await get_weather_multipliers(
        scenario_name=req.weather_scenario,
    )

    # Get OSRM routes (request more alternatives for safe_commute and suv to increase route diversity, max 4 to avoid TooBig)
    n_alternatives = 4 if req.persona in ("safe_commute", "suv") else 3
    osrm_routes = await get_osrm_routes(
        req.origin.lat, req.origin.lng,
        req.destination.lat, req.destination.lng,
        n=n_alternatives,
    )

    # Score each route
    scored_routes = []
    for i, osrm_route in enumerate(osrm_routes):
        # Map route geometry to segment IDs
        segment_ids = map_route_to_segments(
            osrm_route, SEGMENT_DICT, req.carrier,
        )

        # Score route
        route_scores = score_route(
            segment_ids, SEGMENT_DICT, req.carrier,
            weather_multipliers, monitored_conditions,
        )

        # Check destination dead zone
        is_dz, burst_point = check_destination_dead_zone(
            osrm_route, route_scores,
            req.destination.lat, req.destination.lng,
            GRAPH
        )

        base_eta_seconds = round(osrm_route.get("duration", 1800))
        traffic_delay_seconds = round(
            base_eta_seconds * route_scores.get("traffic_delay_ratio", 0.0), 1
        )
        traffic_adjusted_eta_seconds = round(base_eta_seconds + traffic_delay_seconds)
        signal_profile = [
            {
                **point,
                "dominant_band": BAND_NAMES.get(point.get("dominant_band", 2), "LTE_900"),
            }
            for point in route_scores["signal_profile"]
        ]

        route_response = {
            "route_id": f"osrm-{i + 1}",
            "osrm_route_rank": i,
            "geometry": osrm_route.get("geometry", {"type": "LineString", "coordinates": []}),
            "eta_seconds": traffic_adjusted_eta_seconds,
            "base_eta_seconds": base_eta_seconds,
            "osrm_duration_seconds": base_eta_seconds,
            "traffic_delay_seconds": traffic_delay_seconds,
            "traffic_adjusted_eta_seconds": traffic_adjusted_eta_seconds,
            "eta_source": "local_osrm_free_flow_plus_neuralpath_conditions",
            "eta_note": (
                "OSRM free-flow drive time plus NeuralPath local condition delay; "
                "this is not Google live traffic."
            ),
            "distance_meters": round(osrm_route.get("distance", 14000)),
            "connectivity_score": route_scores["connectivity_score"],
            "worst_window_score": route_scores["worst_window_score"],
            "dead_zones": route_scores["dead_zones"],
            "dead_zone_count": route_scores["dead_zone_count"],
            "connectivity_budget": route_scores["connectivity_budget"],
            "dominant_band": BAND_NAMES.get(route_scores["dominant_band"], "LTE_900"),
            "handoff_count": route_scores.get("handoff_count", 0),
            "weather_adjusted": weather_meta.get("condition") not in {"clear", "cloudy"},
            "active_conditions": route_scores["active_conditions"],
            "event_warnings": route_scores["event_warnings"],
            "signal_profile": signal_profile,
            "destination_dead_zone": is_dz,
            "prefetch_burst_point": burst_point,
            "safety_score": route_scores.get("safety_score", 50.0),
            "safety_hard_block_count": route_scores.get("safety_hard_block_count", 0),
            "safety_explanation": route_scores.get("safety_explanation", ""),
            "suv_score": route_scores.get("suv_score", 50.0),
            "suv_hard_block_count": route_scores.get("suv_hard_block_count", 0),
            "blended_rank_score": compute_blended_rank(
                traffic_adjusted_eta_seconds,
                route_scores["connectivity_score"],
                req.alpha,
                handoff_count=route_scores.get("handoff_count", 0),
                use_safety_score=(req.persona == "safe_commute"),
                safety_score=route_scores.get("safety_score", 50.0),
                use_vehicle_score=(req.persona == "suv"),
                vehicle_score=route_scores.get("suv_score", 50.0),
            ),
            "scored_segments": route_scores.get("scored_segments", []),
        }
        scored_routes.append(route_response)

    if scored_routes:
        fastest_route = min(scored_routes, key=lambda r: (r["base_eta_seconds"], r["distance_meters"]))
        best_signal_route = max(
            scored_routes,
            key=lambda r: (
                r["connectivity_score"],
                -r["dead_zone_count"],
                r["worst_window_score"],
                -r["base_eta_seconds"],
            ),
        )

        for route in scored_routes:
            is_fastest = route is fastest_route
            is_best_signal = route is best_signal_route
            route["is_fastest_route"] = is_fastest
            route["is_best_signal_route"] = is_best_signal

            if is_fastest and is_best_signal:
                route["route_role"] = "fastest_and_best_signal"
                route["route_label"] = "Fastest + Best Signal"
            elif is_fastest:
                route["route_role"] = "fastest"
                route["route_label"] = "Fastest"
            elif is_best_signal:
                route["route_role"] = "best_signal"
                route["route_label"] = "Best Signal"
            else:
                route["route_role"] = "alternative"
                route["route_label"] = "Alternative"

    # Apply persona constraints
    scored_routes = apply_persona_constraints(scored_routes, req.persona)

    # Sort by blended rank
    scored_routes.sort(key=lambda r: r["blended_rank_score"])

    # Cache for reranking
    cache_key = route_cache_key(
        req.origin.lat, req.origin.lng,
        req.destination.lat, req.destination.lng,
    )
    cache_routes(cache_key, scored_routes)

    elapsed = time.time() - t_start

    return {
        "routes": [
            {k: v for k, v in r.items() if k != "scored_segments"}
            for r in scored_routes
        ],
        "route_cache_key": cache_key,
        "weather_conditions": {
            "source": weather_meta.get("source", "live"),
            "scenario": weather_meta.get("scenario", "live"),
            "condition": weather_meta.get("condition", "clear"),
            "precipitation_mm_hr": precip,
            "storm_active": storm_active,
            "multipliers_applied": weather_multipliers,
        },
        "condition_snapshot": {
            "evaluated_at": request_time.isoformat(),
            "timezone": LOCAL_TIMEZONE,
            "monitored_conditions": monitored_conditions,
        },
        "timing_ms": round(elapsed * 1000, 1),
    }


@app.post("/api/route/rerank")
async def route_rerank(req: RerankRequest):
    """Re-rank cached routes with a new alpha. Must be <100ms."""
    from cache import get_cached_routes
    from router import rerank_routes

    t_start = time.time()

    cached = get_cached_routes(req.route_cache_key)
    if cached is None:
        raise HTTPException(404, "Route cache key not found. Call /api/route/score first.")

    reranked = rerank_routes(cached, req.alpha)

    elapsed = time.time() - t_start

    return {
        "routes": reranked,
        "alpha": req.alpha,
        "timing_ms": round(elapsed * 1000, 1),
    }


@app.get("/api/heat/tiles")
async def heat_tiles(
    west: float = Query(...),
    south: float = Query(...),
    east: float = Query(...),
    north: float = Query(...),
    carrier: str = Query("composite"),
):
    """Return H3 heatmap tiles for the given bounding box and carrier."""
    t_start = time.time()

    carrier_tiles = H3_TILES.get(carrier, {})

    # Filter tiles within bounding box
    result = []
    for tile_id, tile_data in carrier_tiles.items():
        lat, lon = tile_data["center"]
        if south <= lat <= north and west <= lon <= east:
            result.append(tile_data)

    elapsed = time.time() - t_start

    return {
        "tiles": result,
        "carrier": carrier,
        "count": len(result),
        "timing_ms": round(elapsed * 1000, 1),
    }


@app.get("/api/segment/{osm_way_id}/explain")
async def segment_explain(osm_way_id: str):
    """Natural language explanation for a segment's score."""
    from explainer import explain_segment
    from scorer import get_active_conditions, get_matching_conditions, resolve_request_time

    props = SEGMENT_DICT.get(osm_way_id)
    if props is None:
        raise HTTPException(404, f"Segment {osm_way_id} not found")

    lat = float(props.get("midpoint_lat", 12.97))
    lon = float(props.get("midpoint_lon", 77.59))

    active_conditions = get_matching_conditions(
        lat,
        lon,
        get_active_conditions(resolve_request_time()),
    )
    congestion_active = any(
        condition.get("type") in {"rush_hour", "venue_event"}
        for condition in active_conditions
    )

    explanation = explain_segment(
        props,
        congestion_active=congestion_active,
        weather_active=False,  # Would check cached weather
    )

    return explanation


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "segments_loaded": len(SEGMENT_DICT),
        "h3_tiles": sum(len(v) for v in H3_TILES.values()),
        "graph_loaded": GRAPH is not None,
    }

@app.post("/api/telemetry/report")
async def telemetry_report(report: TelemetryReport):
    """Live V2V feedback loop to temporarily override a segment's score."""
    from cache import cache_telemetry_override
    success = cache_telemetry_override(report.osm_way_id, report.signal_score, report.ttl_seconds)
    return {
        "status": "success" if success else "in-memory-only",
        "way_id": report.osm_way_id,
        "new_score": report.signal_score
    }
