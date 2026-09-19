const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function normalizeCarrier(carrier) {
    return carrier === 'vodafone' ? 'vi' : carrier;
}

export const api = {
    // Fetch H3 heatmap tiles from backend
    async heatTiles(west = 77.4, south = 12.8, east = 77.8, north = 13.2, carrier = "composite") {
        const backendCarrier = normalizeCarrier(carrier);
        const url = `${BASE_URL}/api/heat/tiles?west=${west}&south=${south}&east=${east}&north=${north}&carrier=${backendCarrier}`;
        const res = await fetch(url);
        const data = await res.json();
        return data.tiles || [];
    },

    async evHeatmap() {
        try {
            const url = `${BASE_URL}/api/ev/heatmap?max_features=1000000`;
            const res = await fetch(url);
            if (!res.ok) return null;
            return await res.json();
        } catch (error) {
            console.error("EV heatmap unavailable:", error);
            return null;
        }
    },

    async evChargers(originCoords, destCoords, radiusKm = 3.0) {
        if (!originCoords || !destCoords) return [];
        try {
            const params = new URLSearchParams({
                orig_lat: originCoords[1],
                orig_lng: originCoords[0],
                dest_lat: destCoords[1],
                dest_lng: destCoords[0],
                radius_km: radiusKm,
                max_results: 80,
            });
            const res = await fetch(`${BASE_URL}/api/ev/chargers?${params.toString()}`);
            if (!res.ok) return [];
            const data = await res.json();
            return data.chargers || [];
        } catch (error) {
            console.error("EV chargers unavailable:", error);
            return [];
        }
    },

    async evRouteOptions(originCoords, destCoords, currentSoCPercent = 80, batteryCapacityKwh = 60) {
        if (!originCoords || !destCoords) return null;
        try {
            const res = await fetch(`${BASE_URL}/api/route/options`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vehicleType: 'ev',
                    origin: { lat: originCoords[1], lng: originCoords[0] },
                    destination: { lat: destCoords[1], lng: destCoords[0] },
                    currentSoCPercent,
                    batteryCapacityKwh,
                }),
            });
            if (!res.ok) return null;
            return await res.json();
        } catch (error) {
            console.error("EV route options unavailable:", error);
            return null;
        }
    },

    // Score routes — backend is the single source of truth for routing + scoring
    async scoreRoutes(
        originCoords,
        destCoords,
        alpha = 0.5,
        carrier = "composite",
        persona = "it_shuttle",
        timestamp = null,
        weatherScenario = 'live',
    ) {
        const backendCarrier = normalizeCarrier(carrier);
        if (!originCoords || !destCoords) {
            return { routes: [], route_cache_key: null };
        }

        console.log(`[ROUTING] Requesting routes for ${backendCarrier}...`);

        try {
            const res = await fetch(`${BASE_URL}/api/route/score`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    origin: { lat: originCoords[1], lng: originCoords[0] },
                    destination: { lat: destCoords[1], lng: destCoords[0] },
                    alpha,
                    carrier: backendCarrier,
                    persona,
                    timestamp: timestamp || new Date().toISOString(),
                    weather_scenario: weatherScenario,
                }),
            });

            if (!res.ok) {
                console.error(`[ROUTING] Backend error: ${res.status}`);
                return { routes: [], route_cache_key: null };
            }

            const data = await res.json();

            if (!data.routes || data.routes.length === 0) {
                console.warn("[ROUTING] Backend returned no routes.");
                return { routes: [], route_cache_key: data.route_cache_key || null };
            }

            console.log(`[ROUTING] Received ${data.routes.length} scored routes from backend.`);
            return data;
        } catch (error) {
            console.error("[ROUTING] Backend unreachable:", error);
            return { routes: [], route_cache_key: null };
        }
    },

    // Fast <100ms Re-rank using cached key
    async rerankRoutes(routeCacheKey, alpha) {
        try {
            const res = await fetch(`${BASE_URL}/api/route/rerank`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ route_cache_key: routeCacheKey, alpha })
            });
            return await res.json();
        } catch (error) {
            console.error("Backend offline, cannot rerank");
            return null;
        }
    },

    // Natural Language Segment Explanation
    async explainSegment(osm_way_id) {
        try {
            const res = await fetch(`${BASE_URL}/api/segment/${osm_way_id}/explain`);
            if (!res.ok) return null;
            return await res.json();
        } catch (error) {
            return null;
        }
    }
};
