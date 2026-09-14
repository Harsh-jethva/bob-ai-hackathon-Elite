"""Rolling 72-hour planning orchestration (PRD 11.6).

Orchestrates FCFS baseline + optimized plan generation with
consistent evaluation populations.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.data.generator import Vessel, Berth, Crane
from src.models.congestion_model import CongestionForecast
from src.optimization.berth_allocator import (
    solve_berth_allocation, SolverResult, SolverStatus, ScheduleAssignment
)
from src.config.settings import settings


@dataclass
class PlanResult:
    plan_type: str  # "FCFS" | "optimized"
    assignments: List[ScheduleAssignment]
    solver_result: Optional[SolverResult]
    forecasts: List[CongestionForecast]
    vessels_count: int
    deferred_count: int
    avg_wait_hours: float
    avg_delay_hours: float
    berth_utilization: float
    crane_utilization: float
    runtime_seconds: float


def _compute_kpis(assignments: List[ScheduleAssignment],
                    vessels: List[Vessel],
                    berths: List[Berth],
                    cranes: List[Crane],
                    horizon_hours: float) -> Dict[str, float]:
    """Compute KPIs for a plan with proper population denominators (PRD 13)."""
    n = len(assignments)
    if n == 0:
        return {
            "avg_wait_hours": 0.0,
            "avg_delay_hours": 0.0,
            "deferred_count": 0,
            "berth_utilization": 0.0,
            "crane_utilization": 0.0,
        }

    scheduled = [a for a in assignments if not a.deferred]
    deferred = [a for a in assignments if a.deferred]

    waits = [a.wait_time for a in scheduled]
    delays = [a.delay for a in scheduled]

    avg_wait = round(sum(waits) / len(waits), 2) if waits else 0.0
    avg_delay = round(sum(delays) / len(delays), 2) if delays else 0.0

    total_berth_cap = max(1.0, len(berths) * horizon_hours)
    total_crane_cap = max(1.0, len(cranes) * horizon_hours)

    berth_occupied_h = sum(max(0.0, min(horizon_hours, a.end_time) - a.start_time) for a in scheduled)
    crane_occupied_h = sum(max(0.0, min(horizon_hours, a.end_time) - a.start_time) for a in scheduled)

    return {
        "avg_wait_hours": avg_wait,
        "avg_delay_hours": avg_delay,
        "deferred_count": len(deferred),
        "berth_utilization": min(1.0, round(berth_occupied_h / total_berth_cap, 3)),
        "crane_utilization": min(1.0, round(crane_occupied_h / total_crane_cap, 3)),
    }


def generate_fcfs(
    vessels: List[Vessel],
    berths: List[Berth],
    cranes: List[Crane],
    horizon_hours: float = 72.0,
) -> PlanResult:
    """Generate FCFS baseline plan (PRD 11.7)."""
    from src.models.congestion_model import predict_congestion
    forecasts = predict_congestion(vessels, berths, cranes, horizon_hours)

    # FCFS = sort by arrival, assign earliest available berth/crane
    assignments = []
    berth_next = {b.berth_id: 0.0 for b in berths}
    crane_next = {c.crane_id: 0.0 for c in cranes}

    for v in sorted(vessels, key=lambda x: x.arrival_time):
        target_port = v.preferred_port or v.destination_port
        port_berths = [b for b in berths if b.port_id == target_port]
        candidates = port_berths if port_berths else berths

        compatible = [b for b in candidates
                      if v.vessel_length_m <= b.max_vessel_length_m
                      and v.vessel_draft_m <= b.max_vessel_draft_m]
        if not compatible:
            compatible = candidates
        best = min(compatible, key=lambda b: berth_next[b.berth_id])
        earliest = max(v.arrival_time, berth_next[best.berth_id])

        port_cranes = [c for c in cranes if c.port_id == best.port_id]
        if not port_cranes:
            port_cranes = cranes
        # Distribute across available cranes at port
        assigned_crane = min(port_cranes, key=lambda c: crane_next[c.crane_id]) if port_cranes else (cranes[0] if cranes else None)
        crane_start = crane_next[assigned_crane.crane_id] if assigned_crane else 0.0
        start = max(earliest, crane_start)
        end = start + v.service_duration_h
        is_unplaced = start >= horizon_hours

        assignments.append(ScheduleAssignment(
            vessel_id=v.vessel_id,
            berth_id=best.berth_id if not is_unplaced else "unassigned",
            crane_id=assigned_crane.crane_id if (assigned_crane and not is_unplaced) else "unassigned",
            start_time=round(start, 2) if not is_unplaced else 0.0,
            end_time=round(end, 2) if not is_unplaced else 0.0,
            wait_time=round(max(0.0, start - v.arrival_time), 2) if not is_unplaced else 0.0,
            delay=round(max(0.0, start - v.arrival_time), 2) if not is_unplaced else 0.0,
            deferred=is_unplaced,
            deferral_reason="Exceeds planning horizon" if is_unplaced else ("Crosses horizon window" if end > horizon_hours else ""),
        ))
        if not is_unplaced:
            berth_next[best.berth_id] = end
            if assigned_crane:
                crane_next[assigned_crane.crane_id] = end

    kpis = _compute_kpis(assignments, vessels, berths, cranes, horizon_hours)
    return PlanResult(
        plan_type="FCFS",
        assignments=assignments,
        solver_result=None,
        forecasts=forecasts,
        vessels_count=len(vessels),
        deferred_count=kpis["deferred_count"],
        avg_wait_hours=kpis["avg_wait_hours"],
        avg_delay_hours=kpis["avg_delay_hours"],
        berth_utilization=kpis["berth_utilization"],
        crane_utilization=kpis["crane_utilization"],
        runtime_seconds=0.0,
    )


def generate_optimized(
    vessels: List[Vessel],
    berths: List[Berth],
    cranes: List[Crane],
    horizon_hours: float = 72.0,
) -> PlanResult:
    """Generate optimized berth- and crane-aware plan (PRD 11.4)."""
    from src.models.congestion_model import predict_congestion
    forecasts = predict_congestion(vessels, berths, cranes, horizon_hours)

    solver_result = solve_berth_allocation(
        vessels, berths, cranes, forecasts, horizon_hours)

    assignments = solver_result.assignments

    # Vessels not in assignments (deferred/solver dropped)
    assigned_ids = {a.vessel_id for a in assignments}
    for v in vessels:
        if v.vessel_id not in assigned_ids:
            assignments.append(ScheduleAssignment(
                vessel_id=v.vessel_id,
                berth_id="unassigned",
                crane_id="unassigned",
                start_time=0.0,
                end_time=0.0,
                wait_time=0.0,
                delay=0.0,
                deferred=True,
                deferral_reason="Not scheduled — solver could not place",
            ))

    kpis = _compute_kpis(assignments, vessels, berths, cranes, horizon_hours)
    return PlanResult(
        plan_type="optimized",
        assignments=assignments,
        solver_result=solver_result,
        forecasts=forecasts,
        vessels_count=len(vessels),
        deferred_count=kpis["deferred_count"],
        avg_wait_hours=kpis["avg_wait_hours"],
        avg_delay_hours=kpis["avg_delay_hours"],
        berth_utilization=kpis["berth_utilization"],
        crane_utilization=kpis["crane_utilization"],
        runtime_seconds=solver_result.runtime_seconds,
    )


def generate_both(
    vessels: List[Vessel],
    berths: List[Berth],
    cranes: List[Crane],
    horizon_hours: float = 72.0,
) -> Tuple[PlanResult, PlanResult]:
    """Generate both FCFS and optimized plans with same population."""
    fcfs = generate_fcfs(vessels, berths, cranes, horizon_hours)
    optimized = generate_optimized(vessels, berths, cranes, horizon_hours)
    return fcfs, optimized
