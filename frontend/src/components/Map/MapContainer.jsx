import { useStore } from '../../store';
import React, { useEffect, useRef, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import maplibregl from 'maplibre-gl';
import { cellToLatLng } from 'h3-js';
import { useDebounce } from 'use-debounce';
import { api } from '../../api/client';
import MapStylePicker from '../MapStylePicker';
import {
    estimateExpectedBandwidth,
    getSignalProfilePointForProgress,
    getPreferredRouteIndex,
    getRouteConnectivity,
    getRouteDuration,
    getRouteSafetyScore,
    getRouteSuvScore,
} from '../../utils/routeBlend';

const NAVIGATION_PROGRESS_STEP = 0.08;

const ARROW_SVG = `<svg viewBox="0 0 24 24" width="32" height="32" style="filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));">
  <path d="M12 2L2 22l10-4 10 4L12 2z" fill="#10b981" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round"/>
</svg>`;

function getMapLibreStyle(mapStyle, isDarkMode) {
    if (mapStyle === 'terrain') {
        return {
            version: 8,
            sources: {
                opentopo: {
                    type: 'raster',
                    tiles: ['https://a.tile.opentopomap.org/{z}/{x}/{y}.png'],
                    tileSize: 256,
                    maxzoom: 17,
                    attribution: 'Map data: OpenStreetMap contributors, SRTM | OpenTopoMap',
                },
            },
            layers: [
                { id: 'terrain-layer', type: 'raster', source: 'opentopo', minzoom: 0 },
            ],
        };
    }

    if (mapStyle === 'hybrid') {
        return {
            version: 8,
            sources: {
                satellite: {
                    type: 'raster',
                    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
                    maxzoom: 19,
                    attribution: 'Tiles © Esri',
                },
                roads: {
                    type: 'raster',
                    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}'],
                    maxzoom: 19,
                },
            },
            layers: [
                { id: 'satellite-layer', type: 'raster', source: 'satellite', minzoom: 0 },
                { id: 'roads-layer', type: 'raster', source: 'roads', minzoom: 0, paint: { 'raster-opacity': 0.65 } },
            ],
        };
    }

    return isDarkMode
        ? 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
        : 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
}

function getNavigationCamera(mode, bearing = 30) {
    if (mode === 'top-down') return { zoom: 15, pitch: 0, bearing: 0 };
    if (mode === 'drone') return { zoom: 15.5, pitch: 45, bearing };
    return { zoom: 16.5, pitch: 65, bearing };
}

function routesShareGeometry(a, b) {
    const coordsA = a?.geometry?.coordinates;
    const coordsB = b?.geometry?.coordinates;

    if (!coordsA?.length || !coordsB?.length || coordsA.length !== coordsB.length) {
        return false;
    }

    return coordsA.every((coord, index) => (
        coord[0] === coordsB[index]?.[0] && coord[1] === coordsB[index]?.[1]
    ));
}

function findDistinctRoute(indexedRoutes, primary, preferredRoutes = []) {
    const preferred = preferredRoutes.find(({ route }) => route && route !== primary && !routesShareGeometry(route, primary));
    if (preferred) return preferred;

    return indexedRoutes.find(({ route }) => route && route !== primary && !routesShareGeometry(route, primary));
}

function pickDisplayRoutes(routes) {
    if (!Array.isArray(routes) || routes.length === 0) {
        return [];
    }

    if (routes.length === 1) {
        return [routes[0], routes[0]];
    }

    const persona = useStore.getState().personaPreset;
    const indexedRoutes = routes.map((route, index) => ({ route, index }));

    // When safe_commute is active, pick safest vs fastest
    if (persona === 'safe_commute') {
        const safetySorted = [...indexedRoutes].sort((a, b) => {
            const safetyDelta = getRouteSafetyScore(b.route) - getRouteSafetyScore(a.route);
            if (safetyDelta !== 0) return safetyDelta;
            return getRouteDuration(a.route) - getRouteDuration(b.route);
        });
        const speedSorted = [...indexedRoutes].sort((a, b) => {
            return getRouteDuration(a.route) - getRouteDuration(b.route);
        });
        const taggedSafestRoute = indexedRoutes.find(({ route }) => route.is_safest_route || route.route_role === 'safest');
        const safestRoute = taggedSafestRoute || safetySorted[0];
        const comparisonRoute = findDistinctRoute(indexedRoutes, safestRoute.route, speedSorted);

        return [safestRoute.route, comparisonRoute?.route || safestRoute.route];
    }

    if (persona === 'suv') {
        const suvSorted = [...indexedRoutes].sort((a, b) => {
            const suvDelta = getRouteSuvScore(b.route) - getRouteSuvScore(a.route);
            if (suvDelta !== 0) return suvDelta;

            return getRouteDuration(a.route) - getRouteDuration(b.route);
        });
        const speedSorted = [...indexedRoutes].sort((a, b) => {
            const durationDelta = getRouteDuration(a.route) - getRouteDuration(b.route);
            if (durationDelta !== 0) return durationDelta;

            return getRouteSuvScore(b.route) - getRouteSuvScore(a.route);
        });
        const taggedSuvRoute = indexedRoutes.find(({ route }) => route.is_suv_route || route.route_role === 'suv_optimal');
        const suvRoute = taggedSuvRoute || suvSorted[0];
        const comparisonRoute = findDistinctRoute(indexedRoutes, suvRoute.route, speedSorted);

        return [suvRoute.route, comparisonRoute?.route || suvRoute.route];
    }

    const connectivitySorted = [...indexedRoutes].sort((a, b) => {
        const connectivityDelta = getRouteConnectivity(b.route) - getRouteConnectivity(a.route);
        if (connectivityDelta !== 0) return connectivityDelta;

        const deadZoneDelta = (a.route.dead_zone_count || 0) - (b.route.dead_zone_count || 0);
        if (deadZoneDelta !== 0) return deadZoneDelta;

        return getRouteDuration(a.route) - getRouteDuration(b.route);
    });

    const speedSorted = [...indexedRoutes].sort((a, b) => {
        const durationDelta = getRouteDuration(a.route) - getRouteDuration(b.route);
        if (durationDelta !== 0) return durationDelta;

        return getRouteConnectivity(b.route) - getRouteConnectivity(a.route);
    });

    const taggedSignalRoute = indexedRoutes.find(({ route }) => route.is_best_signal_route);
    const taggedFastestRoute = indexedRoutes.find(({ route }) => route.is_fastest_route);
    const connectivityRoute = taggedSignalRoute || connectivitySorted[0];
    const speedRoute = findDistinctRoute(indexedRoutes, connectivityRoute.route, taggedFastestRoute ? [taggedFastestRoute, ...speedSorted] : speedSorted);

    return [connectivityRoute.route, speedRoute?.route || connectivityRoute.route];
}

