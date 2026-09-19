import math
import os
import uuid
from dataclasses import dataclass

import httpx

from digipin_wrapper import encode_digipin

OCM_BASE_URL = "https://api.openchargemap.io/v3/poi"


@dataclass
class Charger:
    id: str
    name: str
    lat: float
    lng: float
    digipin: str
    operator: str
    power_kw: float
    connector_types: list[str]
    num_points: int
    is_operational: bool
    distance_km: float
    address: str = ""


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def fetch_ocm_chargers(
    lat: float,
    lng: float,
    radius_km: float,
    max_results: int = 50,
) -> list[Charger]:
    params = {
        "output": "json",
        "latitude": lat,
        "longitude": lng,
        "distance": radius_km,
        "distanceunit": "KM",
        "maxresults": max_results,
        "camelcase": "true",
        "statustypeid": "50",
    }
    api_key = os.getenv("OCM_API_KEY")
    if api_key:
        params["key"] = api_key

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(OCM_BASE_URL, params=params, timeout=10.0)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    chargers = []
    for item in data:
        status = item.get("statusType")
        if status and not status.get("isOperational", True):
            continue

        address_info = item.get("addressInfo", {}) or {}
        c_lat = address_info.get("latitude")
        c_lng = address_info.get("longitude")
        if c_lat is None or c_lng is None:
            continue

        operator_info = item.get("operatorInfo") or {}
        operator = operator_info.get("title", "Unknown")
        connections = item.get("connections", []) or []
        powers = [conn.get("powerKW") for conn in connections if conn.get("powerKW")]
        power_kw = float(max(powers)) if powers else 22.0
        connector_types = sorted({
            conn.get("connectionType", {}).get("title", "Unknown")
            for conn in connections
            if conn.get("connectionType")
        })

        chargers.append(Charger(
            id=str(item.get("uuid") or uuid.uuid4()),
            name=address_info.get("title", "EV Charger"),
            lat=float(c_lat),
            lng=float(c_lng),
            digipin=encode_digipin(float(c_lat), float(c_lng)),
            operator=operator,
            power_kw=power_kw,
            connector_types=connector_types or ["Type 2"],
            num_points=max(1, len(connections)),
            is_operational=True,
            distance_km=haversine_km(lat, lng, float(c_lat), float(c_lng)),
            address=address_info.get("addressLine1", ""),
        ))

    chargers.sort(key=lambda charger: charger.distance_km)
    return chargers


_BANGALORE_CHARGERS_CACHE: list[Charger] = []


async def get_bangalore_chargers() -> list[Charger]:
    global _BANGALORE_CHARGERS_CACHE
    if not _BANGALORE_CHARGERS_CACHE:
        import json
        from pathlib import Path
        
        path = Path(__file__).parent.parent / "geojson" / "bangalore_chargers.json"
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                _BANGALORE_CHARGERS_CACHE = [Charger(**d) for d in data]
        else:
            _BANGALORE_CHARGERS_CACHE = await fetch_ocm_chargers(12.9716, 77.5946, 50.0, max_results=1000)
    return _BANGALORE_CHARGERS_CACHE


def point_to_line_dist(pt: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    l2 = (end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2
    if l2 == 0:
        return haversine_km(pt[0], pt[1], start[0], start[1])

    t = max(
        0,
        min(
            1,
            ((pt[0] - start[0]) * (end[0] - start[0]) + (pt[1] - start[1]) * (end[1] - start[1])) / l2,
        ),
    )
    projection = (
        start[0] + t * (end[0] - start[0]),
        start[1] + t * (end[1] - start[1]),
    )
    return haversine_km(pt[0], pt[1], projection[0], projection[1])


def distance_to_polyline(lat: float, lng: float, polyline: list[tuple[float, float]]) -> float:
    if not polyline or len(polyline) < 2:
        return float("inf")

    point = (lat, lng)
    return min(
        point_to_line_dist(point, polyline[i], polyline[i + 1])
        for i in range(len(polyline) - 1)
    )


async def fetch_enroute_chargers(
    orig_lat: float,
    orig_lng: float,
    dest_lat: float,
    dest_lng: float,
    radius_km: float = 0.5,
    max_results: int = 100,
) -> list[Charger]:
    from router import OSRM_URL

    polyline = [(orig_lat, orig_lng), (dest_lat, dest_lng)]
    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{orig_lng},{orig_lat};{dest_lng},{dest_lat}"
        f"?geometries=geojson&overview=full"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
        data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            coords = data["routes"][0]["geometry"]["coordinates"]
            polyline = [(coord[1], coord[0]) for coord in coords]
    except Exception:
        pass

    valid = []
    for charger in await get_bangalore_chargers():
        route_distance = distance_to_polyline(charger.lat, charger.lng, polyline)
        if route_distance <= radius_km:
            charger.distance_km = route_distance
            valid.append(charger)

    valid.sort(key=lambda charger: charger.distance_km)
    return valid[:max_results]


async def fetch_nearby_chargers(
    lat: float,
    lng: float,
    radius_km: float = 10.0,
    max_results: int = 50,
) -> list[Charger]:
    valid = []
    for charger in await get_bangalore_chargers():
        distance = haversine_km(lat, lng, charger.lat, charger.lng)
        if distance <= radius_km:
            charger.distance_km = distance
            valid.append(charger)

    valid.sort(key=lambda charger: charger.distance_km)
    return valid[:max_results]


async def find_best_detour_charger(
    lat: float,
    lng: float,
    min_power_kw: float = 22.0,
    radius_km: float = 20.0,
) -> Charger | None:
    candidates = []
    for charger in await get_bangalore_chargers():
        if charger.power_kw < min_power_kw:
            continue
        distance = haversine_km(lat, lng, charger.lat, charger.lng)
        if distance <= radius_km:
            charger.distance_km = distance
            candidates.append(charger)

    if not candidates:
        return None

    candidates.sort(key=lambda charger: charger.distance_km)
    return candidates[0]
