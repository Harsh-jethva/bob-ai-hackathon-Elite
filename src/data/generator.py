import numpy as np, pandas as pd
from datetime import timedelta
from src.config.ports import PORTS
from src.config.settings import DATA_DIR

TEU_CHOICES = [300, 600, 1200, 2000, 2800]
TEU_P       = [0.25, 0.30, 0.25, 0.15, 0.05]
HOUR_WEIGHTS = {0:2,1:1,2:1,3:1,4:1,5:2,6:3,7:5,8:8,9:9,10:8,11:7,
                12:5,13:4,14:4,15:5,16:6,17:6,18:4,19:4,20:6,21:7,22:6,23:4}

def generate_vessels(port_id, start, days, base_rate, seed):
    rng, rows, vid = np.random.default_rng(seed), [], 0
    for d in range(days):
        day_scale = rng.uniform(0.6, 1.8)              # some days bunch up (weather etc.)
        for h in range(24):
            lam = base_rate * HOUR_WEIGHTS[h] / sum(HOUR_WEIGHTS.values()) * day_scale
            for _ in range(rng.poisson(lam)):
                teu    = int(rng.choice(TEU_CHOICES, p=TEU_P))
                rows.append(dict(
                    vessel_id=f"{port_id}-V{vid:05d}", name=f"MV {chr(65+vid%26)}-{vid:04d}",
                    port=port_id,
                    eta=start + timedelta(days=d, hours=h, minutes=int(rng.integers(0, 60))),
                    teu=teu,
                    length_m=round(80 + teu/20 + rng.normal(0, 10), 1),
                    draft_m=round(5 + teu/500 + rng.normal(0, 0.3), 2),
                    priority=int(rng.choice([1, 2, 3], p=[0.2, 0.6, 0.2])),
                    status="inbound"))
                vid += 1
    return pd.DataFrame(rows).sort_values("eta").reset_index(drop=True)

def generate_all(days=90, seed=7, start=pd.Timestamp("2024-01-01")):
    frames = [generate_vessels(pid, start, days, cfg["base_arrivals_per_day"], seed + i)
              for i, (pid, cfg) in enumerate(PORTS.items())]
    v = pd.concat(frames).sort_values("eta").reset_index(drop=True)
    v.to_csv(DATA_DIR / "vessels.csv", index=False)
    return v

if __name__ == "__main__":
    v = generate_all()
    print(f"Generated {len(v)} vessel calls -> {DATA_DIR/'vessels.csv'}")