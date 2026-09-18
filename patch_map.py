import re

file_path = "/home/ankith/mahe_ws/frontend/src/components/Map/MapContainer.jsx"

with open(file_path, 'r') as f:
    content = f.read()

# 1. Add ARROW_SVG
content = content.replace(
    "const NAVIGATION_PROGRESS_STEP = 0.08;\n",
    """const NAVIGATION_PROGRESS_STEP = 0.08;

const ARROW_SVG = `<svg viewBox="0 0 24 24" width="32" height="32" style="filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));">
  <path d="M12 2L2 22l10-4 10 4L12 2z" fill="#10b981" stroke="#ffffff" stroke-width="1.5" stroke-linejoin="round"/>
</svg>`;\n"""
)

# 2. Add state refs
content = content.replace(
    "    const [is3D, setIs3D] = useState(true);\n    const [mapLoaded, setMapLoaded] = React.useState(false);",
    """    const [is3D, setIs3D] = useState(true);
    const [isCameraDetached, setIsCameraDetached] = useState(false);

    const carMarkerRef = useRef(null);
    const animationFrame = useRef(null);
    const isNavigatingRef = useRef(isNavigating);
    const cameraDetachedRef = useRef(false);
    const isAnimatingRecenterRef = useRef(false);
    const carBearingRef = useRef(0);
    const [mapLoaded, setMapLoaded] = React.useState(false);"""
)

# 3. clearMapRoutes
content = content.replace(
    "        map.current.getSource('route-signal').setData(emptyFC);\n        map.current.getSource('dead-zones').setData(emptyFC);\n        map.current.getSource('car').setData({ type: 'Feature', geometry: { type: 'Point', coordinates: [77.5946, 12.9716] } });\n    };",
    "        map.current.getSource('route-signal').setData(emptyFC);\n        map.current.getSource('dead-zones').setData(emptyFC);\n    };"
)

# 4. updateMapWithRoutes
content = content.replace(
    "            map.current.getSource('dead-zones').setData({ type: 'FeatureCollection', features: deadZoneFeatures });\n\n            // Reset car to start\n            map.current.getSource('car').setData({ type: 'Feature', geometry: { type: 'Point', coordinates: coordsA[0] } });\n        }\n    };",
    "            map.current.getSource('dead-zones').setData({ type: 'FeatureCollection', features: deadZoneFeatures });\n        }\n    };"
)

# 5. Add markers sync
content = content.replace(
    """    useEffect(() => {
        if (!mapLoaded || !map.current) return;
        if (originCoords && originMarkerRef.current) {
            originMarkerRef.current.setLngLat(originCoords).addTo(map.current);
        }
        if (destinationCoords && destMarkerRef.current) {
            destMarkerRef.current.setLngLat(destinationCoords).addTo(map.current);
        }
    }, [originCoords, destinationCoords, mapLoaded]);""",
    """    // Sync markers if coords change from elsewhere
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
    }, [destinationCoords, isNavigating]);"""
)

# 6. VEHICLE MARKER layer replace
vehicle_marker_old = """                // ═══════════════════════════════════════════════════
                // 5. VEHICLE MARKER
                // ═══════════════════════════════════════════════════
                map.current.addSource('car', {
                    type: 'geojson',
                    data: { type: 'Feature', geometry: { type: 'Point', coordinates: [77.5946, 12.9716] } }
                });
                map.current.addLayer({
                    id: 'car-pulse', type: 'circle', source: 'car',
                    paint: { 'circle-color': '#3b82f6', 'circle-radius': 16, 'circle-opacity': 0, 'circle-blur': 0.5, 'circle-opacity-transition': { duration: 500 } }
                });
                map.current.addLayer({
                    id: 'car-core', type: 'circle', source: 'car',
                    paint: { 'circle-color': '#ffffff', 'circle-radius': 5, 'circle-opacity': 0, 'circle-opacity-transition': { duration: 500 } }
                });"""

vehicle_marker_new = """                // ═══════════════════════════════════════════════════
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
                .addTo(map.current);"""
content = content.replace(vehicle_marker_old, vehicle_marker_new)

# 7. Add dynamic color to interpolation controller
interp_old = """            if (map.current.getSource('dead-zones')) {
                map.current.getSource('dead-zones').setData({
                    type: 'FeatureCollection',
                    features: getDeadZoneFeatures(selectedRoute),
                });
            }
        } catch (err) {"""
interp_new = """            if (map.current.getSource('dead-zones')) {
                map.current.getSource('dead-zones').setData({
                    type: 'FeatureCollection',
                    features: getDeadZoneFeatures(selectedRoute),
                });
            }

            // Dynamically update car color if it exists
            if (carMarkerRef.current) {
                const svgPath = carMarkerRef.current.getElement().querySelector('path');
                if (svgPath) {
                    svgPath.setAttribute('fill', preferredRouteIndex === 0 ? '#10b981' : '#3b82f6');
                }
            }
        } catch (err) {"""
content = content.replace(interp_old, interp_new)


with open(file_path, 'w') as f:
    f.write(content)
print("Applied initial patches")
