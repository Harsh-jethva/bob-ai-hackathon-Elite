"""Port Congestion Machine Learning Training Pipeline.

Trains and validates a Gradient Boosted Decision Tree (GBDT) model
on synthetic multi-scenario port operational data to forecast queue lengths
and berth utilization across rolling 72-hour planning horizons.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

from src.data.generator import generate_scenario, generate_ports, generate_berths, generate_cranes, generate_vessels
from src.data.features import build_congestion_features
from src.config.ports import PORT_CLUSTERS
from src.config.settings import settings


def generate_training_dataset(num_samples: int = 150) -> pd.DataFrame:
    """Generate diverse multi-cluster operational feature rows for ML training."""
    rows = []
    scenarios = ["normal", "high_arrival", "crane_outage", "berth_maintenance", "weather_disruption", "congestion"]
    cluster_keys = list(PORT_CLUSTERS.keys())
    rng = np.random.RandomState(settings.random_seed)

    for i in range(num_samples):
        sc_name = scenarios[i % len(scenarios)]
        cluster = cluster_keys[i % len(cluster_keys)]
        fleet_size = rng.randint(8, 45)
        horizon = float(rng.choice([24.0, 48.0, 72.0, 96.0]))

        sc_data = generate_scenario(
            scenario=sc_name,
            num_vessels=fleet_size,
            cluster=cluster,
        )

        ports = sc_data["ports"]
        berths = sc_data["berths"]
        cranes = sc_data["cranes"]
        vessels = sc_data["vessels"]

        for p in ports:
            p_berths = [b for b in berths if b.port_id == p.port_id]
            p_cranes = [c for c in cranes if c.port_id == p.port_id]
            p_vessels = [v for v in vessels if v.preferred_port == p.port_id or v.destination_port == p.port_id]

            if not p_berths:
                continue

            feats = build_congestion_features(p_vessels, p_berths, p_cranes, horizon)
            
            # Ground truth simulated queue ratio
            sim_queue_target = max(0.0, feats["total_service_h"] / max(1.0, len(p_berths) * horizon))
            # Inject slight stochastic noise
            sim_queue_target += rng.normal(0.0, 0.02)
            sim_queue_target = max(0.0, sim_queue_target)

            rows.append({
                "num_vessels": feats["num_vessels"],
                "total_berth_capacity": feats["total_berth_capacity"],
                "total_crane_capacity": feats["total_crane_capacity"],
                "total_service_h": feats["total_service_h"],
                "total_cargo_teu": feats["total_cargo_teu"],
                "arrival_density_per_h": feats["arrival_density_per_h"],
                "berth_utilization": feats["berth_utilization"],
                "crane_utilization": feats["crane_utilization"],
                "target_queue_ratio": sim_queue_target,
            })

    return pd.DataFrame(rows)


def train_model():
    """Train Gradient Boosting model and save artifact to models directory."""
    print("=== Training PortPilot Congestion ML Predictor ===")
    df = generate_training_dataset(num_samples=180)
    print(f"Generated {len(df)} training observation vectors across all regional clusters.")

    feature_cols = [
        "num_vessels",
        "total_berth_capacity",
        "total_crane_capacity",
        "total_service_h",
        "total_cargo_teu",
        "arrival_density_per_h",
        "berth_utilization",
        "crane_utilization",
    ]
    target_col = "target_queue_ratio"

    # Train / test split
    split_idx = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]

    X_train = train_df[feature_cols]
    y_train = train_df[target_col]
    X_test = test_df[feature_cols]
    y_test = test_df[target_col]

    model = GradientBoostingRegressor(
        n_estimators=100,
        learning_rate=0.08,
        max_depth=4,
        random_state=settings.random_seed,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)

    print(f"Train samples: {len(X_train)} | Test samples: {len(X_test)}")
    print(f"Test MAE   = {mae:.4f} queue ratio")
    print(f"Test RMSE  = {rmse:.4f}")
    print(f"Test R^2   = {r2:.4f}")

    # Save model artifact
    models_dir = Path(__file__).resolve().parent.parent.parent / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    out_path = models_dir / "congestion_predictor.joblib"
    joblib.dump(model, out_path)
    print(f"SUCCESS: Model saved to {out_path}")
    return model


if __name__ == "__main__":
    train_model()