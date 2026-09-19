"""Rolling 72-hour planning orchestration (PRD 11.6).

Orchestrates FCFS baseline + priority-optimized plan generation with
consistent evaluation populations and comprehensive financial cost modeling.
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
    # Economic cost metrics ($)
    total_demurrage_cost: float = 0.0
    total_cargo_holding_cost: float = 0.0
    total_charter_idle_cost: float = 0.0
    total_schedule_cost: float = 0.0
    p1_avg_wait_hours: float = 0.0
    p2_avg_wait_hours: float = 0.0
    p3_avg_wait_hours: float = 0.0


@dataclass
class VesselCostDetail:
    """Individual vessel cost comparison between FCFS and Priority Optimization."""
    vessel_id: str
    vessel_name: str
    priority: int
    priority_score: float
    cargo_type: str
    cargo_value_usd: float
    fcfs_wait_h: float
    opt_wait_h: float
    wait_reduction_h: float
    fcfs_cost_usd: float
    opt_cost_usd: float
    cost_saved_usd: float
    status: str


@dataclass
class PlanComparisonResult:
    """Detailed financial savings and operational comparison between FCFS and Priority Optimization."""
    fcfs_total_cost_usd: float
    opt_total_cost_usd: float
    net_savings_usd: float
    savings_pct: float
    fcfs_demurrage_usd: float
    opt_demurrage_usd: float
    demurrage_saved_usd: float
    fcfs_holding_usd: float
    opt_holding_usd: float
    holding_saved_usd: float
    fcfs_charter_usd: float
    opt_charter_usd: float
    charter_saved_usd: float
    p1_wait_reduction_h: float
    p2_wait_reduction_h: float
    p3_wait_reduction_h: float
    vessel_details: List[VesselCostDetail] = field(default_factory=list)


def _compute_vessel_schedule_cost(v: Vessel, a: ScheduleAssignment) -> Tuple[float, float, float, float]:
    """Calculate (demurrage, cargo_holding, charter_idle, total_cost) for a vessel assignment."""
    if a.deferred:
        # Deferred penalty: heavy rescheduling + 24h holding + penalty
        holding = 24.0 * getattr(v, "holding_cost_per_hour_usd", 800.0)
        charter = 24.0 * (getattr(v, "vessel_daily_charter_usd", 25_000.0) / 24.0)
        demurrage = 18.0 * getattr(v, "demurrage_rate_per_hour_usd", 1200.0)
        deferral_penalty = 50_000.0
        return (demurrage, holding, charter, demurrage + holding + charter + deferral_penalty)

    wait_h = a.wait_time
    laycan_end = getattr(v, "laycan_end_h", v.arrival_time + 12.0)
    
    # Contractual free laytime (standard 4.0h allowance)
    free_laytime = getattr(v, "free_laytime_hours", 4.0)
    demurrage_wait_h = max(0.0, wait_h - free_laytime)
    
    # Demurrage also triggers if service start time breaches contractual laycan deadline
    demurrage_laycan_h = max(0.0, a.start_time - laycan_end)
    demurrage_h = max(demurrage_wait_h, demurrage_laycan_h)

    demurrage = demurrage_h * getattr(v, "demurrage_rate_per_hour_usd", 1000.0)
    holding = wait_h * getattr(v, "holding_cost_per_hour_usd", 800.0)
    charter = wait_h * (getattr(v, "vessel_daily_charter_usd", 25_000.0) / 24.0)
    total = demurrage + holding + charter

    return (demurrage, holding, charter, total)


def _compute_kpis(
    assignments: List[ScheduleAssignment],
    vessels: List[Vessel],
    berths: List[Berth],
    cranes: List[Crane],
    horizon_hours: float,
) -> Dict[str, Any]:
    """Compute KPIs for a plan with proper population denominators and financial costs."""
    n = len(assignments)
    if n == 0:
        return {
            "avg_wait_hours": 0.0,
            "avg_delay_hours": 0.0,
            "deferred_count": 0,
            "berth_utilization": 0.0,
            "crane_utilization": 0.0,
            "total_demurrage_cost": 0.0,
            "total_cargo_holding_cost": 0.0,
            "total_charter_idle_cost": 0.0,
            "total_schedule_cost": 0.0,
            "p1_avg_wait_hours": 0.0,
            "p2_avg_wait_hours": 0.0,
            "p3_avg_wait_hours": 0.0,
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

    vessels_by_id = {v.vessel_id: v for v in vessels}

    tot_demurrage = 0.0
    tot_holding = 0.0
    tot_charter = 0.0
    tot_cost = 0.0

    p1_waits, p2_waits, p3_waits = [], [], []

    for a in assignments:
        v = vessels_by_id.get(a.vessel_id)
        if v:
            dem, hld, cht, tc = _compute_vessel_schedule_cost(v, a)
            tot_demurrage += dem
            tot_holding += hld
            tot_charter += cht
            tot_cost += tc

            if not a.deferred:
                if v.priority == 1:
                    p1_waits.append(a.wait_time)
                elif v.priority == 2:
                    p2_waits.append(a.wait_time)
                else:
                    p3_waits.append(a.wait_time)

    return {
        "avg_wait_hours": avg_wait,
        "avg_delay_hours": avg_delay,
        "deferred_count": len(deferred),
        "berth_utilization": min(1.0, round(berth_occupied_h / total_berth_cap, 3)),
        "crane_utilization": min(1.0, round(crane_occupied_h / total_crane_cap, 3)),
        "total_demurrage_cost": round(tot_demurrage, 2),
        "total_cargo_holding_cost": round(tot_holding, 2),
        "total_charter_idle_cost": round(tot_charter, 2),
        "total_schedule_cost": round(tot_cost, 2),
        "p1_avg_wait_hours": round(sum(p1_waits) / len(p1_waits), 2) if p1_waits else 0.0,
        "p2_avg_wait_hours": round(sum(p2_waits) / len(p2_waits), 2) if p2_waits else 0.0,
        "p3_avg_wait_hours": round(sum(p3_waits) / len(p3_waits), 2) if p3_waits else 0.0,
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

    # FCFS = sort strictly by arrival time
    assignments = []
    valid_berths = [b for b in berths if getattr(b, "available_to", horizon_hours) > getattr(b, "available_from", 0.0)]
    candidates_pool = valid_berths if valid_berths else berths

    berth_next = {b.berth_id: getattr(b, "available_from", 0.0) for b in candidates_pool}
    crane_next = {c.crane_id: getattr(c, "available_from", 0.0) for c in cranes}

    for v in sorted(vessels, key=lambda x: x.arrival_time):
        target_port = v.preferred_port or v.destination_port
        port_berths = [b for b in candidates_pool if b.port_id == target_port]
        candidates = port_berths if port_berths else candidates_pool

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

        # Assign up to required cranes
        req_cranes = min(v.required_cranes, len(port_cranes))
        sorted_cranes = sorted(port_cranes, key=lambda c: crane_next[c.crane_id])
        assigned_cranes = sorted_cranes[:req_cranes] if req_cranes > 0 else (port_cranes[:1] if port_cranes else [])

        crane_start = max([crane_next[c.crane_id] for c in assigned_cranes], default=earliest)
        start = max(earliest, crane_start)
        end = start + v.service_duration_h
        is_unplaced = start >= horizon_hours or end > getattr(best, "available_to", horizon_hours)

        crane_label = ", ".join(c.crane_id for c in assigned_cranes) if (assigned_cranes and not is_unplaced) else "unassigned"

        assignments.append(ScheduleAssignment(
            vessel_id=v.vessel_id,
            berth_id=best.berth_id if not is_unplaced else "unassigned",
            crane_id=crane_label,
            start_time=round(start, 2) if not is_unplaced else 0.0,
            end_time=round(end, 2) if not is_unplaced else 0.0,
            wait_time=round(max(0.0, start - v.arrival_time), 2) if not is_unplaced else 0.0,
            delay=round(max(0.0, start - v.arrival_time), 2) if not is_unplaced else 0.0,
            deferred=is_unplaced,
            deferral_reason="Exceeds planning horizon" if is_unplaced else ("Crosses horizon window" if end > horizon_hours else ""),
        ))
        if not is_unplaced:
            berth_next[best.berth_id] = end
            for c in assigned_cranes:
                crane_next[c.crane_id] = end

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
        total_demurrage_cost=kpis["total_demurrage_cost"],
        total_cargo_holding_cost=kpis["total_cargo_holding_cost"],
        total_charter_idle_cost=kpis["total_charter_idle_cost"],
        total_schedule_cost=kpis["total_schedule_cost"],
        p1_avg_wait_hours=kpis["p1_avg_wait_hours"],
        p2_avg_wait_hours=kpis["p2_avg_wait_hours"],
        p3_avg_wait_hours=kpis["p3_avg_wait_hours"],
    )


def generate_optimized(
    vessels: List[Vessel],
    berths: List[Berth],
    cranes: List[Crane],
    horizon_hours: float = 72.0,
) -> PlanResult:
    """Generate priority-optimized berth- and crane-aware plan (PRD 11.4)."""
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
        total_demurrage_cost=kpis["total_demurrage_cost"],
        total_cargo_holding_cost=kpis["total_cargo_holding_cost"],
        total_charter_idle_cost=kpis["total_charter_idle_cost"],
        total_schedule_cost=kpis["total_schedule_cost"],
        p1_avg_wait_hours=kpis["p1_avg_wait_hours"],
        p2_avg_wait_hours=kpis["p2_avg_wait_hours"],
        p3_avg_wait_hours=kpis["p3_avg_wait_hours"],
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


def compare_plans(
    fcfs_plan: PlanResult,
    opt_plan: PlanResult,
    vessels: List[Vessel],
) -> PlanComparisonResult:
    """Perform detailed economic cost and operational comparison between FCFS and Priority Optimization."""
    fcfs_by_id = {a.vessel_id: a for a in fcfs_plan.assignments}
    opt_by_id = {a.vessel_id: a for a in opt_plan.assignments}
    vessels_by_id = {v.vessel_id: v for v in vessels}

    vessel_details: List[VesselCostDetail] = []

    for v in vessels:
        a_fcfs = fcfs_by_id.get(v.vessel_id)
        a_opt = opt_by_id.get(v.vessel_id)

        if not a_fcfs or not a_opt:
            continue

        _, _, _, cost_fcfs = _compute_vessel_schedule_cost(v, a_fcfs)
        _, _, _, cost_opt = _compute_vessel_schedule_cost(v, a_opt)

        wait_fcfs = a_fcfs.wait_time if not a_fcfs.deferred else 24.0
        wait_opt = a_opt.wait_time if not a_opt.deferred else 24.0
        wait_diff = round(wait_fcfs - wait_opt, 2)
        cost_diff = round(cost_fcfs - cost_opt, 2)

        if a_opt.deferred:
            status = "⚠️ Deferred"
        elif cost_diff > 0:
            status = f"✅ Saved ${cost_diff:,.0f}"
        elif cost_diff < 0:
            status = f"ℹ️ +${abs(cost_diff):,.0f}"
        else:
            status = "⏸️ Neutral"

        vessel_details.append(VesselCostDetail(
            vessel_id=v.vessel_id,
            vessel_name=v.vessel_name,
            priority=v.priority,
            priority_score=getattr(v, "priority_score", 50.0),
            cargo_type=getattr(v, "cargo_type", "Standard Containerized"),
            cargo_value_usd=getattr(v, "cargo_value_usd", 15_000_000.0),
            fcfs_wait_h=round(wait_fcfs, 2),
            opt_wait_h=round(wait_opt, 2),
            wait_reduction_h=wait_diff,
            fcfs_cost_usd=round(cost_fcfs, 2),
            opt_cost_usd=round(cost_opt, 2),
            cost_saved_usd=cost_diff,
            status=status,
        ))

    # Sort details: highest priority first, then highest cost savings
    vessel_details.sort(key=lambda d: (d.priority, -d.cost_saved_usd))

    net_savings = max(0.0, round(fcfs_plan.total_schedule_cost - opt_plan.total_schedule_cost, 2))
    savings_pct = round((net_savings / max(1.0, fcfs_plan.total_schedule_cost)) * 100.0, 1)
    demurrage_saved = max(0.0, round(fcfs_plan.total_demurrage_cost - opt_plan.total_demurrage_cost, 2))
    holding_saved = max(0.0, round(fcfs_plan.total_cargo_holding_cost - opt_plan.total_cargo_holding_cost, 2))
    charter_saved = max(0.0, round(fcfs_plan.total_charter_idle_cost - opt_plan.total_charter_idle_cost, 2))

    p1_reduction = round(max(0.0, fcfs_plan.p1_avg_wait_hours - opt_plan.p1_avg_wait_hours), 2)
    p2_reduction = round(max(0.0, fcfs_plan.p2_avg_wait_hours - opt_plan.p2_avg_wait_hours), 2)
    p3_reduction = round(max(0.0, fcfs_plan.p3_avg_wait_hours - opt_plan.p3_avg_wait_hours), 2)

    return PlanComparisonResult(
        fcfs_total_cost_usd=fcfs_plan.total_schedule_cost,
        opt_total_cost_usd=opt_plan.total_schedule_cost,
        net_savings_usd=net_savings,
        savings_pct=savings_pct,
        fcfs_demurrage_usd=fcfs_plan.total_demurrage_cost,
        opt_demurrage_usd=opt_plan.total_demurrage_cost,
        demurrage_saved_usd=demurrage_saved,
        fcfs_holding_usd=fcfs_plan.total_cargo_holding_cost,
        opt_holding_usd=opt_plan.total_cargo_holding_cost,
        holding_saved_usd=holding_saved,
        fcfs_charter_usd=fcfs_plan.total_charter_idle_cost,
        opt_charter_usd=opt_plan.total_charter_idle_cost,
        charter_saved_usd=charter_saved,
        p1_wait_reduction_h=p1_reduction,
        p2_wait_reduction_h=p2_reduction,
        p3_wait_reduction_h=p3_reduction,
        vessel_details=vessel_details,
    )
