import numpy as np, pandas as pd
from datetime import timedelta
from src.config.settings import CONGESTION_THRESHOLDS, BUCKET_HOURS

def recommend_diversions(forecast, inbound, ports, diversion_cost, now, min_lead_h=2):
    """forecast: {port: DataFrame[bucket_start, queue_pred]}. Returns diversion recs."""
    recs, taken = [], set()
    for pid, fc in forecast.items():
        nb = len(ports[pid]["berths"]); thr = CONGESTION_THRESHOLDS[1] * nb
        peak = fc.loc[fc.queue_pred.idxmax()]
        if peak.queue_pred <= thr: continue
        excess = int(np.ceil(peak.queue_pred - thr))
        window_end = peak.bucket_start + timedelta(hours=BUCKET_HOURS + 12)
        cands = inbound[(inbound.port == pid)
                        & (inbound.eta >= now + timedelta(hours=min_lead_h))
                        & (inbound.eta <= window_end)].sort_values("teu", ascending=False)
        n = 0
        for (p, alt), cost_h in diversion_cost.items():
            if p != pid or n >= excess: continue
            alt_thr = CONGESTION_THRESHOLDS[1] * len(ports[alt]["berths"])
            alt_peak = forecast[alt].queue_pred.max() if alt in forecast else 0
            slack = int(np.floor(alt_thr - alt_peak))                  # alt port capacity headroom
            for r in cands.itertuples():
                if n >= min(excess, slack) or r.vessel_id in taken: break
                if not any(r.length_m <= b["length_m"] and r.draft_m <= b["depth_m"]
                           for b in ports[alt]["berths"]): continue
                taken.add(r.vessel_id); n += 1
                recs.append(dict(vessel_id=r.vessel_id, name=r.name, teu=r.teu,
                    from_port=pid, to_port=alt, eta=r.eta, extra_steaming_h=cost_h,
                    reason=(f"Peak predicted queue {peak.queue_pred:.1f} ships vs "
                            f"capacity {thr:.0f} berths around {peak.bucket_start:%d %b %H:%M}")))
    return pd.DataFrame(recs)