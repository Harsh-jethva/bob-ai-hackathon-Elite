import pandas as pd
from datetime import timedelta
from src.config.settings import CRANE_RATE_TEU_PER_H

def simulate_port(vessels, port_id, cfg, start, hours):
    """FCFS hourly simulation. Returns (schedule_df, snapshots_df)."""
    berths, nb = cfg["berths"], len(cfg["berths"])
    NC, MAXK = cfg["n_cranes"], cfg.get("max_cranes_per_vessel", 4)
    v = vessels[vessels.port == port_id].sort_values("eta")
    queue, berth, sched, snaps = [], [None]*nb, [], []
    for step in range(hours):
        t = start + timedelta(hours=step)
        queue += v[(v.eta >= t) & (v.eta < t + timedelta(hours=1))].to_dict("records")
        queue.sort(key=lambda r: (r["priority"], r["eta"]))            # FCFS + priority
        for i, b in enumerate(berths):                                  # berth = first fit
            if berth[i] is None:
                for j, r in enumerate(queue):
                    if r["length_m"] <= b["length_m"] and r["draft_m"] <= b["depth_m"]:
                        berth[i] = dict(r, berth=b["id"], start=t, remaining=r["teu"], cranes=0)
                        queue.pop(j); break
        active = [s for s in berth if s]
        share = 0
        if active:                                                       # proportional crane sharing
            share = min(MAXK, max(1.0, NC / len(active)))
            for s in active:
                s["cranes"] = share; s["remaining"] -= share * CRANE_RATE_TEU_PER_H
        for i, s in enumerate(berth):
            if s and s["remaining"] <= 0:
                sched.append(dict(vessel_id=s["vessel_id"], name=s["name"], teu=s["teu"],
                    priority=s["priority"], eta=s["eta"], berth=s["berth"],
                    start=s["start"], end=t + timedelta(hours=1),
                    wait_h=(s["start"] - s["eta"]).total_seconds()/3600, cranes=s["cranes"]))
                berth[i] = None
        yard = (sum(s["remaining"] for s in active) + sum(r["teu"] for r in queue)) * 2
        snaps.append(dict(ts=t, port_id=port_id, vessels_waiting_now=len(queue),
            berth_occupancy_pct=100*len(active)/nb,
            crane_util_pct=100*min(1.0, len(active)*share/NC) if active else 0.0,
            yard_occupancy_pct=min(100.0, 100*yard/cfg["yard_capacity_teu"])))
    return pd.DataFrame(sched), pd.DataFrame(snaps)