import pandas as pd
from datetime import timedelta
from src.config.settings import HORIZON_HOURS, BUCKET_HOURS, CRANE_RATE_TEU_PER_H
from src.models.congestion_model import CongestionModel
from src.optimization.router import recommend_diversions
from src.optimization.berth_allocator import solve_berth_cranes, solve_greedy
from src.data.features import FEATURES

def forecast_buckets(model, live, inbound, ports, now):
    """{port: DataFrame[bucket_start, queue_pred, level]} — recursive 6h rolling forecast."""
    out = {}
    for pid, cfg in ports.items():
        nb = len(cfg["berths"]); rows, hist = [], [live[pid]["waiting_now"]] * 5
        for b in range(HORIZON_HOURS // BUCKET_HOURS):
            t = now + timedelta(hours=b * BUCKET_HOURS)
            win6  = inbound[(inbound.port == pid) & (inbound.eta >= t) & (inbound.eta < t + timedelta(hours=6))]
            win12 = inbound[(inbound.port == pid) & (inbound.eta >= t) & (inbound.eta < t + timedelta(hours=12))]
            f = pd.DataFrame([dict(
                vessels_waiting_now=hist[-1], berth_occupancy_pct=live[pid]["berth_occupancy_pct"],
                crane_util_pct=live[pid]["crane_util_pct"], yard_occupancy_pct=live[pid]["yard_occupancy_pct"],
                arrivals_next_6h=len(win6), teu_next_6h=win6.teu.sum(),
                arrivals_next_12h=len(win12), teu_next_12h=win12.teu.sum(),
                hour=t.hour, dow=t.dayofweek,
                waiting_lag_6h=hist[-1], waiting_lag_12h=hist[-2], waiting_lag_24h=hist[-4])])
            q = float(model.predict(f)[0])
            rows.append(dict(bucket_start=t, queue_pred=q, level=CongestionModel.level(q, nb)))
            hist.append(q)
        out[pid] = pd.DataFrame(rows)
    return out

def build_plan(now, live, inbound, model, ports, diversion_cost, crane_rate=CRANE_RATE_TEU_PER_H):
    # 1) PREDICT congestion for next 72h per port
    forecast = forecast_buckets(model, live, inbound, ports, now)
    # 2) RECOMMEND diversions (requirement #2)
    recs = recommend_diversions(forecast, inbound, ports, diversion_cost, now)
    div = recs.set_index("vessel_id").to_port.to_dict() if len(recs) else {}
    inbound = inbound.copy()
    inbound["planned_port"] = [div.get(v, p) for v, p in zip(inbound.vessel_id, inbound.port)]

    # 3) OPTIMIZE berth + crane assignment per port (requirement #3)
    sched_all, base_all = [], []
    for pid, cfg in ports.items():
        todo = inbound[(inbound.planned_port == pid) & (inbound.eta <= now + timedelta(hours=56))]
        occupied = live[pid]["occupied"]
        opt = solve_berth_cranes(todo, cfg, now, crane_rate=crane_rate, occupied=occupied)
        base = solve_greedy(todo, cfg, now, crane_rate=crane_rate, occupied=occupied)  # FCFS baseline
        if opt is not None and len(opt):
            opt["port"] = pid; sched_all.append(opt)
        if base is not None and len(base):
            base["port"] = pid; base_all.append(base)
    schedule = pd.concat(sched_all, ignore_index=True)
    baseline = pd.concat(base_all, ignore_index=True)

    # 4) KPIs (requirement #4 — the "look at dashboard and decide" layer)
    kpis = dict(
        vessels_planned=len(schedule),
        avg_wait_opt_h=round(schedule.wait_h.mean(), 2),
        avg_wait_fcfs_h=round(baseline.wait_h.mean(), 2),
        max_wait_opt_h=round(schedule.wait_h.max(), 2),
        diversions=len(recs),
        improvement_pct=round(100 * max(0, baseline.wait_h.mean() - schedule.wait_h.mean())
                              / max(baseline.wait_h.mean(), 1e-6), 1))
    return dict(now=now, forecast=forecast, recs=recs, schedule=schedule, kpis=kpis)