# routing_simulation.py
# Simulates 1,000 random trips to prove the effectiveness of the GNN coverage map.

import torch
import numpy as np
import networkx as nx
import random
from pathlib import Path
from tqdm import tqdm

from gnn_pipeline import build_pyg_graph, NeuralPathGNN, FEATURES_PATH, GRAPH_PATH, FEATURE_COLS

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data_bnglr"
MODEL_WEIGHTS = DATA_DIR / "best_model.pt"

# ── 1. LOAD DATA AND RUN GNN ──────────────────────────────────────────────────
print("Loading graph and running GNN inference...")
data, scaler, df, G, edge_list = build_pyg_graph(FEATURES_PATH, GRAPH_PATH)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
data = data.to(device)
model = NeuralPathGNN(in_channels=len(FEATURE_COLS)).to(device)

if MODEL_WEIGHTS.exists():
    model.load_state_dict(torch.load(MODEL_WEIGHTS, map_location=device, weights_only=True))

model.eval()
with torch.no_grad():
    scores = model(data.x, data.edge_index).cpu().numpy()
    composite_scores = np.clip(scores, 0, 100)

print("Updating graph edge weights...")
# Add the scores to the NetworkX graph edges
for i, (u, v, edata) in enumerate(edge_list):
    score = composite_scores[i]
    length = edata.get('length', 50.0)
    
    # Baseline weight (standard distance routing)
    G[u][v][0]['distance_weight'] = length
    
    # Proposed weight: Heavily penalize segments with score < 35 (Dead Zones)
    # Exponential penalty makes the router prefer slightly longer but connected routes
    penalty = 1.0 + 8.0 * np.exp(-score / 15.0) 
    G[u][v][0]['connectivity_weight'] = length * penalty
    G[u][v][0]['signal_score'] = score

nodes = list(G.nodes())

# ── 2. MACRO-SIMULATION ───────────────────────────────────────────────────────
N_TRIPS = 1000
print(f"Simulating {N_TRIPS} random trips across the city...")

baseline_dead_zone_distance = 0
proposed_dead_zone_distance = 0
baseline_total_distance = 0
proposed_total_distance = 0
successful_trips = 0

random.seed(42)

for _ in tqdm(range(N_TRIPS)):
    u = random.choice(nodes)
    v = random.choice(nodes)
    
    try:
        # Route 1: Standard Shortest Path (Baseline)
        path_base = nx.shortest_path(G, source=u, target=v, weight='distance_weight')
        
        # Route 2: Connectivity-Aware Path (Proposed)
        path_prop = nx.shortest_path(G, source=u, target=v, weight='connectivity_weight')
        
        # Evaluate Route 1
        dist_base = 0
        dead_base = 0
        for i in range(len(path_base)-1):
            n1, n2 = path_base[i], path_base[i+1]
            edata = G[n1][n2][0]
            dist_base += edata.get('length', 50)
            if edata.get('signal_score', 100) < 60.0: # Threshold for Poor Signal
                dead_base += edata.get('length', 50)
                
        # Evaluate Route 2
        dist_prop = 0
        dead_prop = 0
        for i in range(len(path_prop)-1):
            n1, n2 = path_prop[i], path_prop[i+1]
            edata = G[n1][n2][0]
            dist_prop += edata.get('length', 50)
            if edata.get('signal_score', 100) < 60.0:
                dead_prop += edata.get('length', 50)
                
        baseline_dead_zone_distance += dead_base
        proposed_dead_zone_distance += dead_prop
        baseline_total_distance += dist_base
        proposed_total_distance += dist_prop
        successful_trips += 1
        
    except nx.NetworkXNoPath:
        continue

# ── 3. COMPUTE METRICS ────────────────────────────────────────────────────────
print("\n" + "="*50)
print(f"ROUTING SIMULATION RESULTS ({successful_trips} TRIPS)")
print("="*50)
print(f"Baseline (Shortest Path) Total Poor Signal Dist : {baseline_dead_zone_distance/1000:.1f} km")
print(f"Proposed (Conn-Aware) Total Poor Signal Dist    : {proposed_dead_zone_distance/1000:.1f} km")
print("-" * 50)

if baseline_dead_zone_distance > 0:
    reduction_pct = ((baseline_dead_zone_distance - proposed_dead_zone_distance) / baseline_dead_zone_distance) * 100
else:
    reduction_pct = 0.0

if baseline_total_distance > 0:
    distance_increase_pct = ((proposed_total_distance - baseline_total_distance) / baseline_total_distance) * 100
else:
    distance_increase_pct = 0.0

print(f"Metrics for the IEEE Paper Abstract & Results:")
print(f"1. Poor Signal Exposure Reduction: {reduction_pct:.1f}%")
print(f"2. Trade-off (Extra Distance Traveled): {distance_increase_pct:.2f}%")
print("="*50)