function normalizeDisplayRoutePair(signalRoute, speedRoute) {
    if (!signalRoute) return [];

    return [signalRoute, speedRoute || signalRoute];
}

function getDeadZoneFeature(zone, index) {
    const coordinates = zone?.geometry?.coordinates;

    if (!coordinates?.length) return null;

    return {
        type: 'Feature',
        properties: {
            osm_way_id: zone.osm_way_id || '',
            duration_seconds: zone.duration_seconds || 0,
            length_meters: zone.length_meters || 0,
            prefetch_mb_required: zone.prefetch_mb_required || 0,
            index,
        },
        geometry: { type: 'LineString', coordinates },
    };
}

function getDeadZoneFeatures(route) {
    return route?.dead_zones?.map(getDeadZoneFeature).filter(Boolean) || [];
}

function getEmptyFeatureCollection() {
    return { type: 'FeatureCollection', features: [] };
}

function getLiveSignalColor(score = 0) {
    if (score >= 85) return '#3b82f6';
    if (score >= 65) return '#22c55e';
    if (score >= 40) return '#facc15';
    if (score >= 25) return '#f97316';
    return '#ef4444';
}

function buildSolidLineGradient(color) {
    return ['interpolate', ['linear'], ['line-progress'], 0, color, 1, color];
}

function buildLineGradient(signalProfile, fallbackColor = '#22c55e') {
    if (!Array.isArray(signalProfile) || signalProfile.length === 0) {
        return buildSolidLineGradient(fallbackColor);
    }

    const stops = [];

    signalProfile.forEach((point) => {
        const start = Math.max(0, Math.min(Number(point.progress_start ?? 0), 1));
        const end = Math.max(start, Math.min(Number(point.progress_end ?? start), 1));
        const color = getLiveSignalColor(Number(point.score ?? 50));

        stops.push([start, color], [end, color]);
    });

    const normalizedStops = stops
        .sort((a, b) => a[0] - b[0])
        .reduce((acc, [progress, color]) => {
            const last = acc[acc.length - 1];
            const safeProgress = last
                ? Math.max(progress, last[0] + 0.0001)
                : Math.max(0, progress);

            if (safeProgress <= 1) {
                acc.push([safeProgress, color]);
            }

            return acc;
        }, []);

    if (normalizedStops.length === 0 || normalizedStops[0][0] > 0) {
        normalizedStops.unshift([0, normalizedStops[0]?.[1] || fallbackColor]);
    }

    if (normalizedStops[normalizedStops.length - 1][0] < 1) {
        normalizedStops.push([1, normalizedStops[normalizedStops.length - 1][1]]);
    }

    return [
        'interpolate',
        ['linear'],
        ['line-progress'],
        ...normalizedStops.flatMap(([progress, color]) => [progress, color]),
    ];
}

function distanceMeters(a, b) {
    const lonDelta = (a[0] - b[0]) * Math.cos(((a[1] + b[1]) / 2) * Math.PI / 180);
    const latDelta = a[1] - b[1];
    return Math.sqrt((lonDelta * lonDelta) + (latDelta * latDelta)) * 111320;
}

function getNearestSignalPoint(signalProfile, coord) {
    if (!Array.isArray(signalProfile) || signalProfile.length === 0) {
        return null;
    }

    let bestPoint = null;
    let bestDistance = Infinity;

    signalProfile.forEach((point) => {
        if (point.lat === undefined || point.lng === undefined) return;

        const candidate = [Number(point.lng), Number(point.lat)];
        const distance = distanceMeters(coord, candidate);

        if (distance < bestDistance) {
            bestDistance = distance;
            bestPoint = point;
        }
    });

    return bestDistance <= 350 ? bestPoint : null;
}

function buildSignalRouteFeatures(route) {
    const coords = route?.geometry?.coordinates || [];

    if (coords.length < 2) {
        return getEmptyFeatureCollection();
    }

    const features = [];

    for (let i = 0; i < coords.length - 1; i += 1) {
        const progress = (i + 0.5) / Math.max(coords.length - 1, 1);
        const midpoint = [
            (coords[i][0] + coords[i + 1][0]) / 2,
            (coords[i][1] + coords[i + 1][1]) / 2,
        ];
        const profilePoint = getNearestSignalPoint(route?.signal_profile, midpoint)
            || getSignalProfilePointForProgress(route?.signal_profile, progress);

        // If no data exists for this specific location, do not fall back to route average
        const score = profilePoint ? Number(profilePoint.score) : null;
        const bandwidth = profilePoint
            ? Number(profilePoint.expected_bandwidth_mbps ?? estimateExpectedBandwidth(score, profilePoint.dominant_band))
            : 0;

        features.push({
            type: 'Feature',
            properties: {
                score: score ?? -1,
                color: score !== null ? getLiveSignalColor(score) : '#64748b', // slate-500 for no-data
                bandwidth_mbps: bandwidth,
                dominant_band: profilePoint?.dominant_band || route?.dominant_band || 'LTE_900',
            },
            geometry: {
                type: 'LineString',
                coordinates: [coords[i], coords[i + 1]],
            },
        });
    }

    return {
        type: 'FeatureCollection',
        features,
    };
}

