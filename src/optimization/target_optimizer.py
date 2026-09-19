"""Target Port-Based Congestion Optimization & Decision Engine.

Implements the target-port-first maritime decision workflow:
1. Simulates the target port's 72-hour rolling operations (existing docked vessels,
   crane availability, incoming vessel queue).
2. Computes the evaluated vessel's realistic queue time, berth allocation, and total costs.
3. Evaluates nearby alternative ports with full voyage economics (extra distance,
   fuel burn, port charges, demurrage savings).
4. Produces a justified, data-driven recommendation without arbitrary destination switching.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

from src.data.generator import Vessel, Berth, Crane, PortSpec
from src.config.ports import get_port_distance_nm, get_live_state, PortLiveState
from src.optimization.berth_allocator import solve_berth_allocation, ScheduleAssignment
from src.optimization.planner import generate_optimized, PlanResult
from src.optimization.voyage_cost import (
    VoyageCostParams,
    TargetPortCost,
    DiversionCost,
    compute_target_port_cost,
    compute_diversion_cost,
)
from src.models.congestion_model import predict_congestion, CongestionLevel


class RecommendationVerdict(Enum):
    PROCEED_TO_TARGET = "PROCEED_TO_TARGET"
    CONSIDER_DIVERSION = "CONSIDER_DIVERSION"


@dataclass
class TargetPortAnalysis:
    """Detailed operational analysis of the predetermined target port."""
    port_spec: PortSpec
    live_state: PortLiveState
    total_berths: int
    occupied_berths_now: int
    free_berths_now: int
    total_cranes: int
    busy_cranes_now: int
    incoming_vessels_count: int
    evaluated_vessel_assignment: Optional[ScheduleAssignment]
    expected_wait_hours: float
    service_start_time: float
    service_end_time: float
    congestion_level: CongestionLevel
    berth_utilization: float
    crane_utilization: float
    cost_breakdown: TargetPortCost


@dataclass
class AlternativePortEvaluation:
    """Evaluation of a nearby candidate port against the target port."""
    candidate_port: PortSpec
    is_physically_feasible: bool
    infeasibility_reason: str
    distance_nm: float
    distance_km: float
    expected_wait_hours: float
    diversion_cost: Optional[DiversionCost]
    is_recommended: bool
    summary_verdict: str
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)


@dataclass
class TargetPortOptimizationResult:
    """Final decision result produced by the target-port optimization engine."""
    vessel: Vessel
    target_port: PortSpec
    verdict: RecommendationVerdict
    confidence: float
    headline: str
    detailed_justification: str
    target_analysis: TargetPortAnalysis
    alternatives: List[AlternativePortEvaluation]
    best_alternative: Optional[AlternativePortEvaluation]
    total_target_cost: float
    potential_savings: float


def run_target_port_optimization(
    vessel: Vessel,
    target_port: PortSpec,
    all_ports: List[PortSpec],
    all_berths: List[Berth],
    all_cranes: List[Crane],
    incoming_fleet: List[Vessel],
    cluster_key: str = "india",
    cost_params: Optional[VoyageCostParams] = None,
    horizon_hours: float = 72.0,
    min_saving_threshold_usd: float = 10000.0,
) -> TargetPortOptimizationResult:
    """Execute complete target-port-based congestion simulation and economic routing."""
    if cost_params is None:
        cost_params = VoyageCostParams()

    # -------------------------------------------------------------------------
    # 1. TARGET PORT 72-HOUR SIMULATION
    # -------------------------------------------------------------------------
    target_berths = [b for b in all_berths if b.port_id == target_port.port_id]
    target_cranes = [c for c in all_cranes if c.port_id == target_port.port_id]
    target_live_state = get_live_state(cluster_key, target_port.port_id)

    # Inbound vessels for target port (ensure evaluated vessel is included)
    target_vessels = [
        v for v in incoming_fleet
        if (v.preferred_port == target_port.port_id or v.destination_port == target_port.port_id)
        and v.vessel_id != vessel.vessel_id
    ]
    # Add evaluated vessel
    target_vessels.append(vessel)
    target_vessels.sort(key=lambda x: x.arrival_time)

    # Solve CP-SAT allocation for target port
    target_plan: PlanResult = generate_optimized(target_vessels, target_berths, target_cranes, horizon_hours)

    vessel_assignment = next(
        (a for a in target_plan.assignments if a.vessel_id == vessel.vessel_id), None
    )

    if vessel_assignment and not vessel_assignment.deferred:
        expected_wait = vessel_assignment.wait_time
        start_time = vessel_assignment.start_time
        end_time = vessel_assignment.end_time
    else:
        # If deferred beyond horizon, minimum wait is until horizon
        expected_wait = max(24.0, horizon_hours - vessel.arrival_time)
        start_time = horizon_hours
        end_time = horizon_hours + vessel.service_duration_h

    # Congestion forecast for target port
    forecasts = predict_congestion(target_vessels, target_berths, target_cranes, horizon_hours)
    target_forecast = next((f for f in forecasts if f.port_id == target_port.port_id), None)
    cong_level = target_forecast.congestion_level if target_forecast else CongestionLevel.MEDIUM
    b_util = target_plan.berth_utilization
    c_util = target_plan.crane_utilization

    # Calculate full economic cost at target port
    target_cost = compute_target_port_cost(
        vessel=vessel,
        target_port=target_port,
        wait_hours=expected_wait,
        params=cost_params,
    )

    occ_berths = len(target_live_state.occupied_berths)
    free_berths = target_port.num_berths - occ_berths
    busy_cranes = sum(1 for v in target_live_state.crane_busy_until.values() if v > 0)

    target_analysis = TargetPortAnalysis(
        port_spec=target_port,
        live_state=target_live_state,
        total_berths=target_port.num_berths,
        occupied_berths_now=occ_berths,
        free_berths_now=free_berths,
        total_cranes=target_port.num_cranes,
        busy_cranes_now=busy_cranes,
        incoming_vessels_count=len(target_vessels),
        evaluated_vessel_assignment=vessel_assignment,
        expected_wait_hours=expected_wait,
        service_start_time=start_time,
        service_end_time=end_time,
        congestion_level=cong_level,
        berth_utilization=b_util,
        crane_utilization=c_util,
        cost_breakdown=target_cost,
    )

    # -------------------------------------------------------------------------
    # 2. EVALUATE NEARBY ALTERNATIVE PORTS
    # -------------------------------------------------------------------------
    candidate_ports = [p for p in all_ports if p.port_id != target_port.port_id]
    evaluations: List[AlternativePortEvaluation] = []

    for cand in candidate_ports:
        # Physical compatibility check
        is_length_ok = vessel.vessel_length_m <= cand.max_vessel_length_m
        is_draft_ok = vessel.vessel_draft_m <= cand.max_vessel_draft_m
        is_feasible = is_length_ok and is_draft_ok

        infeasibility_msg = ""
        if not is_length_ok and not is_draft_ok:
            infeasibility_msg = f"Exceeds max length ({cand.max_vessel_length_m}m) & draft ({cand.max_vessel_draft_m}m)"
        elif not is_length_ok:
            infeasibility_msg = f"Vessel length {vessel.vessel_length_m}m exceeds max berth length {cand.max_vessel_length_m}m"
        elif not is_draft_ok:
            infeasibility_msg = f"Vessel draft {vessel.vessel_draft_m}m exceeds max berth draft {cand.max_vessel_draft_m}m"

        dist_nm = get_port_distance_nm(cluster_key, target_port.port_id, cand.port_id)
        dist_km = dist_nm * 1.852

        if not is_feasible:
            evaluations.append(AlternativePortEvaluation(
                candidate_port=cand,
                is_physically_feasible=False,
                infeasibility_reason=infeasibility_msg,
                distance_nm=dist_nm,
                distance_km=round(dist_km, 1),
                expected_wait_hours=0.0,
                diversion_cost=None,
                is_recommended=False,
                summary_verdict="❌ Infeasible",
                pros=[],
                cons=[infeasibility_msg],
            ))
            continue

        # Simulate alternative port 72h operations with evaluated vessel
        cand_berths = [b for b in all_berths if b.port_id == cand.port_id]
        cand_cranes = [c for c in all_cranes if c.port_id == cand.port_id]

        # Alternative arrival time = original arrival + sailing time to diversion
        extra_sailing_h = dist_nm / max(1.0, cost_params.vessel_speed_knots)
        sim_vessel = Vessel(
            vessel_id=vessel.vessel_id,
            vessel_name=vessel.vessel_name,
            arrival_time=round(vessel.arrival_time + extra_sailing_h, 2),
            estimated_arrival_time=round(vessel.arrival_time + extra_sailing_h, 2),
            service_duration_h=vessel.service_duration_h,
            cargo_volume=vessel.cargo_volume,
            priority=vessel.priority,
            vessel_length_m=vessel.vessel_length_m,
            vessel_draft_m=vessel.vessel_draft_m,
            required_cranes=vessel.required_cranes,
            origin_port=vessel.origin_port,
            destination_port=cand.port_id,
            preferred_port=cand.port_id,
            status="scheduled",
        )

        cand_fleet = [
            v for v in incoming_fleet
            if (v.preferred_port == cand.port_id or v.destination_port == cand.port_id)
            and v.vessel_id != vessel.vessel_id
        ]
        cand_fleet.append(sim_vessel)
        cand_fleet.sort(key=lambda x: x.arrival_time)

        cand_plan = generate_optimized(cand_fleet, cand_berths, cand_cranes, horizon_hours)
        cand_assignment = next(
            (a for a in cand_plan.assignments if a.vessel_id == vessel.vessel_id), None
        )

        cand_wait = cand_assignment.wait_time if cand_assignment and not cand_assignment.deferred else 12.0

        # Calculate comprehensive economic comparison
        div_cost = compute_diversion_cost(
            vessel=vessel,
            target_cost=target_cost,
            candidate_port=cand,
            extra_distance_nm=dist_nm,
            wait_hours_at_alt=cand_wait,
            params=cost_params,
            min_saving_threshold_usd=min_saving_threshold_usd,
        )

        pros = []
        cons = []

        if div_cost.net_cost_difference > 0:
            pros.append(f"Financial savings of ${div_cost.net_cost_difference:,.0f} vs target port")
        else:
            cons.append(f"Net financial premium of ${abs(div_cost.net_cost_difference):,.0f}")

        if div_cost.time_difference_hours > 0:
            pros.append(f"Completes cargo operations {div_cost.time_difference_hours:.1f}h earlier")
        else:
            cons.append(f"Adds {abs(div_cost.time_difference_hours):.1f}h total voyage turnaround time")

        if cand_wait < expected_wait:
            pros.append(f"Minimal port waiting: {cand_wait:.1f}h vs {expected_wait:.1f}h at target")
        else:
            cons.append(f"Alternative port also experiencing {cand_wait:.1f}h wait")

        cons.append(f"Additional sailing: {dist_nm:.0f} NM ({div_cost.extra_sailing_fuel_mt:.1f} MT bunker burn)")

        evaluations.append(AlternativePortEvaluation(
            candidate_port=cand,
            is_physically_feasible=True,
            infeasibility_reason="",
            distance_nm=dist_nm,
            distance_km=round(dist_km, 1),
            expected_wait_hours=round(cand_wait, 1),
            diversion_cost=div_cost,
            is_recommended=div_cost.is_economically_viable,
            summary_verdict="✅ Viable Diversion" if div_cost.is_economically_viable else "⚠️ Higher Overall Cost",
            pros=pros,
            cons=cons,
        ))

    # -------------------------------------------------------------------------
    # 3. SYNTHESIZE DECISION & RECOMMENDATION
    # -------------------------------------------------------------------------
    viable_alternatives = [
        e for e in evaluations
        if e.is_physically_feasible and e.diversion_cost and e.diversion_cost.is_economically_viable
    ]

    # Sort viable alternatives by net financial savings descending
    viable_alternatives.sort(
        key=lambda x: x.diversion_cost.net_cost_difference if x.diversion_cost else 0.0,
        reverse=True,
    )

    best_alt = viable_alternatives[0] if viable_alternatives else None

    # Decision logic:
    # A ship should only consider diversion if:
    # 1. Target port is significantly congested (wait exceeds laytime or high congestion)
    # 2. There exists a physically compatible alternative port
    # 3. Diversion net savings exceed threshold after paying for extra fuel + OPEX
    if best_alt and (expected_wait > cost_params.free_laytime_hours or cong_level in (CongestionLevel.HIGH, CongestionLevel.CRITICAL)):
        verdict = RecommendationVerdict.CONSIDER_DIVERSION
        savings = best_alt.diversion_cost.net_cost_difference
        confidence = min(0.92, 0.65 + (savings / max(1.0, target_cost.total_target_cost)) * 0.5)
        headline = f"Consider Diversion to {best_alt.candidate_port.port_name} (Est. Net Savings: ${savings:,.0f})"
        detailed_justification = (
            f"{vessel.vessel_name} faces an expected waiting queue of {expected_wait:.1f} hours at "
            f"{target_port.port_name} ({cong_level.value} congestion, {target_analysis.occupied_berths_now}/{target_port.num_berths} berths busy). "
            f"This will incur estimated waiting OPEX, auxiliary fuel, and demurrage penalties totaling ${target_cost.total_target_cost:,.0f}. "
            f"Diverting {best_alt.distance_nm:.0f} NM to {best_alt.candidate_port.port_name} requires ${best_alt.diversion_cost.extra_sailing_fuel_cost:,.0f} "
            f"in additional bunker fuel ({best_alt.diversion_cost.extra_sailing_fuel_mt:.1f} MT), but reduces waiting time to {best_alt.expected_wait_hours:.1f}h. "
            f"This yields a net bottom-line financial saving of ${savings:,.0f} and saves {best_alt.diversion_cost.time_difference_hours:.1f} hours in total voyage completion."
        )
    else:
        verdict = RecommendationVerdict.PROCEED_TO_TARGET
        savings = 0.0
        confidence = 0.90
        if expected_wait <= cost_params.free_laytime_hours:
            reason = f"estimated waiting time of {expected_wait:.1f}h is within contractual free laytime ({cost_params.free_laytime_hours:.0f}h)"
        else:
            reason = "additional sailing distance and bunker fuel costs exceed potential waiting demurrage savings at alternative ports"

        headline = f"Proceed to Predetermined Destination: {target_port.port_name}"
        detailed_justification = (
            f"{vessel.vessel_name} should maintain course to its predetermined destination ({target_port.port_name}). "
            f"Although {target_port.port_name} currently has {target_analysis.occupied_berths_now}/{target_port.num_berths} berths occupied, {reason}. "
            f"Arbitrary port diversion would cause unnecessary bunker fuel burn, contractual cargo rerouting disruptions, and inland intermodal friction."
        )

    return TargetPortOptimizationResult(
        vessel=vessel,
        target_port=target_port,
        verdict=verdict,
        confidence=round(confidence, 2),
        headline=headline,
        detailed_justification=detailed_justification,
        target_analysis=target_analysis,
        alternatives=evaluations,
        best_alternative=best_alt,
        total_target_cost=target_cost.total_target_cost,
        potential_savings=round(savings, 2),
    )
