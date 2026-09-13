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
    """Assigns each vessel -> berth + start time + crane count (CP-SAT).
    Falls back to greedy if OR-Tools is missing or the model is infeasible."""
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
        if e >= 0:                                   # future arrival
            lo, hi = e, min(e + max_wait_m, H - 60)
        else:                                        # FIX 1: already arrived & waiting ->
            lo, hi = 0, max_wait_m                   # may wait up to max_wait MORE from now
        hi = max(hi, lo)

        opts = []
        for bi, b in enumerate(berths):
            if r.length_m > b["length_m"] or r.draft_m > b["depth_m"]:
                continue
            for k in range(1, MAXK + 1):
                dur = max(60, int(math.ceil(r.teu / (k * crane_rate) * 60)))
                if lo + dur > H:                     # FIX 2: can't finish inside horizon ->
                    continue                         # drop this option (instead of infeasibility)
                if not opts:                         # create vars once, on first valid option
                    sv = m.NewIntVar(lo, hi, f"s_{v}")
                    ev = m.NewIntVar(lo + 30, H, f"e_{v}")
                    wv = m.NewIntVar(0, max(1, hi - e), f"w_{v}")
                    m.Add(wv == sv - e)
                    starts[v] = sv
                    obj_terms.append(PRIORITY_WEIGHT.get(r.priority, 2) * wv)
                bv = m.NewBoolVar(f"x_{v}_{bi}_{k}")
                x[(v, bi, k)] = bv
                iv = m.NewOptionalIntervalVar(sv, dur, ev, bv, f"iv_{v}_{bi}_{k}")
                berth_iv[bi].append(iv)
                all_iv.append(iv); all_dem.append(k)
                opts.append(bv)
        if opts:
            m.Add(sum(opts) == 1)                    # exactly one berth + crane-count choice
        # else: vessel can't be served this cycle -> skipped (picked up next planning run)

    for occ in (occupied or []):                     # freeze currently-berthed ships
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
            m.AddNoOverlap(berth_iv[bi])             # one ship per berth at a time
    m.AddCumulative(all_iv, all_dem, NC)             # cranes are a shared resource
    if obj_terms:
        m.Minimize(sum(obj_terms))                   # minimize weighted waiting time

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
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
        return solve_greedy(vessels_df, port_cfg, t0, crane_rate, occupied)
    return pd.DataFrame(rows).sort_values("start").reset_index(drop=True)


def solve_greedy(vessels_df, port_cfg, t0, crane_rate=30, occupied=None):
    """FCFS fallback (~current spreadsheet practice) - also the KPI baseline."""
    if vessels_df is None or len(vessels_df) == 0:
        return pd.DataFrame()
    berths = port_cfg["berths"]
    nb = len(berths)
    free = [t0] * nb                                 # FIX 3: one slot PER BERTH (was the crash)
    for occ in (occupied or []):
        bi = int(occ.get("berth_index", 0))
        if 0 <= bi < nb:
            free[bi] = max(free[bi], occ["end"])
    k_def = max(1, min(port_cfg.get("max_cranes_per_vessel", 4),
                       port_cfg["n_cranes"] // nb))
    rows = []
    for r in vessels_df.sort_values(["eta", "priority"]).itertuples():
        feas = [i for i, b in enumerate(berths)
                if r.length_m <= b["length_m"] and r.draft_m <= b["depth_m"]]
        if not feas:
            continue
        i = min(feas, key=lambda j: free[j])         # earliest-free compatible berth
        start = max(r.eta, free[i])
        dur = timedelta(minutes=max(60, int(math.ceil(r.teu / (k_def * crane_rate) * 60))))
        rows.append(dict(vessel_id=r.vessel_id, name=r.name, teu=r.teu,
                         priority=r.priority, berth=berths[i]["id"], berth_index=i,
                         cranes=k_def, eta=r.eta, start=start, end=start + dur,
                         wait_h=max(0.0, (start - r.eta).total_seconds() / 3600)))
        free[i] = start + dur
    return pd.DataFrame(rows).sort_values("start").reset_index(drop=True)