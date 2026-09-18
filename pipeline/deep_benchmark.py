# deep_benchmark.py
# Comprehensive GNN + Feature Engineering evaluation for IEEE paper.
# Run with: python3 deep_benchmark.py
#
# Generates:
#   1. Feature Ablation Study (drop each physics feature, measure MAE increase)
#   2. Aggregation Strategy Comparison (max vs mean vs sum)
#   3. GNN Depth Ablation (1-layer, 2-layer, 3-layer, 4-layer)
#   4. Loss Function Comparison (Huber vs MSE vs L1)
#   5. Feature Engineering Statistics (distributions, correlations, coverage)
#   6. Spatial Error Analysis (where does the model fail?)
#   7. Per-Carrier Score Analysis

import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch_geometric.nn import SAGEConv, GCNConv, GraphNorm
from torch_geometric.data import Data
import json
import time

from gnn_pipeline import build_pyg_graph, NeuralPathGNN, FEATURES_PATH, GRAPH_PATH, FEATURE_COLS

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data_bnglr"
MODEL_WEIGHTS = DATA_DIR / "best_model.pt"
RESULTS_OUT = SCRIPT_DIR / "benchmark_results.json"

# ── HELPER: QUICK TRAIN + EVAL ────────────────────────────────────────────────
def quick_train_eval(model, data, epochs=200, lr=0.001, label="Model"):
    """Train a model for N epochs and return test MAE, RMSE, R²."""
    device = next(model.parameters()).device
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)

    model.train()
    for epoch in range(1, epochs + 1):
        opt.zero_grad()
        out = model(data.x, data.edge_index)
        mask = data.train_mask & ~torch.isnan(data.y)
        loss = F.huber_loss(out[mask], data.y[mask], delta=10.0)
        loss.backward()
        opt.step()

    model.eval()
    tm = data.test_mask & ~torch.isnan(data.y)
    with torch.no_grad():
        preds = model(data.x, data.edge_index)[tm].cpu().numpy()
    y_true = data.y[tm].cpu().numpy()

    mae  = mean_absolute_error(y_true, preds)
    rmse = np.sqrt(mean_squared_error(y_true, preds))
    r2   = r2_score(y_true, preds)
    return mae, rmse, r2


