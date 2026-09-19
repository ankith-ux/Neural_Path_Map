<p align="center">
  <img src="https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" />
  <img src="https://img.shields.io/badge/PyG-2.5+-3C2179?style=for-the-badge&logo=pyg&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/OSRM-MLD-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/CUDA-CuPy-76B900?style=for-the-badge&logo=nvidia&logoColor=white" />
</p>

# 🧠 NeuralPathMap

**GNN-Powered Connectivity-Aware Navigation for Urban Environments**

> *Predict. Prepare. Never Drop.*

NeuralPathMap is a full-stack urban navigation intelligence platform that uses a Graph Neural Network to predict per-segment cellular connectivity scores across **393,221 road segments** in Bangalore, India. The system integrates physics-based RF propagation modeling, real geospatial data, and live contextual scoring to route users through paths that optimize both travel time and network reliability.

---

## 📑 Table of Contents

- [Key Results](#-key-results)
- [System Architecture](#-system-architecture)
- [Feature Engineering Pipeline](#-feature-engineering-pipeline)
- [GNN Model](#-gnn-model)
- [Backend API](#-backend-api)
- [Frontend](#-frontend)
- [Computer Vision Pipeline](#-computer-vision-pipeline)
- [Personas & Use Cases](#-personas--use-cases)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Data Sources](#-data-sources)
- [Benchmarks](#-benchmarks)
- [License](#-license)

---

## 🏆 Key Results

| Metric | Value |
|---|---|
| **Test MAE** | **1.48** (on 0–100 scale) |
| **Test R²** | **0.969** |
| **Segments Scored** | 393,221 |
| **Inference Speed** | 65.3 ms (full city, GPU) |
| **Poor-Signal Exposure Reduction** | Significant (1,000-trip Monte Carlo simulation) |
| **Distance Trade-off** | Minimal additional travel distance |

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OFFLINE PIPELINE                            │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐    │
│  │  OSM Graph   │   │ Cell Tower   │   │  SRTM Elevation +   │    │
│  │  (OSMnx)     │──▶│ RF Scores    │──▶│  Building SVF +     │    │
│  │  393K edges  │   │ (Hata Model) │   │  Terrain Shadow     │    │
│  └──────────────┘   └──────┬───────┘   └──────────┬───────────┘    │
│                            │                       │                │
│                   ┌────────▼───────────────────────▼─────────┐      │
│                   │    compute_features.py                    │      │
│                   │    16-core parallel + GPU CuPy batching   │      │
│                   │    Output: features_real.parquet           │      │
│                   └────────────────────┬─────────────────────┘      │
│                                        │                            │
│                   ┌────────────────────▼─────────────────────┐      │
│                   │    gnn_pipeline.py                         │      │
│                   │    GraphSAGE (2-layer, max-agg, skip)     │      │
│                   │    Huber loss, spatial block CV            │      │
│                   │    Output: scored_segments.geojson         │      │
│                   └────────────────────┬─────────────────────┘      │
│                                        │                            │
│                   ┌────────────────────▼─────────────────────┐      │
│                   │    extract_safety_features.py              │      │
│                   │    POI density, lighting, landuse, SUV     │      │
│                   │    Output: scored_segments_safe.geojson    │      │
│                   └────────────────────┬─────────────────────┘      │
└────────────────────────────────────────┼────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────┐
│                        ONLINE SERVING                               │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐      │
│  │   OSRM       │   │  FastAPI     │   │  React + MapLibre  │      │
│  │   (Docker)   │◀─▶│  Backend     │◀─▶│  Frontend          │      │
│  │   MLD algo   │   │  Scorer +    │   │  Heatmaps, Routes  │      │
│  └──────────────┘   │  Router +    │   │  Signal Profile    │      │
│                     │  Weather +   │   └────────────────────┘      │
│  ┌──────────────┐   │  Explainer   │                                │
│  │   Redis      │◀─▶│             │                                │
│  │   (Cache)    │   └──────────────┘                                │
│  └──────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 Feature Engineering Pipeline

**`pipeline/compute_features.py`** — Computes a 10-dimensional feature vector for each of the 393K road segments, using 16 CPU cores and optional GPU acceleration (CuPy on RTX 4060).

### Feature Matrix

| Feature | Source | Description |
|---|---|---|
| `svf` | Buildings GeoJSON + Ray Casting | Sky View Factor — 36-ray sweep per segment, fraction unblocked by buildings |
| `jio_rf_score` | Cell Tower Parquet + Okumura-Hata | Per-carrier RF power prediction using physics-based path loss model |
| `airtel_rf_score` | " | " |
| `vi_rf_score` | " | " |
| `bsnl_rf_score` | " | " |
| `elevation` | SRTM 30m DEM (`.hgt` tiles) | Ground elevation at segment midpoint |
| `slope` | SRTM (start/end elev) | Terrain gradient along the road segment (%) |
| `road_type_enc` | OSMnx GraphML | Encoded road class: motorway(0) → service(5) |
| `segment_length` | OSMnx edge geometry | Physical length of the road segment (meters) |
| `dominant_band_enc` | Nearest tower radio type | GSM(0), HSPA(1), LTE(2), NR(3) |

### RF Propagation Model

The per-carrier RF score uses a **vectorised Okumura-Hata path loss model**:

```
L = 69.55 + 26.16·log₁₀(f) − 13.82·log₁₀(hb) − a(hm) + (44.9 − 6.55·log₁₀(hb))·log₁₀(d)
```

Where `f` = carrier frequency (MHz), `d` = distance to tower (km), `hb` = base station height, `hm` = mobile height.

Corrections applied:
- **Building shadow**: Up to 15 dB attenuation scaled by `(1 - SVF)`
- **Terrain shadow**: LOS ray-tracing between segment and nearest tower (10-sample Bresenham); 60% attenuation if blocked
- **Technology multiplier**: NR(1.0×), LTE(0.75×), HSPA(0.4×), GSM(0.1×)

### Labels

Ground truth labels are sourced from **Ookla Speedtest Q4 2024 fixed-tile data**, matched to road segments via spatial join. Log-percentile normalisation (p2→0, p98→100) is applied in the GNN pipeline.

---

## 🧬 GNN Model

**`pipeline/gnn_pipeline.py`** — 2-layer GraphSAGE with max aggregation, skip connections, and spatial block cross-validation.

### Architecture: `NeuralPathGNN`

```
Input (10 features) 
  → SAGEConv(max, 128) → GraphNorm → ReLU → Dropout(0.4)
  → SAGEConv(max, 128) → GraphNorm → ReLU → Skip Connection → Dropout(0.4)
  → Linear(128 → 64) → ReLU
  → Linear(64 → 1) → Sigmoid × 100
```

### Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Aggregation** | `max` | Preserves strong RF signals from nearby towers instead of washing them out via mean |
| **Depth** | 2 layers | Sufficient for geographic propagation; 3+ layers cause over-smoothing (validated by ablation: 3L R²=0.93 vs 2L R²=0.95) |
| **Loss** | Huber (δ=10) | Less sensitive to very-low-speed Ookla outliers than MSE |
| **Split** | 20×20 spatial grid block CV | Prevents data leakage — entire geographic blocks assigned to train/val/test |
| **Skip connection** | Layer 2 output + Layer 1 output | Preserves local features while incorporating neighborhood context |

### Training

- **Optimizer**: Adam (lr=0.001, weight_decay=1e-4)
- **Scheduler**: ReduceLROnPlateau (patience=15, factor=0.5)
- **Early stopping**: 120 epochs patience
- **Hardware**: RTX 4060 (CUDA)
- **Epochs**: Up to 2,000 (typically converges ~400–600)

---

## ⚡ Backend API

**`backend/main.py`** — FastAPI application serving scored routes, heatmap tiles, and NLP segment explanations.

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/route/score` | Score routes between origin/destination with connectivity, safety, and SUV metrics |
| `POST` | `/api/route/rerank` | Re-rank cached routes with a new time–connectivity trade-off alpha (< 100ms) |
| `GET` | `/api/heat/tiles` | H3 resolution-8 heatmap tiles for a carrier within a bounding box |
| `GET` | `/api/segment/{id}/explain` | Natural language explanation for a segment's connectivity score |
| `POST` | `/api/telemetry/report` | Live V2V feedback loop — temporarily override a segment's score |
| `GET` | `/api/health` | Health check — segments loaded, H3 tiles, graph status |

### Online Scoring Pipeline

At request time, precomputed GNN scores are adjusted by:

1. **Weather attenuation** — Live precipitation from OpenMeteo API; band-specific multipliers (5G most affected: 0.60× in heavy rain)
2. **Congestion penalties** — Time-of-day rush-hour zones (Silk Board, Whitefield, Electronic City) with configurable windows
3. **Event penalties** — Venue-proximity scoring (Chinnaswamy Stadium, Palace Grounds, etc.) with pre/post buffer windows
4. **Telemetry overrides** — Live V2V score corrections with TTL-based expiration

### Blended Ranking

Routes are ranked by:
```
edge_weight = α × norm_travel_time + (1-α) × (1 - norm_score) + handoff_penalty
```
Where `α` controls the time–connectivity trade-off and `handoff_penalty = 0.02 × handoff_count`.

### Caching

- **Redis** (optional) + in-memory fallback for route caching (10-min TTL)
- **Weather cache**: 5-minute TTL to avoid redundant API calls
- **Telemetry overrides**: 1-hour TTL, in-memory + Redis for cross-worker persistence

---

## 🗺 Frontend

**`frontend/`** — React 18 + Vite + MapLibre GL JS + Zustand state management.

### Features

- **Interactive Map**: MapLibre GL with multiple base styles, carrier-specific heatmap overlays
- **Route Search**: Origin/destination input with real-time route scoring and comparison
- **Signal Profile**: Per-segment connectivity visualization along the route with progress tracking
- **Navigation Panel**: Turn-by-turn with dead zone warnings, connectivity budget breakdown, and prefetch triggers
- **Carrier Toggle**: Switch between Jio, Airtel, Vi, BSNL, and composite views
- **Persona Panel**: Switch routing profiles (Emergency, IT Shuttle, Ride-Hailing, Safe Commute, SUV)
- **Time Travel Panel**: Simulate routes at different times of day to preview rush-hour impacts
- **Telemetry HUD**: Real-time route telemetry display
- **Camera Controls**: Map view presets for different perspectives

### Tech Stack

| Library | Purpose |
|---|---|
| React 18 | UI framework |
| MapLibre GL | Map rendering (open-source, no API key) |
| Zustand | Lightweight state management |
| Lucide React | Icon library |
| h3-js | H3 hexagonal grid for heatmap tiles |
| TailwindCSS | Utility-first CSS |
| Vite | Build tooling and dev server |

---

## 📷 Computer Vision Pipeline

**`cv_pipeline/cv_demo.py`** — Demonstrates camera-based SVF correction using street-level imagery.

### Pipeline

1. **Fetch** street-level images from Mapillary API for a target road segment
2. **Segment** images using **SegFormer-B2** (nvidia/segformer-b2-finetuned-ade-512-512) for semantic segmentation
3. **Compute** camera-derived Sky View Factor from sky pixel fraction (ADE20K class 2)
4. **Compare** camera SVF vs. geometric SVF (from building polygon ray casting) and measure RSRP prediction error reduction

This demonstrates how CV-derived obstruction data can improve RF coverage predictions beyond what geometric building data alone can achieve.

---

## 👤 Personas & Use Cases

The platform supports 5 routing personas, each with different optimization objectives:

| Persona | Alpha | Behavior |
|---|---|---|
| **Emergency** | 0.10 | Minimizes dead zones; forces zero-dead-zone route if ETA penalty ≤ 30% |
| **Safe Commute** | 0.15 | Three Pillars of Night Safety: visibility (lit roads), activity (POI density), escape (no dead ends) |
| **SUV** | 0.40 | Road suitability scoring: lane count, surface quality, width/height restrictions, access tags |
| **IT Shuttle** | 0.50 | Balanced time–connectivity trade-off (default) |
| **Ride-Hailing** | 0.70 | Prioritizes shortest travel time with basic connectivity awareness |

### Safety Score ("Three Pillars")

```
Safety = 0.45 × road_class + 0.20 × poi_density + 0.15 × landuse 
       + 0.15 × connectivity + 0.05 × lighting
```

Hard-blocked segments: tracks, paths, footways, farmland, forest, quarries.

### SUV Suitability Score

```
SUV = 0.35 × road_class + 0.30 × lane_score + 0.20 × surface_score + 0.15 × connectivity
```

Hard blocks: width < 2.5m, height < 2.2m, weight < 2.5t, dirt/mud/grass surfaces, non-motor-vehicle roads.

---

## 📁 Project Structure

```
Neural_Path_Map/
│
├── pipeline/                       # Offline data processing & ML
│   ├── compute_features.py         # Feature engineering (16-core + GPU)
│   ├── gnn_pipeline.py             # GNN training & GeoJSON export
│   ├── extract_safety_features.py  # Safety + SUV feature augmentation
│   ├── deep_benchmark.py           # Comprehensive ablation studies
│   ├── routing_simulation.py       # 1,000-trip Monte Carlo evaluation
│   ├── benchmark_results.json      # Evaluation metrics
│   ├── download_graph.py           # OSMnx graph download
│   ├── download_building.py        # Building footprint download
│   ├── filter_towers.py            # Cell tower data filtering
│   └── ...
│
├── backend/                        # Online serving (FastAPI)
│   ├── main.py                     # App entry point & endpoints
│   ├── router.py                   # OSRM integration & route scoring
│   ├── scorer.py                   # Weather, congestion, event penalties
│   ├── weather.py                  # Weather simulation & band multipliers
│   ├── explainer.py                # NLP segment explanations
│   ├── cache.py                    # Redis + in-memory caching
│   ├── config.py                   # Constants, zones, venues, personas
│   ├── docker-compose.yml          # OSRM + Redis Docker services
│   ├── requirements.txt            # Python dependencies
│   └── test_api.py                 # API tests
│
├── frontend/                       # Web UI (React + MapLibre)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/                # MapContainer — map rendering & layers
│   │   │   ├── NavigationPanel/    # Turn-by-turn navigation
│   │   │   ├── RouteSearch/        # Origin/destination input
│   │   │   ├── PersonaPanel/       # Persona selection
│   │   │   ├── CarrierToggle/      # Carrier selection
│   │   │   ├── TelemetryHUD/       # Real-time telemetry display
│   │   │   ├── TimeTravelPanel/    # Time-of-day simulation
│   │   │   └── CameraControls/    # Map view presets
│   │   ├── store/                  # Zustand state management
│   │   ├── api/                    # Backend API client
│   │   └── utils/                  # Utility functions
│   ├── package.json
│   └── vite.config.js
│
├── cv_pipeline/                    # Computer vision demo
│   ├── cv_demo.py                  # SegFormer SVF correction
│   └── cv_visualise.py             # Visualization scripts
│
├── geojson/                        # Spatial data (gitignored, large)
│   ├── scored_segments.geojson     # GNN output (~167 MB)
│   ├── scored_segments_safe.geojson # + safety/SUV features (~298 MB)
│   ├── bangalore_graph.graphml     # OSMnx road graph (~150 MB)
│   └── bangalore_buildings.geojson # Building footprints (~191 MB)
│
├── test/                           # Integration & utility tests
│
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Docker** (for OSRM routing engine)
- **CUDA-capable GPU** (optional, for CuPy acceleration & GNN training)

### 1. Clone & Set Up Python Environment

```bash
git clone https://github.com/ankith-ux/Neural_Path_Map.git
cd Neural_Path_Map

python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

For the full pipeline (feature engineering + GNN training):
```bash
pip install torch torchvision torch-geometric
pip install osmnx geopandas rasterio scipy scikit-learn pandas h3 tqdm
pip install cupy-cuda12x  # Optional: GPU acceleration for feature engineering
```

For the CV pipeline:
```bash
pip install transformers pillow
```

### 2. Prepare Data

The data pipeline requires several external datasets. Place them in `data_bnglr/`:

| File | Source | Description |
|---|---|---|
| `bangalore_graph.graphml` | `pipeline/download_graph.py` | OSMnx road network |
| `bangalore_buildings.geojson` | `pipeline/download_building.py` | Building footprints |
| `towers_{jio,airtel,vi,bsnl}.parquet` | OpenCelliD / local scraping | Cell tower locations with radio type & frequency |
| `N12E077.hgt`, `N13E077.hgt` | NASA SRTM 30m | Digital elevation model tiles |
| `ookla_q4_2024/` | Ookla Open Data | Speedtest performance tiles |

### 3. Run the Offline Pipeline

```bash
# Step 1: Compute features (takes ~45 min on 16 cores)
python3 pipeline/compute_features.py

# Step 2: Train GNN and export scored GeoJSON
python3 pipeline/gnn_pipeline.py

# Step 3: Augment with safety + SUV features (requires internet for Overpass API)
python3 pipeline/extract_safety_features.py
```

### 4. Start Infrastructure

```bash
# Start OSRM routing engine + Redis cache
cd backend
docker compose up -d

# Prepare OSRM data (one-time)
# Download Karnataka OSM extract → osrm-data/
# Run: docker run -v ./osrm-data:/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/karnataka-latest.osm.pbf
# Run: docker run -v ./osrm-data:/data osrm/osrm-backend osrm-partition /data/karnataka-latest.osrm
# Run: docker run -v ./osrm-data:/data osrm/osrm-backend osrm-customize /data/karnataka-latest.osrm
```

### 5. Start Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) to access the application.

---

## 📊 Data Sources

| Dataset | License | Usage |
|---|---|---|
| **OpenStreetMap** (via OSMnx) | ODbL | Road network graph, road types, lane counts, surface tags |
| **SRTM 30m** (NASA) | Public Domain | Elevation and slope computation, terrain LOS analysis |
| **Ookla Open Data** | CC BY-NC-SA 4.0 | Speedtest fixed-tile ground truth labels |
| **OpenCelliD** | CC BY-SA 4.0 | Cell tower locations, radio types, frequencies |
| **OpenMeteo API** | CC BY 4.0 | Live weather data for rain attenuation |
| **Overpass API** (OSM) | ODbL | POI density, street lighting, landuse polygons |
| **Mapillary** | CC BY-SA 4.0 | Street-level imagery for CV pipeline |

---

## 📈 Benchmarks

### Feature Ablation Study

Dropping each feature and measuring MAE increase on the test set:

| Feature Dropped | MAE | ΔMAE | Impact |
|---|---|---|---|
| All features (proposed) | **1.48** | — | **Baseline** |
| `vi_rf_score` | 3.00 | +1.52 | **+103%** — most impactful |
| `jio_rf_score` | 2.53 | +1.05 | +71% |
| `bsnl_rf_score` | 2.35 | +0.87 | +59% |
| `road_type_enc` | 2.26 | +0.78 | +53% |
| `slope` | 2.02 | +0.55 | +37% |
| `segment_length` | 2.01 | +0.54 | +36% |
| `elevation` | 1.95 | +0.47 | +32% |
| `airtel_rf_score` | 1.92 | +0.44 | +30% |
| `svf` | 1.86 | +0.39 | +26% |

### Aggregation Comparison

| Strategy | MAE | R² |
|---|---|---|
| **Max** (selected) | 2.61 | 0.918 |
| Mean | 1.80 | 0.951 |
| Sum | 2.00 | 0.940 |

> Max aggregation is used despite slightly higher standalone MAE because it preserves strong RF signals from nearby towers — critical for avoiding false dead zones in routing.

### Spatial Error by SVF Category

| SVF Category | MAE | Segments |
|---|---|---|
| Dense Canyon (0–0.3) | 1.36 | 22,250 |
| Moderate (0.3–0.6) | 1.85 | 4,749 |
| Suburban (0.6–0.85) | 1.58 | 2,117 |
| Open (0.85–1.0) | 1.63 | 3,865 |

---

## 📄 License

This project is for academic and research purposes. See individual data source licenses above for usage restrictions.

---

<p align="center">
  <sub>Built with ☕ in Bangalore</sub>
</p>
