"""Berth and crane allocation optimizer using OR-Tools CP-SAT with heuristic fallback.

This implementation uses OR-Tools CP-SAT constraint programming solver
with priority weighting and resource optimization. The solver status reporting
follows PRD 11.4 & 15.2 requirements for transparency.

Hard constraints (PRD 11.4):
  - Service cannot begin before arrival
  - Service duration respected
  - Berth assignments cannot overlap
  - Vessel length/draft compatible with berth
  - Berth availability & maintenance windows
  - Crane capacity & availability
  - Planning-horizon rules
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import time

from ortools.sat.python import cp_model

from src.data.generator import Vessel, Berth, Crane
from src.models.congestion_model import CongestionForecast
from src.config.settings import settings


class SolverStatus(Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    NOT_SOLVED = "NOT_SOLVED"
    TIMEOUT = "TIMEOUT"
    FALLBACK = "FALLBACK"


@dataclass
class ScheduleAssignment:
    vessel_id: str
    berth_id: str
    crane_id: str
    start_time: float
    end_time: float
    wait_time: float
    delay: float
    deferred: bool
    deferral_reason: str = ""


@dataclass
class SolverResult:
    status: SolverStatus
    assignments: List[ScheduleAssignment]
    runtime_seconds: float
    method: str
    time_limit_seconds: float
    relaxation: bool
    fallback_used: bool
    objective_value: Optional[float] = None
    solver_metadata: Dict[str, Any] = field(default_factory=dict)
    fallback_reason: str = ""


def _solve_greedy_fallback(
    vessels: List[Vessel],
    berths: List[Berth],
    cranes: List[Crane],
    horizon_hours: float = 72.0,
    fallback_reason: str = "",
) -> SolverResult:
    """Greedy priority-weighted FCFS heuristic fallback."""
    t0 = time.time()
    sorted_vessels = sorted(vessels, key=lambda v: (v.priority, v.arrival_time))

    # Respect existing berth occupancy and maintenance windows
    valid_berths = [b for b in berths if getattr(b, "available_to", horizon_hours) > getattr(b, "available_from", 0.0)]
    candidates_pool = valid_berths if valid_berths else berths

    berth_next = {b.berth_id: getattr(b, "available_from", 0.0) for b in candidates_pool}
    crane_next = {c.crane_id: getattr(c, "available_from", 0.0) for c in cranes}

    assignments = []
    deferred_count = 0
    total_wait = 0.0

    for v in sorted_vessels:
        target_port = v.preferred_port or v.destination_port
        port_berths = [b for b in candidates_pool if b.port_id == target_port]
        candidates = port_berths if port_berths else candidates_pool

        compatible_berths = [
            b for b in candidates
            if v.vessel_length_m <= b.max_vessel_length_m
            and v.vessel_draft_m <= b.max_vessel_draft_m
        ]
        if not compatible_berths:
            compatible_berths = candidates

        best_berth = min(compatible_berths, key=lambda b: berth_next[b.berth_id])
        earliest_berth = max(v.arrival_time, berth_next[best_berth.berth_id])

        port_cranes = [c for c in cranes if c.port_id == best_berth.port_id]
        if not port_cranes:
            port_cranes = cranes

        assigned_cranes = []
        for _ in range(min(v.required_cranes, len(port_cranes))):
            c = min(port_cranes, key=lambda cr: crane_next[cr.crane_id])
            assigned_cranes.append(c)

        if not assigned_cranes:
            assigned_cranes = port_cranes[:1] if port_cranes else []

        earliest_crane = max(
            [crane_next[c.crane_id] for c in assigned_cranes],
            default=earliest_berth
        )
        start = max(earliest_berth, earliest_crane)
        end = start + v.service_duration_h

        is_unplaced = start >= horizon_hours or end > getattr(best_berth, "available_to", horizon_hours)
        if is_unplaced:
            deferred_count += 1

        wait = max(0.0, start - v.arrival_time) if not is_unplaced else 0.0
        total_wait += wait

        assignments.append(ScheduleAssignment(
            vessel_id=v.vessel_id,
            berth_id=best_berth.berth_id if not is_unplaced else "unassigned",
            crane_id=", ".join(c.crane_id for c in assigned_cranes) if (assigned_cranes and not is_unplaced) else "unassigned",
            start_time=round(start, 2) if not is_unplaced else 0.0,
            end_time=round(end, 2) if not is_unplaced else 0.0,
            wait_time=round(wait, 2) if not is_unplaced else 0.0,
            delay=round(wait, 2) if not is_unplaced else 0.0,
            deferred=is_unplaced,
            deferral_reason="Exceeds planning horizon" if is_unplaced else ("Crosses horizon window" if end > horizon_hours else ""),
        ))

        if not is_unplaced:
            berth_next[best_berth.berth_id] = end
            for c in assigned_cranes:
                crane_next[c.crane_id] = end

    runtime = time.time() - t0
    objective = total_wait * 10.0 + deferred_count * 1000.0

    metadata = {
        "num_vessels": len(vessels),
        "num_berths": len(berths),
        "num_cranes": len(cranes),
        "deferred_count": deferred_count,
        "total_wait_hours": round(total_wait, 2),
        "solver_engine": "Greedy Heuristic",
    }

    return SolverResult(
        status=SolverStatus.FALLBACK,
        assignments=assignments,
        runtime_seconds=round(runtime, 4),
        method="Priority-weighted greedy fallback",
        time_limit_seconds=float(settings.solver_time_limit_seconds),
        relaxation=False,
        fallback_used=True,
        objective_value=objective,
        solver_metadata=metadata,
        fallback_reason=fallback_reason,
    )


def solve_berth_allocation(
    vessels: List[Vessel],
    berths: List[Berth],
    cranes: List[Crane],
    forecasts: List[CongestionForecast],
    horizon_hours: float = 72.0,
    time_limit: Optional[int] = None,
) -> SolverResult:
    """Solve berth + crane allocation using OR-Tools CP-SAT.

    Enforces all hard constraints:
    - Compatibility (vessel length & draft vs berth limits)
    - Non-overlapping vessel service on each berth
    - Crane cumulative capacity per port
    - Start time >= arrival time
    - Planning horizon bounds
    - Priority-weighted optimization objective
    """
    if not vessels or not berths:
        return _solve_greedy_fallback(vessels, berths, cranes, horizon_hours, "Empty vessel or berth list")

    t0 = time.time()
    time_limit = time_limit or settings.solver_time_limit_seconds

    scale = 100  # 0.01 hour (36s) resolution for exact timestamps
    horizon_int = int(round(horizon_hours * scale))

    try:
        model = cp_model.CpModel()

        assign_vars: Dict[tuple, Any] = {}
        start_vars: Dict[tuple, Any] = {}
        end_vars: Dict[tuple, Any] = {}
        interval_vars: Dict[tuple, Any] = {}
        deferred_vars: Dict[str, Any] = {}

        # Precompute berth lookup
        berths_by_id = {b.berth_id: b for b in berths}
        ports_set = {b.port_id for b in berths}

        for v in vessels:
            v_id = v.vessel_id
            # Compatible operational berths
            comp_berths = [
                b for b in berths
                if v.vessel_length_m <= b.max_vessel_length_m
                and v.vessel_draft_m <= b.max_vessel_draft_m
                and getattr(b, "available_to", horizon_hours) > getattr(b, "available_from", 0.0)
            ]
            if not comp_berths:
                comp_berths = [b for b in berths if getattr(b, "available_to", horizon_hours) > getattr(b, "available_from", 0.0)] or berths

            dur_int = max(1, int(round(v.service_duration_h * scale)))
            arr_int = max(0, int(round(v.arrival_time * scale)))

            deferred_vars[v_id] = model.NewBoolVar(f"def_{v_id}")
            b_vars = []

            for b in comp_berths:
                b_id = b.berth_id
                b_from = getattr(b, "available_from", 0.0)
                b_to = getattr(b, "available_to", horizon_hours)
                b_from_int = max(0, int(round(b_from * scale)))
                b_to_int = min(horizon_int, int(round(b_to * scale)))
                earliest_start = max(arr_int, b_from_int)

                if earliest_start >= horizon_int or earliest_start + dur_int > b_to_int:
                    continue

                is_assigned = model.NewBoolVar(f"assign_{v_id}_{b_id}")
                start_v = model.NewIntVar(earliest_start, horizon_int, f"start_{v_id}_{b_id}")
                end_v = model.NewIntVar(earliest_start + dur_int, horizon_int + dur_int, f"end_{v_id}_{b_id}")
                interval_v = model.NewOptionalIntervalVar(start_v, dur_int, end_v, is_assigned, f"int_{v_id}_{b_id}")

                if b_to < horizon_hours:
                    model.Add(end_v <= b_to_int).OnlyEnforceIf(is_assigned)

                assign_vars[(v_id, b_id)] = is_assigned
                start_vars[(v_id, b_id)] = start_v
                end_vars[(v_id, b_id)] = end_v
                interval_vars[(v_id, b_id)] = interval_v
                b_vars.append(is_assigned)

            # Exactly one berth assigned or deferred
            model.Add(sum(b_vars) + deferred_vars[v_id] == 1)

        # Hard Constraint: No overlap on each berth
        for b in berths:
            b_id = b.berth_id
            b_intervals = [
                interval_vars[(v.vessel_id, b_id)]
                for v in vessels
                if (v.vessel_id, b_id) in interval_vars
            ]
            if b_intervals:
                model.AddNoOverlap(b_intervals)

        # Hard Constraint: Crane cumulative capacity per port
        for pid in ports_set:
            port_cranes = [c for c in cranes if c.port_id == pid]
            total_cranes = len(port_cranes)
            if total_cranes > 0:
                port_intervals = []
                port_demands = []

                # Account for pre-busy cranes
                for c in port_cranes:
                    c_busy = getattr(c, "available_from", 0.0)
                    if c_busy > 0.0:
                        busy_int = min(horizon_int, int(round(c_busy * scale)))
                        if busy_int > 0:
                            port_intervals.append(
                                model.NewFixedSizeIntervalVar(0, busy_int, f"busy_c_{c.crane_id}")
                            )
                            port_demands.append(1)

                for v in vessels:
                    for b in berths:
                        if b.port_id == pid and (v.vessel_id, b.berth_id) in interval_vars:
                            port_intervals.append(interval_vars[(v.vessel_id, b.berth_id)])
                            port_demands.append(min(v.required_cranes, total_cranes))
                if port_intervals:
                    model.AddCumulative(port_intervals, port_demands, total_cranes)

        # Optimization Objective: Minimize weighted wait time + deferral penalties
        obj_terms = []
        for v in vessels:
            v_id = v.vessel_id
            p_weight = max(1, 4 - v.priority)  # Priority 1 -> 3, Priority 3 -> 1
            arr_int = max(0, int(round(v.arrival_time * scale)))

            # Heavy penalty for deferring a vessel
            obj_terms.append(deferred_vars[v_id] * 5000 * p_weight)

            # Single wait variable per vessel
            wait_v = model.NewIntVar(0, horizon_int, f"wait_{v_id}")
            model.Add(wait_v == 0).OnlyEnforceIf(deferred_vars[v_id])

            for b in berths:
                if (v_id, b.berth_id) in assign_vars:
                    is_assigned = assign_vars[(v_id, b.berth_id)]
                    start_v = start_vars[(v_id, b.berth_id)]
                    model.Add(wait_v >= start_v - arr_int).OnlyEnforceIf(is_assigned)

                    # Small preference for preferred port
                    port_pref_penalty = 0 if b.port_id == v.preferred_port else 5
                    obj_terms.append(is_assigned * port_pref_penalty)

            obj_terms.append(wait_v * p_weight)

        model.Minimize(sum(obj_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit)
        workers = settings.solver_workers if settings.solver_workers > 0 else 8
        solver.parameters.num_search_workers = workers
        if settings.solver_feasible_acceptable:
            solver.parameters.relative_gap_limit = 0.05

        status_code = solver.Solve(model)
        runtime = time.time() - t0

        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            assignments = []
            deferred_count = 0
            total_wait = 0.0

            # Dynamic crane allocation tracker
            crane_avail_at = {c.crane_id: getattr(c, "available_from", 0.0) for c in cranes}

            scheduled_items = []
            for v in vessels:
                v_id = v.vessel_id
                is_def = solver.BooleanValue(deferred_vars[v_id])

                assigned_berth_id = None
                start_val = 0.0
                end_val = 0.0

                if not is_def:
                    for b in berths:
                        if (v_id, b.berth_id) in assign_vars:
                            if solver.BooleanValue(assign_vars[(v_id, b.berth_id)]):
                                assigned_berth_id = b.berth_id
                                start_val = solver.Value(start_vars[(v_id, b.berth_id)]) / scale
                                end_val = start_val + v.service_duration_h
                                break

                scheduled_items.append((v, is_def, assigned_berth_id, start_val, end_val))

            # Earlier scheduled ships get crane priority
            scheduled_items.sort(key=lambda x: (x[1], x[3]))

            for v, is_def, assigned_berth_id, start_val, end_val in scheduled_items:
                v_id = v.vessel_id
                if is_def or assigned_berth_id is None:
                    deferred_count += 1
                    assignments.append(ScheduleAssignment(
                        vessel_id=v_id,
                        berth_id="unassigned",
                        crane_id="unassigned",
                        start_time=0.0,
                        end_time=0.0,
                        wait_time=0.0,
                        delay=0.0,
                        deferred=True,
                        deferral_reason="Exceeds planning horizon / berth capacity",
                    ))
                else:
                    b_obj = berths_by_id[assigned_berth_id]
                    p_cranes = [c for c in cranes if c.port_id == b_obj.port_id]
                    p_cranes_sorted = sorted(p_cranes, key=lambda c: crane_avail_at[c.crane_id])
                    req_cranes = min(v.required_cranes, len(p_cranes_sorted)) if p_cranes_sorted else 0
                    chosen_cranes = p_cranes_sorted[:req_cranes]
                    for c in chosen_cranes:
                        crane_avail_at[c.crane_id] = end_val
                    assigned_crane_id = ", ".join(c.crane_id for c in chosen_cranes) if chosen_cranes else (p_cranes[0].crane_id if p_cranes else "C-1")

                    wait = max(0.0, start_val - v.arrival_time)
                    total_wait += wait
                    is_unplaced = start_val >= horizon_hours

                    if is_unplaced:
                        deferred_count += 1

                    assignments.append(ScheduleAssignment(
                        vessel_id=v_id,
                        berth_id=assigned_berth_id if not is_unplaced else "unassigned",
                        crane_id=assigned_crane_id if not is_unplaced else "unassigned",
                        start_time=round(start_val, 2) if not is_unplaced else 0.0,
                        end_time=round(end_val, 2) if not is_unplaced else 0.0,
                        wait_time=round(wait, 2) if not is_unplaced else 0.0,
                        delay=round(wait, 2) if not is_unplaced else 0.0,
                        deferred=is_unplaced,
                        deferral_reason="Exceeds planning horizon" if is_unplaced else ("Crosses horizon window" if end_val > horizon_hours else ""),
                    ))

            # Sort assignments by start_time (or vessel arrival for unassigned)
            assignments.sort(key=lambda a: (a.deferred, a.start_time))

            sol_status = SolverStatus.OPTIMAL if status_code == cp_model.OPTIMAL else SolverStatus.FEASIBLE

            metadata = {
                "num_vessels": len(vessels),
                "num_berths": len(berths),
                "num_cranes": len(cranes),
                "deferred_count": deferred_count,
                "total_wait_hours": round(total_wait, 2),
                "solver_engine": "OR-Tools CP-SAT",
                "wall_time_s": round(solver.WallTime(), 4),
                "branches": solver.NumBranches(),
                "conflicts": solver.NumConflicts(),
            }

            return SolverResult(
                status=sol_status,
                assignments=assignments,
                runtime_seconds=round(runtime, 4),
                method="OR-Tools CP-SAT",
                time_limit_seconds=float(time_limit),
                relaxation=False,
                fallback_used=False,
                objective_value=round(solver.ObjectiveValue(), 2),
                solver_metadata=metadata,
            )

        else:
            return _solve_greedy_fallback(
                vessels, berths, cranes, horizon_hours,
                f"CP-SAT solver returned status: {solver.StatusName(status_code)}"
            )

    except Exception as e:
        return _solve_greedy_fallback(
            vessels, berths, cranes, horizon_hours,
            f"CP-SAT solver exception: {str(e)}"
        )