# ── FLEXIBLE GNN MODEL ────────────────────────────────────────────────────────
class FlexGNN(torch.nn.Module):
    """GNN with configurable depth, aggregation, and conv type."""
    def __init__(self, in_ch, hidden=128, n_layers=2, aggr='max',
                 conv_type='sage', dropout=0.4):
        super().__init__()
        self.convs  = torch.nn.ModuleList()
        self.norms  = torch.nn.ModuleList()
        self.n_layers = n_layers
        self.drop = dropout

        for i in range(n_layers):
            in_c = in_ch if i == 0 else hidden
            if conv_type == 'sage':
                self.convs.append(SAGEConv(in_c, hidden, aggr=aggr))
            else:
                self.convs.append(GCNConv(in_c, hidden))
            self.norms.append(GraphNorm(hidden))

        self.lin1 = torch.nn.Linear(hidden, hidden // 2)
        self.lin2 = torch.nn.Linear(hidden // 2, 1)

    def forward(self, x, edge_index):
        h = x
        h_prev = None
        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            h_new = conv(h, edge_index)
            h_new = F.relu(norm(h_new))
            # Skip connection from layer 1 onwards (if dimensions match)
            if h_prev is not None and h_prev.shape == h_new.shape:
                h_new = h_new + h_prev
            h_new = F.dropout(h_new, p=self.drop, training=self.training)
            h_prev = h_new
            h = h_new

        out = F.relu(self.lin1(h))
        return torch.sigmoid(self.lin2(out)).squeeze() * 100.0


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    results = {}

    print("=" * 65)
    print("  DEEP BENCHMARK SUITE — GNN + Feature Engineering")
    print("=" * 65)

    # ── Load once ─────────────────────────────────────────────────────────────
    data, scaler, df, G, edge_list = build_pyg_graph(FEATURES_PATH, GRAPH_PATH)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    data_gpu = data.to(device)

    tm = data_gpu.test_mask & ~torch.isnan(data_gpu.y)
    n_test = tm.sum().item()
    print(f"\nTest set: {n_test} segments (geographically isolated)")

    # ── 0. Proposed model (pre-trained) ───────────────────────────────────────
    print("\n" + "─" * 65)
    print("  [0] PRE-TRAINED PROPOSED MODEL (NeuralPathGNN)")
    print("─" * 65)
    model_proposed = NeuralPathGNN(in_channels=len(FEATURE_COLS)).to(device)
    model_proposed.load_state_dict(
        torch.load(MODEL_WEIGHTS, map_location=device, weights_only=True))
    model_proposed.eval()
    with torch.no_grad():
        preds_proposed = model_proposed(data_gpu.x, data_gpu.edge_index)[tm].cpu().numpy()
    y_true = data_gpu.y[tm].cpu().numpy()
    mae0  = mean_absolute_error(y_true, preds_proposed)
    rmse0 = np.sqrt(mean_squared_error(y_true, preds_proposed))
    r2_0  = r2_score(y_true, preds_proposed)
    print(f"  MAE: {mae0:.3f} | RMSE: {rmse0:.3f} | R²: {r2_0:.4f}")
    results['proposed'] = {'mae': mae0, 'rmse': rmse0, 'r2': r2_0}

    # ══════════════════════════════════════════════════════════════════════════
    #  TEST 1: FEATURE ABLATION (drop one feature at a time)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("  TEST 1: FEATURE ABLATION STUDY")
    print("  (Drop one physics feature → measure MAE increase)")
    print("═" * 65)

    ablation_results = {}
    for drop_idx, feat_name in enumerate(FEATURE_COLS):
        # Zero out the column in test+train
        x_ablated = data_gpu.x.clone()
        x_ablated[:, drop_idx] = 0.0

        data_abl = Data(
            x=x_ablated, edge_index=data_gpu.edge_index,
            y=data_gpu.y, train_mask=data_gpu.train_mask,
            val_mask=data_gpu.val_mask, test_mask=data_gpu.test_mask,
        ).to(device)

        m = FlexGNN(len(FEATURE_COLS), hidden=128, n_layers=2,
                     aggr='max', conv_type='sage').to(device)
        mae, rmse, r2 = quick_train_eval(m, data_abl, epochs=200,
                                          label=f"Drop {feat_name}")
        delta = mae - mae0
        pct = (delta / mae0) * 100
        print(f"  Drop {feat_name:>20s} → MAE: {mae:.3f}  "
              f"(Δ={delta:+.3f}, {pct:+.1f}%)")
        ablation_results[feat_name] = {
            'mae': round(mae, 3), 'rmse': round(rmse, 3),
            'delta_mae': round(delta, 3), 'pct_increase': round(pct, 1)
        }
    results['feature_ablation'] = ablation_results

    # ══════════════════════════════════════════════════════════════════════════
    #  TEST 2: AGGREGATION STRATEGY COMPARISON
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("  TEST 2: AGGREGATION STRATEGY COMPARISON")
    print("  (max vs mean vs sum in GraphSAGE)")
    print("═" * 65)

    agg_results = {}
    for aggr in ['max', 'mean', 'sum']:
        m = FlexGNN(len(FEATURE_COLS), hidden=128, n_layers=2,
                     aggr=aggr, conv_type='sage').to(device)
        mae, rmse, r2 = quick_train_eval(m, data_gpu, epochs=200,
                                          label=f"SAGEConv-{aggr}")
        print(f"  SAGEConv aggr={aggr:>4s} → MAE: {mae:.3f} | "
              f"RMSE: {rmse:.3f} | R²: {r2:.4f}")
        agg_results[aggr] = {'mae': round(mae, 3), 'rmse': round(rmse, 3),
                              'r2': round(r2, 4)}
    results['aggregation_comparison'] = agg_results

    # ══════════════════════════════════════════════════════════════════════════
    #  TEST 3: GNN DEPTH ABLATION (1, 2, 3, 4 layers)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("  TEST 3: GNN DEPTH ABLATION")
    print("  (How many GNN layers before over-smoothing?)")
    print("═" * 65)

    depth_results = {}
    for n_layers in [1, 2, 3]:
        m = FlexGNN(len(FEATURE_COLS), hidden=128, n_layers=n_layers,
                     aggr='max', conv_type='sage').to(device)
        mae, rmse, r2 = quick_train_eval(m, data_gpu, epochs=200,
                                          label=f"{n_layers}-layer")
        print(f"  {n_layers}-layer SAGEConv → MAE: {mae:.3f} | "
              f"RMSE: {rmse:.3f} | R²: {r2:.4f}")
        depth_results[str(n_layers)] = {
            'mae': round(mae, 3), 'rmse': round(rmse, 3),
            'r2': round(r2, 4)
        }
    results['depth_ablation'] = depth_results

    # ══════════════════════════════════════════════════════════════════════════
    #  TEST 4: LOSS FUNCTION COMPARISON
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("  TEST 4: LOSS FUNCTION COMPARISON")
    print("  (Huber vs MSE vs L1)")
    print("═" * 65)

    loss_results = {}
    for loss_name, loss_fn in [
        ('Huber (δ=10)', lambda o, t: F.huber_loss(o, t, delta=10.0)),
        ('MSE',          lambda o, t: F.mse_loss(o, t)),
        ('L1 (MAE)',     lambda o, t: F.l1_loss(o, t)),
    ]:
        m = FlexGNN(len(FEATURE_COLS), hidden=128, n_layers=2,
                     aggr='max', conv_type='sage').to(device)
        opt = torch.optim.Adam(m.parameters(), lr=0.001, weight_decay=1e-4)
        m.train()
        for ep in range(200):
            opt.zero_grad()
            out = m(data_gpu.x, data_gpu.edge_index)
            mask = data_gpu.train_mask & ~torch.isnan(data_gpu.y)
            loss = loss_fn(out[mask], data_gpu.y[mask])
            loss.backward()
            opt.step()

        m.eval()
        with torch.no_grad():
            preds = m(data_gpu.x, data_gpu.edge_index)[tm].cpu().numpy()
        mae  = mean_absolute_error(y_true, preds)
        rmse = np.sqrt(mean_squared_error(y_true, preds))
        r2   = r2_score(y_true, preds)
        print(f"  {loss_name:>15s} → MAE: {mae:.3f} | "
              f"RMSE: {rmse:.3f} | R²: {r2:.4f}")
        loss_results[loss_name] = {
            'mae': round(mae, 3), 'rmse': round(rmse, 3),
            'r2': round(r2, 4)
        }
    results['loss_comparison'] = loss_results

    # ══════════════════════════════════════════════════════════════════════════
    #  TEST 5: FEATURE ENGINEERING STATISTICS
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("  TEST 5: FEATURE ENGINEERING STATISTICS")
    print("  (Distributions, correlations, coverage)")
    print("═" * 65)

    feat_stats = {}
    rf_cols = ['jio_rf_score', 'airtel_rf_score', 'vi_rf_score', 'bsnl_rf_score']

    # Overall dataset stats
    total_segments = len(df)
    labeled = df[rf_cols].mean(axis=1) > 0
    labeled_count = labeled.sum()
    unlabeled_count = total_segments - labeled_count

    print(f"\n  Total road segments: {total_segments:,}")
    print(f"  Segments with RF data (labeled): {labeled_count:,} "
          f"({100*labeled_count/total_segments:.1f}%)")
    print(f"  Segments without RF data (dead zones): {unlabeled_count:,} "
          f"({100*unlabeled_count/total_segments:.1f}%)")

    feat_stats['total_segments'] = total_segments
    feat_stats['labeled_segments'] = int(labeled_count)
    feat_stats['coverage_pct'] = round(100 * labeled_count / total_segments, 1)

    # Per-feature distribution
    print(f"\n  {'Feature':>22s} | {'Mean':>8s} | {'Std':>8s} | "
          f"{'Min':>8s} | {'Median':>8s} | {'Max':>8s}")
    print("  " + "-" * 75)
    feature_distributions = {}
    for col in FEATURE_COLS:
        vals = df[col].dropna()
        row = {
            'mean': round(float(vals.mean()), 3),
            'std': round(float(vals.std()), 3),
            'min': round(float(vals.min()), 3),
            'median': round(float(vals.median()), 3),
            'max': round(float(vals.max()), 3),
        }
        print(f"  {col:>22s} | {row['mean']:8.3f} | {row['std']:8.3f} | "
              f"{row['min']:8.3f} | {row['median']:8.3f} | {row['max']:8.3f}")
        feature_distributions[col] = row
    feat_stats['distributions'] = feature_distributions

    # Feature-to-label correlation
    print(f"\n  Feature-to-Label Pearson Correlation (labeled segments only):")
    label_vals = df[rf_cols].mean(axis=1)
    correlations = {}
    for col in FEATURE_COLS:
        mask = labeled
        corr = np.corrcoef(df[col][mask].fillna(0), label_vals[mask])[0, 1]
        print(f"    {col:>22s}  →  r = {corr:+.4f}")
        correlations[col] = round(float(corr), 4)
    feat_stats['correlations'] = correlations

    # Per-carrier tower coverage
    print(f"\n  Per-Carrier Coverage (segments with RF score > 0):")
    carrier_coverage = {}
    for col in rf_cols:
        carrier = col.replace('_rf_score', '')
        has_data = (df[col] > 0).sum()
        pct = 100 * has_data / total_segments
        print(f"    {carrier:>8s}: {has_data:>6,} segments ({pct:.1f}%)")
        carrier_coverage[carrier] = {
            'segments': int(has_data), 'pct': round(pct, 1)
        }
    feat_stats['carrier_coverage'] = carrier_coverage

    # SVF distribution
    svf = df['svf']
    print(f"\n  Sky View Factor (SVF) Analysis:")
    print(f"    Mean SVF: {svf.mean():.3f} (1.0 = fully open sky)")
    print(f"    Segments with SVF < 0.5 (dense urban canyon): "
          f"{(svf < 0.5).sum():,} ({100*(svf<0.5).sum()/total_segments:.1f}%)")
    print(f"    Segments with SVF > 0.9 (open road): "
          f"{(svf > 0.9).sum():,} ({100*(svf>0.9).sum()/total_segments:.1f}%)")
    feat_stats['svf_analysis'] = {
        'mean': round(float(svf.mean()), 3),
        'dense_canyon_pct': round(100 * (svf < 0.5).sum() / total_segments, 1),
        'open_road_pct': round(100 * (svf > 0.9).sum() / total_segments, 1),
    }

    # Terrain shadow impact
    ts = df['terrain_shadow']
    shadowed = (ts == 1).sum()
    print(f"\n  Terrain Shadow Analysis:")
    print(f"    Segments with LoS blocked by terrain: "
          f"{shadowed:,} ({100*shadowed/total_segments:.1f}%)")
    if shadowed > 0 and labeled.sum() > 0:
        shadow_mask = (ts == 1) & labeled
        clear_mask  = (ts == 0) & labeled
        if shadow_mask.sum() > 0 and clear_mask.sum() > 0:
            avg_shadow = label_vals[shadow_mask].mean()
            avg_clear  = label_vals[clear_mask].mean()
            print(f"    Avg RF score (shadowed): {avg_shadow:.1f}")
            print(f"    Avg RF score (clear LoS): {avg_clear:.1f}")
            print(f"    Signal degradation from terrain: "
                  f"{avg_clear - avg_shadow:.1f} points")
            feat_stats['terrain_shadow'] = {
                'shadowed_segments': int(shadowed),
                'avg_score_shadowed': round(float(avg_shadow), 1),
                'avg_score_clear': round(float(avg_clear), 1),
                'degradation': round(float(avg_clear - avg_shadow), 1),
            }

    results['feature_stats'] = feat_stats

    # ══════════════════════════════════════════════════════════════════════════
    #  TEST 6: SPATIAL ERROR ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("  TEST 6: SPATIAL ERROR ANALYSIS")
    print("  (Where does the model perform best / worst?)")
    print("═" * 65)

    # Get full predictions from proposed model
    model_proposed.eval()
    with torch.no_grad():
        all_preds = model_proposed(
            data_gpu.x, data_gpu.edge_index).cpu().numpy()

    test_idx = tm.cpu().numpy()
    test_df = df[test_idx].copy()
    test_df['prediction'] = all_preds[test_idx]
    test_df['abs_error'] = np.abs(
        test_df['prediction'] - data.y.cpu().numpy()[test_idx])

    # Error by road type
    road_names = {0: 'Motorway', 1: 'Trunk', 2: 'Primary',
                  3: 'Secondary', 4: 'Tertiary/Residential', 5: 'Service'}
    print(f"\n  Error by Road Type:")
    road_errors = {}
    for enc, name in road_names.items():
        subset = test_df[test_df['road_type_enc'] == enc]
        if len(subset) > 10:
            m = subset['abs_error'].mean()
            print(f"    {name:>25s}: MAE = {m:.2f}  (n={len(subset):,})")
            road_errors[name] = {'mae': round(m, 2), 'n': len(subset)}
    results['spatial_error'] = {'by_road_type': road_errors}

    # Error by SVF bucket
    print(f"\n  Error by SVF (Urban Density):")
    svf_errors = {}
    for lo, hi, label in [(0, 0.3, 'Dense Canyon (0-0.3)'),
                           (0.3, 0.6, 'Moderate (0.3-0.6)'),
                           (0.6, 0.85, 'Suburban (0.6-0.85)'),
                           (0.85, 1.01, 'Open (0.85-1.0)')]:
        subset = test_df[(test_df['svf'] >= lo) & (test_df['svf'] < hi)]
        if len(subset) > 10:
            m = subset['abs_error'].mean()
            print(f"    {label:>25s}: MAE = {m:.2f}  (n={len(subset):,})")
            svf_errors[label] = {'mae': round(m, 2), 'n': len(subset)}
    results['spatial_error']['by_svf'] = svf_errors

    # Error by terrain shadow
    print(f"\n  Error by Terrain Shadow:")
    for shadow_val, label in [(0, 'Clear LoS'), (1, 'Terrain Blocked')]:
        subset = test_df[test_df['terrain_shadow'] == shadow_val]
        if len(subset) > 10:
            m = subset['abs_error'].mean()
            print(f"    {label:>25s}: MAE = {m:.2f}  (n={len(subset):,})")

    # ══════════════════════════════════════════════════════════════════════════
    #  TEST 7: INFERENCE SPEED
    # ══════════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("  TEST 7: INFERENCE SPEED")
    print("═" * 65)

    model_proposed.eval()
    # Warm-up
    with torch.no_grad():
        _ = model_proposed(data_gpu.x, data_gpu.edge_index)
    torch.cuda.synchronize() if torch.cuda.is_available() else None

    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        with torch.no_grad():
            _ = model_proposed(data_gpu.x, data_gpu.edge_index)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        times.append(time.perf_counter() - t0)

    avg_ms = np.mean(times) * 1000
    std_ms = np.std(times) * 1000
    print(f"  Full city inference ({total_segments:,} segments):")
    print(f"    Average: {avg_ms:.1f} ms  (±{std_ms:.1f} ms)")
    print(f"    Throughput: {total_segments / (avg_ms/1000):,.0f} segments/sec")
    results['inference_speed'] = {
        'avg_ms': round(avg_ms, 1),
        'std_ms': round(std_ms, 1),
        'segments': total_segments,
    }

    # ── SAVE ALL RESULTS ──────────────────────────────────────────────────────
    with open(RESULTS_OUT, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "═" * 65)
    print(f"  ALL RESULTS SAVED → {RESULTS_OUT}")
    print("═" * 65)
