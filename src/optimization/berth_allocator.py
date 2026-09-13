import math
import pandas as pd
from datetime import timedelta
from src.config.settings import PRIORITY_WEIGHT

try:
    from ortools.sat.python import cp_model
    HAVE_ORTOOLS = True
except ImportError:
    HAVE_ORTOOLS = False


def solve_berth_cranes(vessels_df, port_cfg, t0, horizon_h=96, max_wait_h=12,
                       crane_rate=30, occupied=None, time_limit_s=30):
    """Vessel -> berth + start + crane count (CP-SAT).
    Waiting beyond max_wait is a heavy penalty (soft), not forbidden (hard),
    so the model stays feasible even in overloaded scenarios."""
    if not HAVE_ORTOOLS or vessels_df is None or len(vessels_df) == 0:
        return solve_greedy(vessels_df, port_cfg, t0, crane_rate, occupied)

    berths = port_cfg["berths"]
    nb = len(berths)
    NC = port_cfg["n_cranes"]
    MAXK = min(port_cfg.get("max_cranes_per_vessel", 4), NC)
    H = int(horizon_h * 60)
    max_wait_m = int(max_wait_h * 60)

    m = cp_model.CpModel()
    x, starts, obj_terms = {}, {}, []
    berth_iv = {i: [] for i in range(nb)}
    all_iv, all_dem = [], []

    for r in vessels_df.itertuples():
        v = r.vessel_id
        e = int((r.eta - t0).total_seconds() // 60)
        lo = max(0, e)          # cannot start before arrival / before now
        hi = H - 60             # must finish inside the planning horizon
        opts = []
        for bi, b in enumerate(berths):
            if r.length_m > b["length_m"] or r.draft_m > b["depth_m"]:
                continue
            for k in range(1, MAXK + 1):
                dur = max(60, int(math.ceil(r.teu / (k * crane_rate) * 60)))
                if lo + dur > H:
                    continue
                if not opts:
                    sv = m.NewIntVar(lo, hi, f"s_{v}")
                    ev = m.NewIntVar(lo + 30, H, f"e_{v}")
                    wv = m.NewIntVar(0, max(1, H - e), f"w_{v}")
                    late = m.NewIntVar(0, H, f"late_{v}")
                    m.Add(wv == sv - e)                    # total waiting minutes
                    m.Add(late >= sv - (lo + max_wait_m))  # minutes past 12h target
                    w = PRIORITY_WEIGHT.get(r.priority, 2)
                    obj_terms.append(w * wv + 5 * w * late)  # wait cost + deadline penalty
                    starts[v] = sv
                bv = m.NewBoolVar(f"x_{v}_{bi}_{k}")
                x[(v, bi, k)] = bv
                iv = m.NewOptionalIntervalVar(sv, dur, ev, bv, f"iv_{v}_{bi}_{k}")
                berth_iv[bi].append(iv)
                all_iv.append(iv); all_dem.append(k)
                opts.append(bv)
        if opts:
            m.Add(sum(opts) == 1)

    for occ in (occupied or []):
        bi = int(occ.get("berth_index", 0))
        if not (0 <= bi < nb):
            continue
        s = int((occ["start"] - t0).total_seconds() // 60)
        d = max(1, int((occ["end"] - t0).total_seconds() // 60) - s)
        iv = m.NewIntervalVar(s, d, s + d, f"fix_{occ['vessel_id']}")
        berth_iv[bi].append(iv)
        all_iv.append(iv); all_dem.append(int(occ.get("cranes", 1)))

    for bi in range(nb):
        if berth_iv[bi]:
            m.AddNoOverlap(berth_iv[bi])
    m.AddCumulative(all_iv, all_dem, NC)
    if obj_terms:
        m.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("[warn] CP-SAT found no solution -> greedy fallback")
        return solve_greedy(vessels_df, port_cfg, t0, crane_rate, occupied)

    rows = []
    for r in vessels_df.itertuples():
        v = r.vessel_id
        sel = [key for key in x if key[0] == v and solver.BooleanValue(x[key])]
        if not sel:
            continue
        _, bi, k = sel[0]
        s_min = solver.Value(starts[v])
        dur = max(60, int(math.ceil(r.teu / (k * crane_rate) * 60)))
        rows.append(dict(vessel_id=v, name=r.name, teu=r.teu, priority=r.priority,
                         berth=berths[bi]["id"], berth_index=bi, cranes=k, eta=r.eta,
                         start=t0 + timedelta(minutes=s_min),
                         end=t0 + timedelta(minutes=s_min + dur),
                         wait_h=max(0, s_min - int((r.eta - t0).total_seconds() // 60)) / 60))
    if not rows:
        print("[warn] CP-SAT scheduled no vessels -> greedy fallback")
        return solve_greedy(vessels_df, port_cfg, t0, crane_rate, occupied)
    return pd.DataFrame(rows).sort_values("start").reset_index(drop=True)


def solve_greedy(vessels_df, port_cfg, t0, crane_rate=30, occupied=None):
    """FCFS fallback (~current spreadsheet practice) - also the KPI baseline."""
    if vessels_df is None or len(vessels_df) == 0:
        return pd.DataFrame()
    berths = port_cfg["berths"]
    nb = len(berths)
    free = [t0] * nb
    for occ in (occupied or []):
        bi = int(occ.get("berth_index", 0))
        if 0 <= bi < nb:
            free[bi] = max(free[bi], occ["end"])
    k_def = max(1, min(port_cfg.get("max_cranes_per_vessel", 4), port_cfg["n_cranes"] // nb))
    rows = []
    for r in vessels_df.sort_values(["eta", "priority"]).itertuples():
        feas = [i for i, b in enumerate(berths)
                if r.length_m <= b["length_m"] and r.draft_m <= b["depth_m"]]
        if not feas:
            continue
        i = min(feas, key=lambda j: free[j])
        start = max(r.eta, free[i])
        dur = timedelta(minutes=max(60, int(math.ceil(r.teu / (k_def * crane_rate) * 60))))
        rows.append(dict(vessel_id=r.vessel_id, name=r.name, teu=r.teu, priority=r.priority,
                         berth=berths[i]["id"], berth_index=i, cranes=k_def, eta=r.eta,
                         start=start, end=start + dur,
                         wait_h=max(0.0, (start - r.eta).total_seconds() / 3600)))
        free[i] = start + dur
    return pd.DataFrame(rows).sort_values("start").reset_index(drop=True)