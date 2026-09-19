from dataclasses import dataclass

GRAVITY = 9.81
AIR_DENSITY = 1.225
JOULES_PER_KWH = 3_600_000
SAFETY_MARGIN_PCT = 15.0
HVAC_PENALTY_COLD_THRESHOLD = 10
HVAC_PENALTY_HOT_THRESHOLD = 35
HVAC_PENALTY_MULTIPLIER = 1.5
MIN_SPEED_MPS = 0.1


@dataclass
class EVProfile:
    mass_kg: float = 1800.0
    frontal_area_m2: float = 2.3
    drag_coeff: float = 0.28
    rolling_resistance: float = 0.01
    regen_efficiency: float = 0.65
    motor_efficiency: float = 0.90
    battery_capacity_kwh: float = 60.0
    aux_power_kw: float = 1.5


def compute_segment_energy_kwh(
    distance_m: float,
    speed_mps: float,
    elevation_gain_m: float,
    headwind_mps: float = 0.0,
    temperature_c: float = 25.0,
    profile: EVProfile | None = None,
) -> float:
    profile = profile or EVProfile()
    speed_mps = max(speed_mps, MIN_SPEED_MPS)
    time_s = distance_m / speed_mps

    e_rolling = profile.rolling_resistance * profile.mass_kg * GRAVITY * distance_m
    effective_speed = speed_mps + max(headwind_mps, 0.0)
    e_aero = (
        0.5
        * AIR_DENSITY
        * profile.drag_coeff
        * profile.frontal_area_m2
        * (effective_speed ** 2)
        * distance_m
    )
    e_grade = profile.mass_kg * GRAVITY * elevation_gain_m
    e_traction = e_rolling + e_aero + e_grade

    if e_traction >= 0:
        e_motor = e_traction / profile.motor_efficiency
    else:
        e_motor = e_traction * profile.regen_efficiency

    aux_kw = profile.aux_power_kw
    if temperature_c < HVAC_PENALTY_COLD_THRESHOLD or temperature_c > HVAC_PENALTY_HOT_THRESHOLD:
        aux_kw *= HVAC_PENALTY_MULTIPLIER

    e_aux = aux_kw * (time_s / 3600.0)
    return round((e_motor / JOULES_PER_KWH) + e_aux, 6)


def predict_route_soc(
    route_segments: list[dict],
    initial_soc_pct: float,
    profile: EVProfile | None = None,
    weather: dict | None = None,
) -> dict:
    profile = profile or EVProfile()
    soc_kwh = (initial_soc_pct / 100.0) * profile.battery_capacity_kwh
    waypoints = []
    cumulative_energy = 0.0
    cumulative_distance = 0.0
    critical_waypoint = None
    headwind = weather.get("wind_speed_mps", 0.0) if weather else 0.0
    temp = weather.get("temperature_c", 25.0) if weather else 25.0

    for index, segment in enumerate(route_segments):
        energy = compute_segment_energy_kwh(
            distance_m=segment["distance_m"],
            speed_mps=segment["speed_mps"],
            elevation_gain_m=segment["elevation_gain_m"],
            headwind_mps=headwind,
            temperature_c=temp,
            profile=profile,
        )
        soc_kwh -= energy
        cumulative_energy += energy
        cumulative_distance += segment["distance_m"]
        soc_pct = (soc_kwh / profile.battery_capacity_kwh) * 100.0

        waypoints.append({
            "lat": segment.get("lat"),
            "lng": segment.get("lng"),
            "soc_pct": round(soc_pct, 2),
            "energy_kwh": round(energy, 4),
            "cumulative_energy_kwh": round(cumulative_energy, 4),
        })

        if soc_pct < SAFETY_MARGIN_PCT and critical_waypoint is None:
            critical_waypoint = index

    efficiency = (
        cumulative_energy / (cumulative_distance / 1000.0)
        if cumulative_distance > 0
        else 0.0
    )

    return {
        "waypoints": waypoints,
        "final_soc_pct": round((soc_kwh / profile.battery_capacity_kwh) * 100.0, 2),
        "total_energy_kwh": round(cumulative_energy, 4),
        "total_distance_m": round(cumulative_distance, 2),
        "range_sufficient": critical_waypoint is None,
        "critical_waypoint": critical_waypoint,
        "efficiency_kwh_per_km": round(efficiency, 4),
    }


async def check_reroute_needed(
    route_soc: dict,
    safety_margin_pct: float = SAFETY_MARGIN_PCT,
    current_lat: float = 0.0,
    current_lng: float = 0.0,
) -> dict:
    if route_soc.get("range_sufficient") and route_soc.get("final_soc_pct", 100) >= safety_margin_pct:
        return {
            "reroute_needed": False,
            "reason": None,
            "final_soc_pct": route_soc.get("final_soc_pct"),
            "suggested_charger": None,
            "detour_distance_km": None,
        }

    from ev_charger import find_best_detour_charger

    suggested = await find_best_detour_charger(current_lat, current_lng, min_power_kw=22.0)
    return {
        "reroute_needed": True,
        "reason": "SoC drops below safety margin.",
        "final_soc_pct": route_soc.get("final_soc_pct"),
        "suggested_charger": vars(suggested) if suggested else None,
        "detour_distance_km": suggested.distance_km if suggested else None,
    }
