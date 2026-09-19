from ev_charger import haversine_km


def get_route_elevation_profile(coord_tuples: list[tuple[float, float]]) -> list[dict]:
    """Return a flat Bangalore elevation profile until real DEM sampling is wired in."""
    profile = []
    cumulative_dist = 0.0

    for index, coord in enumerate(coord_tuples):
        lat, lon = coord
        if index > 0:
            prev_lat, prev_lon = coord_tuples[index - 1]
            cumulative_dist += haversine_km(prev_lat, prev_lon, lat, lon) * 1000.0

        profile.append({
            "cumulative_dist_m": cumulative_dist,
            "elevation_m": 900.0,
        })

    return profile