function buildLiveSignalSnapshot(route, progress = 0) {
    const profilePoint = getSignalProfilePointForProgress(route?.signal_profile, progress);

    if (profilePoint) {
        const score = Math.round(profilePoint.score ?? route?.connectivity_score ?? 0);
        const dominantBand = profilePoint.dominant_band || route?.dominant_band || 'LTE_900';
        return {
            score,
            dominantBand,
            expectedBandwidthMbps: profilePoint.expected_bandwidth_mbps
                ?? estimateExpectedBandwidth(score, dominantBand),
            trafficEtaPenalty: profilePoint.traffic_eta_penalty || 0,
            color: getLiveSignalColor(score),
        };
    }

    const fallbackScore = Math.round(route?.connectivity_score ?? 50);
    const fallbackBand = route?.dominant_band || 'LTE_900';

    return {
        score: fallbackScore,
        dominantBand: fallbackBand,
        expectedBandwidthMbps: estimateExpectedBandwidth(fallbackScore, fallbackBand),
        trafficEtaPenalty: 0,
        color: getLiveSignalColor(fallbackScore),
    };
}

export default function MapContainer() {
    const {
        alpha,
        isNavigating,
        originCoords,
        destinationCoords,
        dynamicRouteData,
        setDynamicRouteData,
        carrier,
        persona,
        simulationHoursAhead,
        weatherScenario,
        setRouteCacheKey,
        setCurrentNavSignal,
        setWeatherConditions,
        setOriginCoords,
        setDestinationCoords,
        setOriginText,
        setDestinationText,
        mapSelectionMode,
        setMapSelectionMode,
        isDarkMode,
        toggleDarkMode,
        mapStyle,
        cameraMode,
    } = useStore();
    const mapContainer = useRef(null);
    const map = useRef(null);
    const routeGeometry = useRef(null);
    const originMarkerRef = useRef(null);
    const destMarkerRef = useRef(null);
    const animationFrame = useRef(null);
    const [is3D, setIs3D] = useState(true);
    const [isCameraDetached, setIsCameraDetached] = useState(false);

    const carMarkerRef = useRef(null);
    const isNavigatingRef = useRef(isNavigating);
    const cameraDetachedRef = useRef(false);
    const isAnimatingRecenterRef = useRef(false);
    const carBearingRef = useRef(0);
    const [mapLoaded, setMapLoaded] = React.useState(false);
    const [debouncedSimulationHoursAhead] = useDebounce(simulationHoursAhead, 250);

    const clearMapRoutes = () => {
        routeGeometry.current = null;
        setDynamicRouteData([]);
        setCurrentNavSignal(null);
        setWeatherConditions(null);

        if (!map.current?.getSource('route-a')) return;

        const emptyLine = { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } };
        const emptyFC = { type: 'FeatureCollection', features: [] };

        map.current.getSource('route-a').setData(emptyLine);
        map.current.getSource('route-b').setData(emptyLine);
        map.current.getSource('route-signal').setData(emptyFC);
        map.current.getSource('dead-zones').setData(emptyFC);
    };

    // Sync markers if coords change from elsewhere
    useEffect(() => {
        if (originMarkerRef.current) {
            if (originCoords && !isNavigating) {
                originMarkerRef.current.setLngLat(originCoords).addTo(map.current);
            } else {
                originMarkerRef.current.remove();
            }
        }
    }, [originCoords, isNavigating]);

    useEffect(() => {
        if (destMarkerRef.current) {
            if (destinationCoords && !isNavigating) {
                destMarkerRef.current.setLngLat(destinationCoords).addTo(map.current);
            } else {
                destMarkerRef.current.remove();
            }
        }
    }, [destinationCoords, isNavigating]);

    // Helper function to update map sources with backend route data
    const updateMapWithRoutes = (routes) => {
        const displayRoutes = pickDisplayRoutes(routes);
        if (displayRoutes.length === 0) return;

        const [connectivityRoute, speedRoute] = displayRoutes;
        const displayMetricRoutes = normalizeDisplayRoutePair(connectivityRoute, speedRoute);
        const coordsA = connectivityRoute.geometry.coordinates;

        const selectedInitialRoute = alpha >= 0.5 ? speedRoute : connectivityRoute;
        const deadZoneFeatures = getDeadZoneFeatures(selectedInitialRoute);

        // Update the global ref for rendering
        routeGeometry.current = {
            routes: [
                {
                    geometry: connectivityRoute.geometry,
                    dead_zones: connectivityRoute.dead_zones || [],
                    signal_profile: connectivityRoute.signal_profile || [],
                    connectivity_score: connectivityRoute.connectivity_score,
                    dominant_band: connectivityRoute.dominant_band,
                },
                {
                    geometry: speedRoute.geometry,
                    dead_zones: speedRoute.dead_zones || [],
                    signal_profile: speedRoute.signal_profile || [],
                    connectivity_score: speedRoute.connectivity_score,
                    dominant_band: speedRoute.dominant_band,
                }
            ]
        };

        // Keep summaries and rendered paths tied to the same selected routes.
        setDynamicRouteData(displayMetricRoutes);

        // Update Maplibre Sources Dynamically!
        if (map.current.getSource('route-a')) {
            map.current.getSource('route-a').setData(routeGeometry.current.routes[0].geometry);
            map.current.getSource('route-b').setData(routeGeometry.current.routes[1].geometry);
            map.current.getSource('route-signal').setData(buildSignalRouteFeatures(selectedInitialRoute));
            map.current.getSource('dead-zones').setData({ type: 'FeatureCollection', features: deadZoneFeatures });
        }
    };


    useEffect(() => {
        if (map.current) return;

        map.current = new maplibregl.Map({
            container: mapContainer.current,
            style: getMapLibreStyle(mapStyle, isDarkMode),
            center: [77.5946, 12.9716],
            zoom: 12,
            maxPitch: 85,
            antialias: true,
            maxTileCacheSize: 2000,
            fadeDuration: 300,
            attributionControl: false,
        });
        map.current.addControl(new maplibregl.AttributionControl(), 'bottom-left');

        map.current.on('load', async () => {
            try {
                const originEl = document.createElement('div');
                originEl.className = 'w-4 h-4 bg-sky-400 border-2 border-white rounded-full shadow-[0_0_15px_rgba(56,189,248,0.8)] cursor-grab active:cursor-grabbing';
                originMarkerRef.current = new maplibregl.Marker({ element: originEl, draggable: true });
                if (originCoords) originMarkerRef.current.setLngLat(originCoords).addTo(map.current);
                originMarkerRef.current.on('dragend', () => {
                    const lngLat = originMarkerRef.current.getLngLat();
                    setOriginText('Pinned origin');
                    setOriginCoords([lngLat.lng, lngLat.lat]);
                });

                const destEl = document.createElement('div');
                destEl.className = 'w-4 h-4 bg-emerald-400 border-2 border-white rounded-full shadow-[0_0_15px_rgba(52,211,153,0.8)] cursor-grab active:cursor-grabbing';
                destMarkerRef.current = new maplibregl.Marker({ element: destEl, draggable: true });
                if (destinationCoords) destMarkerRef.current.setLngLat(destinationCoords).addTo(map.current);
                destMarkerRef.current.on('dragend', () => {
                    const lngLat = destMarkerRef.current.getLngLat();
                    setDestinationText('Pinned destination');
                    setDestinationCoords([lngLat.lng, lngLat.lat]);
                });

                map.current.on('click', (event) => {
                    const mode = useStore.getState().mapSelectionMode;
                    if (!mode) return;

                    const coords = [event.lngLat.lng, event.lngLat.lat];
                    if (mode === 'origin') {
                        setOriginText('Pinned origin');
                        setOriginCoords(coords);
                        originMarkerRef.current?.setLngLat(coords).addTo(map.current);
                    } else if (mode === 'destination') {
                        setDestinationText('Pinned destination');
                        setDestinationCoords(coords);
                        destMarkerRef.current?.setLngLat(coords).addTo(map.current);
                    }
                    setMapSelectionMode(null);
                });

                // ═══════════════════════════════════════════════════
                // 1. INITIALIZE EMPTY SOURCES & LAYERS
                // ═══════════════════════════════════════════════════
                const emptyFC = { type: 'FeatureCollection', features: [] };
                const emptyLine = { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } };

                // ═══════════════════════════════════════════════════
                // 2. SIGNAL TOWER MARKERS
                // ═══════════════════════════════════════════════════
                map.current.addSource('towers', { type: 'geojson', data: emptyFC });

                // Outer glow ring — color-coded by signal quality
                map.current.addLayer({
                    id: 'tower-glow', type: 'circle', source: 'towers',
                    paint: {
                        'circle-radius': 0,
                        'circle-blur': 0.6,
                        'circle-opacity': 0,
                        'circle-color': [
                            'interpolate', ['linear'], ['get', 'score'],
                            0, '#ef4444',   // Red = dead zone
                            30, '#f97316',  // Orange = weak
                            60, '#eab308',  // Yellow = moderate
                            80, '#22c55e',  // Green = good
                            100, '#3b82f6'  // Blue = excellent
                        ]
                    }
                });

                // Inner white core dot (the "tower" icon)
                map.current.addLayer({
                    id: 'tower-core', type: 'circle', source: 'towers',
                    paint: {
                        'circle-radius': 0,
                        'circle-color': '#ffffff',
                        'circle-opacity': 0
                    }
                });

                // Tower click popup
                map.current.on('click', 'tower-core', (e) => {
                    const score = e.features[0].properties.score;
                    const quality = score >= 80 ? '5G Excellent' : score >= 60 ? '4G Good' : score >= 30 ? 'LTE Weak' : '⚠️ Dead Zone';
                    const color = score >= 80 ? '#3b82f6' : score >= 60 ? '#22c55e' : score >= 30 ? '#f97316' : '#ef4444';
                    new maplibregl.Popup({ closeButton: true, closeOnClick: true, className: 'neural-popup' })
                        .setLngLat(e.lngLat)
                        .setHTML(`<div style="padding:10px;font-family:sans-serif;color:#fff;background:#0f172a;border-radius:8px;">
                            <strong style="color:${color};font-size:11px;text-transform:uppercase;letter-spacing:1px;">${quality}</strong>
                            <p style="font-size:22px;font-weight:bold;margin:4px 0;">${score}<span style="font-size:12px;color:#94a3b8">/100</span></p>
                            <p style="font-size:10px;color:#64748b;">Signal strength at this tower location</p>
                        </div>`)
                        .addTo(map.current);
                });
                map.current.on('mouseenter', 'tower-core', () => { map.current.getCanvas().style.cursor = 'pointer'; });
                map.current.on('mouseleave', 'tower-core', () => { map.current.getCanvas().style.cursor = ''; });

                // ═══════════════════════════════════════════════════
                // 3. ROUTE LAYERS (empty — populated by useEffects)
                // ═══════════════════════════════════════════════════

                // Route A (Green — Signal Optimized)
                map.current.addSource('route-a', { type: 'geojson', data: emptyLine, lineMetrics: true });
                map.current.addLayer({
                    id: 'route-a-glow', type: 'line', source: 'route-a', layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: { 'line-color': '#22c55e', 'line-width': 12, 'line-blur': 10, 'line-opacity': 0.4, 'line-opacity-transition': { duration: 600 }, 'line-width-transition': { duration: 600 } }
                });
                map.current.addLayer({
                    id: 'route-a-line', type: 'line', source: 'route-a', layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: { 'line-color': '#4ade80', 'line-width': 4, 'line-opacity-transition': { duration: 600 }, 'line-width-transition': { duration: 600 } }
                });

                // Route B (Blue — Speed Optimized)
                map.current.addSource('route-b', { type: 'geojson', data: emptyLine, lineMetrics: true });
                map.current.addLayer({
                    id: 'route-b-glow', type: 'line', source: 'route-b', layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: { 'line-color': '#3b82f6', 'line-width': 12, 'line-blur': 10, 'line-opacity': 0.3, 'line-opacity-transition': { duration: 600 }, 'line-width-transition': { duration: 600 } }
                });
                map.current.addLayer({
                    id: 'route-b-line', type: 'line', source: 'route-b', layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: { 'line-color': '#60a5fa', 'line-width': 4, 'line-opacity-transition': { duration: 600 }, 'line-width-transition': { duration: 600 } }
                });

                // Selected route signal evidence overlay. This is segmented instead of only
                // using line-gradient so long real-world route geometries stay visibly colored.
                map.current.addSource('route-signal', { type: 'geojson', data: emptyFC });
                map.current.addLayer({
                    id: 'route-signal-glow',
                    type: 'line',
                    source: 'route-signal',
                    layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: {
                        'line-color': ['get', 'color'],
                        'line-width': 20,
                        'line-blur': 8,
                        'line-opacity': 0.58,
                        'line-opacity-transition': { duration: 500 },
                    },
                });
                map.current.addLayer({
                    id: 'route-signal-line',
                    type: 'line',
                    source: 'route-signal',
                    layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: {
                        'line-color': ['get', 'color'],
                        'line-width': 8,
                        'line-opacity': 0.98,
                        'line-opacity-transition': { duration: 500 },
                    },
                });

                // ═══════════════════════════════════════════════════
                // 4. DEAD ZONES (Red — No Connectivity)
                // ═══════════════════════════════════════════════════
                map.current.addSource('dead-zones', { type: 'geojson', data: emptyFC });
                map.current.addLayer({
                    id: 'dead-zones-glow', type: 'line', source: 'dead-zones', layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: { 'line-color': '#ef4444', 'line-width': 14, 'line-blur': 12, 'line-opacity': 0.6, 'line-opacity-transition': { duration: 600 } }
                });
                map.current.addLayer({
                    id: 'dead-zones-line', type: 'line', source: 'dead-zones', layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: { 'line-color': '#f87171', 'line-width': 7, 'line-dasharray': [1.5, 2], 'line-opacity-transition': { duration: 600 } }
                });

                // ═══════════════════════════════════════════════════
                // 5. VEHICLE MARKER (HTML)
                // ═══════════════════════════════════════════════════
                const markerEl = document.createElement('div');
                markerEl.className = 'nav-arrow-marker';
                markerEl.innerHTML = ARROW_SVG;
                markerEl.style.display = 'none';
                
                carMarkerRef.current = new maplibregl.Marker({
                    element: markerEl,
                    pitchAlignment: 'map',
                    rotationAlignment: 'map'
                })
                .setLngLat([77.5946, 12.9716])
                .addTo(map.current);


                // ═══════════════════════════════════════════════════
                // 7. CLICK HANDLERS
                // ═══════════════════════════════════════════════════
                map.current.on('click', 'dead-zones-glow', async (e) => {
                    const feature = e.features[0];
                    if (!feature) return;
                    const featureProps = feature.properties || {};
                    const osmWayId = featureProps['osm_way_id'];
                    const durationSeconds = Number(featureProps['duration_seconds'] || 0);
                    const lengthMeters = Number(featureProps['length_meters'] || 0);
                    const prefetchMb = Number(featureProps['prefetch_mb_required'] || 0);
                    const detailRows = [
                        lengthMeters > 0 ? `${Math.round(lengthMeters)} m affected` : null,
                        durationSeconds > 0 ? `${Math.round(durationSeconds)} sec expected impact` : null,
                        prefetchMb > 0 ? `${prefetchMb.toFixed(1)} MB prefetch recommended` : null,
                    ].filter(Boolean);
                    const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, className: 'neural-popup' })
                        .setLngLat(e.lngLat)
                        .setHTML(`<div style="padding:10px;font-family:sans-serif;color:#fff;background:#0f172a;border-radius:8px;">
                                    <strong style="color:#ef4444;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Dead Zone</strong>
                                    ${osmWayId ? '<p style="font-size:13px;margin-top:5px;color:#94a3b8;">Loading segment explanation...</p>' : ''}
                                  </div>`)
                        .addTo(map.current);
                    const result = osmWayId ? await api.explainSegment(osmWayId) : null;
                    const explanation = result?.explanation || result?.reason;
                    popup.setHTML(`<div style="padding:10px;font-family:sans-serif;color:#fff;background:#0f172a;border-radius:8px;max-width:250px;">
                                    <strong style="color:#ef4444;font-size:12px;text-transform:uppercase;letter-spacing:1px;">${osmWayId ? `Sector ${osmWayId}` : 'Dead Zone'}</strong>
                                    ${explanation ? `<p style="font-size:13px;margin-top:5px;line-height:1.4;">${explanation}</p>` : ''}
                                    ${detailRows.length > 0 ? `<p style="font-size:12px;margin-top:7px;line-height:1.4;color:#94a3b8;">${detailRows.join('<br/>')}</p>` : ''}
                                  </div>`);
                });

                map.current.on('mouseenter', 'dead-zones-glow', () => { map.current.getCanvas().style.cursor = 'pointer'; });
                map.current.on('mouseleave', 'dead-zones-glow', () => { map.current.getCanvas().style.cursor = ''; });

                setMapLoaded(true);
            } catch (err) { console.error("Map init error:", err); }
        });
    }, []);

    // --- CARRIER CHANGE: Refresh towers ---
    useEffect(() => {
        if (!mapLoaded || !map.current) return;
        if (!map.current.getSource('towers')) return;

        const refreshCarrierData = async () => {
            console.log(`[MAP] Refreshing data for carrier: ${carrier}`);
            let tileData = await api.heatTiles(77.4, 12.8, 77.8, 13.2, carrier);
            if (!Array.isArray(tileData)) tileData = tileData.tiles || [];

            console.log(`[MAP] Received ${tileData.length} tiles for ${carrier}`);

            // Rebuild tower points from the carrier-provided tile centers.
            const towerFeatures = tileData
                .map(tile => {
                    const h3Id = tile.h3_id || tile.h3 || tile.id;
                    const tileCenter = Array.isArray(tile.center) && tile.center.length >= 2
                        ? [tile.center[1], tile.center[0]]
                        : null;
                    try {
                        const [lat, lng] = tileCenter ? [tileCenter[1], tileCenter[0]] : cellToLatLng(h3Id);
                        return {
                            type: 'Feature',
                            properties: { score: tile.score || 50 },
                            geometry: { type: 'Point', coordinates: [lng, lat] }
                        };
                    } catch { return null; }
                })
                .filter(Boolean);

            map.current.getSource('towers').setData({ type: 'FeatureCollection', features: towerFeatures });
        };

        refreshCarrierData();
    }, [carrier, mapLoaded]);

    // --- FULL BACKEND ROUTING CONTROLLER ---
    useEffect(() => {
        if (!mapLoaded || !map.current || !originCoords || !destinationCoords) return;

        const fetchDynamicRoutes = async () => {
            try {
                const simulatedTimestamp = new Date(
                    Date.now() + debouncedSimulationHoursAhead * 60 * 60 * 1000
                ).toISOString();
                const data = await api.scoreRoutes(
                    originCoords,
                    destinationCoords,
                    alpha,
                    carrier,
                    persona,
                    simulatedTimestamp,
                    weatherScenario,
                );
                if (data && data.routes && data.routes.length > 0) {
                    setWeatherConditions(data.weather_conditions || null);
                    if (data.route_cache_key) {
                        setRouteCacheKey(data.route_cache_key);
                    }
                    updateMapWithRoutes(data.routes);
                    const bounds = new maplibregl.LngLatBounds();
                    bounds.extend(originCoords);
                    bounds.extend(destinationCoords);
                    map.current.fitBounds(bounds, { padding: 150, duration: 1500 });
                } else {
                    clearMapRoutes();
                }
            } catch (err) { console.error("Dynamic Routing Error:", err); }
        };

        if (!isNavigating) fetchDynamicRoutes();
        // Alpha changes should only update route emphasis/metrics locally; refetching geometry on every slider move makes the ETA feel laggy.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [originCoords, destinationCoords, carrier, persona, debouncedSimulationHoursAhead, weatherScenario, isNavigating, mapLoaded]); // EXCLUDE ALPHA

    // --- SMOOTH INTERPOLATION CONTROLLER ---
    useEffect(() => {
        if (!mapLoaded || !map.current) return;

        const preferSignalRoute = alpha <= 0.5;
        try {
            const preferredRouteIndex = getPreferredRouteIndex(dynamicRouteData, alpha);
            const selectedRoute = routeGeometry.current?.routes?.[preferredRouteIndex];
            const routeAGradient = preferSignalRoute
                ? buildLineGradient(routeGeometry.current?.routes?.[0]?.signal_profile, '#22c55e')
                : buildSolidLineGradient('rgba(34,197,94,0.55)');
            const routeBGradient = preferSignalRoute
                ? buildSolidLineGradient('rgba(96,165,250,0.55)')
                : buildLineGradient(routeGeometry.current?.routes?.[1]?.signal_profile, '#60a5fa');
            const routeAOpacity = preferSignalRoute ? 1 : 0.14;
            const routeAWidth = preferSignalRoute ? 4.5 : 2;
            const routeAGlow = preferSignalRoute ? 0.4 : 0.05;
            const deadZoneOpacity = 1;
            const deadZoneGlow = 0.6;
            const routeBOpacity = preferSignalRoute ? 0.14 : 1;
            const routeBWidth = preferSignalRoute ? 2 : 4.5;
            const routeBGlow = preferSignalRoute ? 0.05 : 0.3;

            map.current.setPaintProperty('route-a-line', 'line-opacity', routeAOpacity);
            map.current.setPaintProperty('route-a-line', 'line-width', routeAWidth);
            map.current.setPaintProperty('route-a-line', 'line-gradient', routeAGradient);
            map.current.setPaintProperty('route-a-glow', 'line-opacity', routeAGlow);

            map.current.setPaintProperty('dead-zones-line', 'line-opacity', deadZoneOpacity);
            map.current.setPaintProperty('dead-zones-glow', 'line-opacity', deadZoneGlow);

            map.current.setPaintProperty('route-b-line', 'line-opacity', routeBOpacity);
            map.current.setPaintProperty('route-b-line', 'line-width', routeBWidth);
            map.current.setPaintProperty('route-b-line', 'line-gradient', routeBGradient);
            map.current.setPaintProperty('route-b-glow', 'line-opacity', routeBGlow);

            if (map.current.getSource('route-signal')) {
                map.current.getSource('route-signal').setData(buildSignalRouteFeatures(selectedRoute));
                map.current.setPaintProperty('route-signal-line', 'line-opacity', selectedRoute ? 0.98 : 0);
                map.current.setPaintProperty('route-signal-glow', 'line-opacity', selectedRoute ? 0.52 : 0);
            }

            if (map.current.getSource('dead-zones')) {
                map.current.getSource('dead-zones').setData({
                    type: 'FeatureCollection',
                    features: getDeadZoneFeatures(selectedRoute),
                });
            }

            // Dynamically update car color if it exists
            if (map.current.getLayer('car-pulse')) {
                map.current.setPaintProperty('car-pulse', 'circle-color', preferredRouteIndex === 0 ? '#22c55e' : '#3b82f6');
            }
        } catch (err) {
            console.warn("Route style update skipped:", err);
        }
    }, [alpha, dynamicRouteData, mapLoaded]);

    // --- NAVIGATION CAMERA CONTROLLER & CAR ANIMATION ---
    useEffect(() => {
        if (!map.current || !routeGeometry.current) return;
        let timeoutId;

        const initialRouteIndex = getPreferredRouteIndex(
            useStore.getState().dynamicRouteData,
            useStore.getState().alpha,
        );

        const handleInteractStart = (e) => {
            if (e.originalEvent) {
                cameraDetachedRef.current = true;
                setIsCameraDetached(true);
                clearTimeout(interactionTimeout);
            }
        };
        
        // In this new model, we don't automatically snap back!
        // The user must press "Recenter", just like Google Maps.
        const handleInteractEnd = (e) => {
            // Do nothing
        };

        if (isNavigating) {
            const initialRoute = routeGeometry.current.routes[initialRouteIndex];
            const initialSignal = buildLiveSignalSnapshot(initialRoute, 0);

            // 1. Position and show the car marker immediately at the start of the route
            if (carMarkerRef.current) {
                const startCoords = initialRoute.geometry.coordinates[0];
                const nextCoords = initialRoute.geometry.coordinates[1];
                
                carMarkerRef.current.setLngLat(startCoords);
                if (startCoords && nextCoords) {
                    const bearing = Math.atan2(nextCoords[0] - startCoords[0], nextCoords[1] - startCoords[1]) * 180 / Math.PI;
                    carMarkerRef.current.setRotation(bearing);
                    carBearingRef.current = bearing;
                }

                const el = carMarkerRef.current.getElement();
                el.style.display = 'block';
                const svgPath = el.querySelector('path');
                if (svgPath) {
                    svgPath.setAttribute('fill', initialSignal.color);
                }
            }
            useStore.getState().setCurrentNavSignal(initialSignal);

            // Reset detachment state when starting a new navigation session
            cameraDetachedRef.current = false;
            setIsCameraDetached(false);
            isAnimatingRecenterRef.current = false;

            // 2. Fly the camera in
            const initialCameraMode = useStore.getState().cameraMode || 'driver';
            let initialPitch = 65;
            let initialZoom = 16.5;
            let initialBearing = 30;

            if (initialCameraMode === 'top-down') {
                initialPitch = 0;
                initialZoom = 15;
                initialBearing = 0;
            } else if (initialCameraMode === 'drone') {
                initialPitch = 45;
                initialZoom = 15.5;
            }

            map.current.flyTo({
                center: initialRoute.geometry.coordinates[0],
                zoom: initialZoom,
                pitch: initialPitch,
                bearing: initialBearing,
                essential: true,
                duration: 2000
            });

            map.current.on('dragstart', handleInteractStart);
            map.current.on('zoomstart', handleInteractStart);
            map.current.on('rotatestart', handleInteractStart);
            map.current.on('pitchstart', handleInteractStart);
            
            map.current.on('dragend', handleInteractEnd);
            map.current.on('zoomend', handleInteractEnd);
            map.current.on('rotateend', handleInteractEnd);
            map.current.on('pitchend', handleInteractEnd);

            // 3. Start driving the car down the road!
            let currentDist = 0;
            let lastStoreUpdateTime = 0;
            
            // Cache the SVG path to avoid querying the DOM every frame (which causes severe lag)
            let carSvgPath = null;
            if (carMarkerRef.current) {
                carSvgPath = carMarkerRef.current.getElement().querySelector('path');
            }

            // Simple Euclidean distance (sufficient for small city scales to normalize speed)
            const calcDist = (p1, p2) => Math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2);
            
            // Speed constant (degrees per frame roughly)
            const CAR_SPEED = 0.00004;

            const drive = () => {
                // Dynamically check the slider state every single frame!
                const currentAlpha = useStore.getState().alpha;
                const currentRouteIndex = getPreferredRouteIndex(useStore.getState().dynamicRouteData, currentAlpha);
                const activeRoute = routeGeometry.current.routes[currentRouteIndex];
                const coords = activeRoute.geometry.coordinates;

                // Build cumulative distances for the current route
                const dists = [0];
                for (let j = 1; j < coords.length; j++) {
                    dists[j] = dists[j - 1] + calcDist(coords[j - 1], coords[j]);
                }
                const totalDist = dists[dists.length - 1];

                if (currentDist >= totalDist) {
                    useStore.getState().setCurrentNavSignal(buildLiveSignalSnapshot(activeRoute, 1));
                    useStore.getState().setNavProgress(1); // Arrived
                    return;
                }

                // Find which segment we are currently in
                let idx = 0;
                while (idx < dists.length - 1 && dists[idx + 1] < currentDist) {
                    idx++;
                }

                const segmentStartDist = dists[idx];
                const segmentEndDist = dists[idx + 1];
                const segmentLen = segmentEndDist - segmentStartDist;
                
                let fraction = 0;
                if (segmentLen > 0) {
                    fraction = (currentDist - segmentStartDist) / segmentLen;
                }

                const p1 = coords[idx];
                const p2 = coords[idx + 1] || p1;

                // Linear interpolation for perfectly smooth movement across frames
                const lng = p1[0] + (p2[0] - p1[0]) * fraction;
                const lat = p1[1] + (p2[1] - p1[1]) * fraction;
                const currentCoord = [lng, lat];
                
                const bearing = Math.atan2(p2[0] - p1[0], p2[1] - p1[1]) * 180 / Math.PI;
                carBearingRef.current = bearing;

                if (carMarkerRef.current) {
                    carMarkerRef.current.setLngLat(currentCoord);
                    carMarkerRef.current.setRotation(bearing);
                }

                // Only lock the camera to the car if the user isn't actively exploring the map
                if (!cameraDetachedRef.current && !isAnimatingRecenterRef.current) {
                    const mode = useStore.getState().cameraMode || 'driver';
                    const currentBearing = map.current.getBearing();
                    const currentPitch = map.current.getPitch();
                    const currentZoom = map.current.getZoom();

                    let targetPitch = 65;
                    let targetZoom = 16.5;
                    let targetBearing = bearing;

                    if (mode === 'top-down') {
                        targetPitch = 0;
                        targetZoom = 15;
                        targetBearing = 0;
                    } else if (mode === 'drone') {
                        targetPitch = 45;
                        targetZoom = 15.5;
                        targetBearing = bearing;
                    } else { // 'driver'
                        targetPitch = 65;
                        targetZoom = 16.5;
                        targetBearing = bearing;
                    }

                    // Smoothly adjust bearing so it doesn't snap violently on curvy roads
                    let bearingDiff = targetBearing - currentBearing;
                    if (bearingDiff > 180) bearingDiff -= 360;
                    if (bearingDiff < -180) bearingDiff += 360;
                    
                    const smoothedBearing = currentBearing + (bearingDiff * 0.1);
                    const smoothedPitch = currentPitch + ((targetPitch - currentPitch) * 0.1);
                    const smoothedZoom = currentZoom + ((targetZoom - currentZoom) * 0.1);

                    map.current.jumpTo({ 
                        center: currentCoord,
                        bearing: smoothedBearing,
                        pitch: smoothedPitch,
                        zoom: smoothedZoom
                    });
                }

                // Update progress so UI updates dynamically
                const progress = Math.min(currentDist / Math.max(totalDist, 0.0001), 1);
                const liveSignal = buildLiveSignalSnapshot(activeRoute, progress);
                
                if (carSvgPath) {
                    carSvgPath.setAttribute('fill', liveSignal.color);
                }
                
                // Throttle state updates to max 5 times a second to prevent heavy React re-render lag
                const now = Date.now();
                if (now - lastStoreUpdateTime > 200) {
                    useStore.getState().setCurrentNavSignal(liveSignal);
                    useStore.getState().setNavProgress(progress);
                    lastStoreUpdateTime = now;
                }

                currentDist += CAR_SPEED;
                animationFrame.current = requestAnimationFrame(drive);
            };

            // Wait for the flyTo animation to finish before hitting the gas
            timeoutId = setTimeout(() => { drive(); }, 2000);

        } else {
            // Hide the car
            if (carMarkerRef.current) {
                carMarkerRef.current.getElement().style.display = 'none';
            }
            if (animationFrame.current) cancelAnimationFrame(animationFrame.current);
            useStore.getState().setCurrentNavSignal(null);

            // Zoom back out to the city view
            map.current.flyTo({
                center: [77.5946, 12.9716],
                zoom: 12,
                pitch: 0,
                bearing: 0,
                essential: true,
                duration: 2000
            });
        }

        // Cleanup function to absolutely guarantee the car stops when they hit Exit
        return () => {
            clearTimeout(timeoutId);
            if (animationFrame.current) cancelAnimationFrame(animationFrame.current);
            if (!useStore.getState().isNavigating) {
                useStore.getState().setCurrentNavSignal(null);
            }
            if (map.current) {
                // Remove the interaction listeners we added for navigation
                map.current.off('dragstart', handleInteractStart);
                map.current.off('zoomstart', handleInteractStart);
                map.current.off('rotatestart', handleInteractStart);
                map.current.off('pitchstart', handleInteractStart);
                map.current.off('dragend', handleInteractEnd);
                map.current.off('zoomend', handleInteractEnd);
                map.current.off('rotateend', handleInteractEnd);
                map.current.off('pitchend', handleInteractEnd);
            }
        };
    }, [isNavigating]);

    const recenterMap = () => {
        if (!map.current) return;

        if (isNavigating) {
            setIsCameraDetached(false);
            if (carMarkerRef.current) {
                isAnimatingRecenterRef.current = true;
                map.current.flyTo({
                    center: carMarkerRef.current.getLngLat(),
                    pitch: 65,
                    bearing: carBearingRef.current,
                    zoom: 16.5,
                    duration: 1000
                });
                
                // Once flyTo completes, let drive() take over again
                map.current.once('moveend', () => {
                    isAnimatingRecenterRef.current = false;
                    cameraDetachedRef.current = false;
                });
            }
        } else {
            if (!originCoords) return;
            map.current.flyTo({
                center: originCoords,
                zoom: 14,
                pitch: 0,
                bearing: 0,
                duration: 1500
            });
        }
    };

    const toggle3D = () => {
        if (!map.current) return;
        const nextIs3D = !is3D;
        setIs3D(nextIs3D);
        map.current.easeTo({
            pitch: nextIs3D ? 60 : 0,
            bearing: nextIs3D ? (map.current.getBearing() || 15) : 0,
            duration: 800,
        });
    };

    return (
        <>
            <div ref={mapContainer} className="w-screen h-screen" />



            <div className="absolute bottom-6 right-6 z-10 flex flex-col items-end gap-2">
                <button
                    type="button"
                    onClick={() => {
                        toggleDarkMode();
                        window.location.reload();
                    }}
                    title="Toggle theme"
                    aria-label="Toggle theme"
                    className="h-11 w-11 bg-slate-950/85 backdrop-blur-xl hover:bg-slate-800 text-slate-200 rounded-xl shadow-[0_14px_40px_rgba(0,0,0,0.38)] border border-white/15 transition-all flex items-center justify-center"
                >
                    {isDarkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                </button>

                <button
                    type="button"
                    onClick={toggle3D}
                    title={is3D ? 'Switch to 2D map' : 'Switch to 3D map'}
                    aria-label="Toggle 3D map"
                    className={`h-11 w-11 rounded-xl shadow-[0_14px_40px_rgba(0,0,0,0.38)] border transition-all flex items-center justify-center font-bold text-xs uppercase tracking-wider backdrop-blur-xl ${
                        is3D
                            ? 'bg-sky-500/90 text-white border-sky-400/50'
                            : 'bg-slate-950/85 hover:bg-slate-800 text-slate-200 border-white/15'
                    }`}
                >
                    {is3D ? '2D' : '3D'}
                </button>

                <MapStylePicker />

                {(!isNavigating || isCameraDetached) && (
                    <button
                        type="button"
                        onClick={recenterMap}
                        title="Recenter map"
                        aria-label="Recenter map"
                        className="h-11 w-11 bg-slate-950/85 backdrop-blur-xl hover:bg-slate-800 text-slate-200 rounded-xl shadow-[0_14px_40px_rgba(0,0,0,0.38)] border border-white/15 transition-all flex items-center justify-center"
                    >
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v3m0 12v3m9-9h-3M6 12H3m14.364-6.364-2.121 2.121M8.757 15.243l-2.121 2.121m10.728 0-2.121-2.121M8.757 8.757 6.636 6.636M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" /></svg>
                    </button>
                )}
            </div>
        </>
    );
}
