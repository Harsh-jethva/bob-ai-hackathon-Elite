import pandas as pd
from src.data.generator import generate_all
from src.simulation.port_sim import simulate_port
from src.data.features import build_training_table
from src.models.congestion_model import CongestionModel
from src.config.ports import PORTS
from src.config.settings import DATA_DIR

def main(days=90):
    start = pd.Timestamp("2024-01-01")
    vessels = generate_all(days=days, start=start)
    tables = []
    for pid, cfg in PORTS.items():
        _, snaps = simulate_port(vessels, pid, cfg, start, hours=days*24)
        tables.append(build_training_table(vessels, snaps, pid))
    df = pd.concat(tables).sort_values("ts")
    split = df.ts.max() - pd.Timedelta(days=14)          # time-based split (no leakage)
    train, test = df[df.ts <= split], df[df.ts > split]

    model = CongestionModel(); model.fit(train)
    pred = model.predict(test)
    err = pred - test.label_queue_next6h.values
    print(f"Train rows: {len(train)} | Test rows: {len(test)}")
    print(f"MAE  = {abs(err).mean():.3f} waiting ships")
    print(f"RMSE = {(err**2).mean()**0.5:.3f}")
    model.save()

if __name__ == "__main__":
    main()