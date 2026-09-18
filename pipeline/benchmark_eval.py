# benchmark_eval.py
# Run with: python3 benchmark_eval.py
# This script evaluates the trained NeuralPathGNN and runs ablations
# against a standard GCN and Tabular ML to generate metrics for the paper.

import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor

# Import the data loader and model from the existing pipeline
from gnn_pipeline import build_pyg_graph, NeuralPathGNN, FEATURES_PATH, GRAPH_PATH, FEATURE_COLS

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data_bnglr"

# Point to the pre-trained weights
MODEL_WEIGHTS = DATA_DIR / "best_model.pt"

# ── ABLATION MODEL: STANDARD GCN ──────────────────────────────────────────────
from torch_geometric.nn import GCNConv, GraphNorm

class BaselineGCN(torch.nn.Module):
    """Standard GCN uses 'mean' aggregation, washing out strong RF signals."""
    def __init__(self, in_channels, hidden=128, dropout=0.4):
        super().__init__()
        self.conv1  = GCNConv(in_channels, hidden)
        self.norm1  = GraphNorm(hidden)
        self.conv2  = GCNConv(hidden, hidden)
        self.norm2  = GraphNorm(hidden)
        self.lin1   = torch.nn.Linear(hidden, hidden // 2)
        self.lin2   = torch.nn.Linear(hidden // 2, 1)
        self.drop   = dropout

    def forward(self, x, edge_index):
        h1 = self.conv1(x, edge_index)
        h1 = F.relu(self.norm1(h1))
        h1 = F.dropout(h1, p=self.drop, training=self.training)
        
        h2 = self.conv2(h1, edge_index)
        h2 = F.relu(self.norm2(h2))
        h2 = h2 + h1 # Skip connection
        h2 = F.dropout(h2, p=self.drop, training=self.training)
        
        out = F.relu(self.lin1(h2))
        return torch.sigmoid(self.lin2(out)).squeeze() * 100.0

# ── EVALUATION UTILS ──────────────────────────────────────────────────────────
def compute_metrics(y_true, y_pred, name="Model"):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    print(f"  {name:>25} | MAE: {mae:5.2f} | RMSE: {rmse:5.2f}")
    return mae, rmse

# ── MAIN BENCHMARK SCRIPT ─────────────────────────────────────────────────────
def run_benchmarks():
    print("=== CONNECTIVITY INTELLIGENCE BENCHMARK SUITE ===")
    
    # 1. Load Data
    data, scaler, df, G, edge_list = build_pyg_graph(FEATURES_PATH, GRAPH_PATH)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    data = data.to(device)
    
    # Extract test mask
    tm = data.test_mask & ~torch.isnan(data.y)
    y_test_true = data.y[tm].cpu().numpy()
    
    print(f"\n[Evaluating on 20x20 Geographically Isolated Test Block: {tm.sum().item()} segments]")
    print("-" * 60)

    # 2. Evaluate Proposed Model (NeuralPathGNN with Max Aggregation)
    model_proposed = NeuralPathGNN(in_channels=len(FEATURE_COLS)).to(device)
    if MODEL_WEIGHTS.exists():
        model_proposed.load_state_dict(torch.load(MODEL_WEIGHTS, map_location=device, weights_only=True))
    else:
        print(f"Warning: {MODEL_WEIGHTS} not found. Running untrained weights.")
        
    model_proposed.eval()
    with torch.no_grad():
        out_proposed = model_proposed(data.x, data.edge_index)
        y_test_pred_proposed = out_proposed[tm].cpu().numpy()
        
    compute_metrics(y_test_true, y_test_pred_proposed, "Proposed (GraphSAGE-Max)")

    # 3. Evaluate Ablation (Baseline GCN with Mean Aggregation)
    print("\n[Running Ablation: Training Baseline GCN (Mean Aggregation)]")
    model_gcn = BaselineGCN(in_channels=len(FEATURE_COLS)).to(device)
    opt = torch.optim.Adam(model_gcn.parameters(), lr=0.001)
    
    model_gcn.train()
    # Quick train for ablation comparison (use 150 epochs for speed)
    for epoch in range(150):
        opt.zero_grad()
        out = model_gcn(data.x, data.edge_index)
        mask = data.train_mask & ~torch.isnan(data.y)
        loss = F.huber_loss(out[mask], data.y[mask], delta=10.0)
        loss.backward()
        opt.step()

    model_gcn.eval()
    with torch.no_grad():
        out_gcn = model_gcn(data.x, data.edge_index)
        y_test_pred_gcn = out_gcn[tm].cpu().numpy()
        
    compute_metrics(y_test_true, y_test_pred_gcn, "Ablation (GCN-Mean)")

    # 4. Evaluate Tabular Baseline (Random Forest - No spatial graph data)
    print("\n[Running Baseline: Tabular ML (Ignores Network Topology)]")
    X_train = data.x[data.train_mask & ~torch.isnan(data.y)].cpu().numpy()
    y_train = data.y[data.train_mask & ~torch.isnan(data.y)].cpu().numpy()
    
    X_test = data.x[tm].cpu().numpy()
    
    rf = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
    rf.fit(X_train, y_train)
    y_test_pred_rf = rf.predict(X_test)
    
    compute_metrics(y_test_true, y_test_pred_rf, "Tabular (Random Forest)")
    
    # 5. Evaluate Spatial KNN Baseline (Only uses Lat/Lon, no physics features)
    print("\n[Running Baseline: Spatial KNN (Ignores Physics Features)]")
    # Features: [midpoint_lat, midpoint_lon]
    coords_train = df.loc[(data.train_mask & ~torch.isnan(data.y)).cpu().numpy(), ['midpoint_lat', 'midpoint_lon']].values
    coords_test = df.loc[tm.cpu().numpy(), ['midpoint_lat', 'midpoint_lon']].values
    
    knn = KNeighborsRegressor(n_neighbors=5, weights='distance')
    knn.fit(coords_train, y_train)
    y_test_pred_knn = knn.predict(coords_test)
    
    compute_metrics(y_test_true, y_test_pred_knn, "Spatial KNN (Lat/Lon)")
    print("-" * 60)
    print("Benchmark complete. Copy these metrics directly into your IEEE paper results section.")

if __name__ == "__main__":
    run_benchmarks()
