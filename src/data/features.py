import numpy as np, pandas as pd
from datetime import timedelta

FEATURES = ["vessels_waiting_now","berth_occupancy_pct","crane_util_pct","yard_occupancy_pct",
            "arrivals_next_6h","teu_next_6h","arrivals_next_12h","teu_next_12h",
            "hour","dow","waiting_lag_6h","waiting_lag_12h","waiting_lag_24h"]

def build_training_table(vessels, snapshots, port_id, label_horizon_h=6):
    df = snapshots.sort_values("ts").copy()
    pv = vessels[vessels.port == port_id]
    for h in (6, 12):
        df[f"arrivals_next_{h}h"] = df.ts.apply(
            lambda t: ((pv.eta >= t) & (pv.eta < t + timedelta(hours=h))).sum())
        df[f"teu_next_{h}h"] = df.ts.apply(
            lambda t: pv.loc[(pv.eta >= t) & (pv.eta < t + timedelta(hours=h)), "teu"].sum())
    df["hour"], df["dow"] = df.ts.dt.hour, df.ts.dt.dayofweek
    for lag in (6, 12, 24):
        df[f"waiting_lag_{lag}h"] = df.vessels_waiting_now.shift(lag)
    df["label_queue_next6h"] = df.vessels_waiting_now.shift(-label_horizon_h)  # target
    return df.dropna(subset=FEATURES + ["label_queue_next6h"])