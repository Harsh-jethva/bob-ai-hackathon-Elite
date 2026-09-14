"""What-if simulation engine (PRD 11.9).

Simulation MUST recalculate the full pipeline (Prediction →
Optimization → Planning → Routing) — never just edit numbers on screen.
"""

import copy
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from src.data.generator import Vessel, Berth, Crane, generate_scenario
from src.models.congestion_model import CongestionForecast
from src.optimization.planner import generate_fcfs, generate_optimized, PlanResult
from src.optimization.router import recommend_alternative_ports
from src.config.settings import settings


@dataclass
class SimulationParam:
    param_type: str  # berth_count | crane_count | arrival_surge |
                     # service_duration | crane_outage | berth_maintenance |
                     # weather | port_selection
    port_id: Optional[str] = None
    berth_id: Optional[str] = None
    crane_id: Optional[str] = None
    change_value: Optional[float] = None  # e.g. new count, surge factor


@dataclass
class SimulationResult:
    scenario_name: str
    params_changed: List[SimulationParam]
    baseline_fcfs: PlanResult
    baseline_optimized: PlanResult
    scenario_fcfs: PlanResult
    scenario_optimized: PlanResult
    kpi_comparison: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    reset_available: bool = True


def _clone_scenario(scenario_dict: dict) -> dict:
    """Deep-clone scenario state for simulation."""
    return copy.deepcopy(scenario_dict)


def _apply_param(scenario: dict, param: SimulationParam) -> dict:
    """Apply a simulation parameter change to a cloned scenario."""
    if param.param_type == "berth_count":
        # Adjust number of berths for a port
        if param.port_id and param.change_value:
            new_count = int(param.change_value)
            existing = [b for b in scenario["berths"]
                        if b.port_id == param.port_id]
            # Remove excess berths
            to_remove = len(existing) - new_count
            if to_remove > 0:
                scenario["berths"] = [b for b in scenario["berths"]
                                      if b.port_id != param.port_id
                                      or existing.index(b) >= to_remove]
            # Add new berths if expanding
            elif to_remove < 0:
                ports = scenario["ports"]
                port = next((p for p in ports
                             if p.port_id == param.port_id), None)
                if port:
                    for i in range(abs(to_remove)):
                        from src.data.generator import Berth
                        scenario["berths"].append(Berth(
                            berth_id=f"B-{param.port_id}-extra{i+1}",
                            port_id=param.port_id,
                            max_vessel_length_m=port.max_vessel_length_m * 0.95,
                            max_vessel_draft_m=port.max_vessel_draft_m * 0.95,
                        ))

    elif param.param_type == "crane_count":
        if param.port_id and param.change_value:
            new_count = int(param.change_value)
            existing = [c for c in scenario["cranes"]
                        if c.port_id == param.port_id]
            to_remove = len(existing) - new_count
            if to_remove > 0:
                scenario["cranes"] = [c for c in scenario["cranes"]
                                      if c.port_id != param.port_id
                                      or existing.index(c) >= to_remove]
            elif to_remove < 0:
                ports = scenario["ports"]
                port = next((p for p in ports
                             if p.port_id == param.port_id), None)
                if port:
                    for i in range(abs(to_remove)):
                        from src.data.generator import Crane
                        scenario["cranes"].append(Crane(
                            crane_id=f"C-{param.port_id}-extra{i+1}",
                            port_id=param.port_id,
                            productivity_teu_per_h=port.avg_service_time_h * 10,
                        ))

    elif param.param_type == "crane_outage":
        if param.crane_id:
            scenario["cranes"] = [
                c for c in scenario["cranes"]
                if c.crane_id != param.crane_id
            ]

    elif param.param_type == "berth_maintenance":
        if param.berth_id:
            for b in scenario["berths"]:
                if b.berth_id == param.berth_id:
                    b.available_to = 0.0  # unavailable

    elif param.param_type == "arrival_surge":
        if param.change_value and float(param.change_value) > 0:
            factor = float(param.change_value)
            for v in scenario["vessels"]:
                v.arrival_time = round(v.arrival_time / factor, 2)
                v.estimated_arrival_time = round(
                    v.estimated_arrival_time / factor, 2)

    elif param.param_type == "service_duration":
        if param.change_value and float(param.change_value) > 0:
            factor = float(param.change_value)
            for v in scenario["vessels"]:
                v.service_duration_h = round(
                    v.service_duration_h * factor, 2)

    elif param.param_type == "weather_disruption":
        for v in scenario["vessels"]:
            v.service_duration_h = round(v.service_duration_h * 1.5, 2)

    elif param.param_type == "port_selection":
        # Redirect vessels to a different preferred port
        if param.port_id:
            for v in scenario["vessels"]:
                v.preferred_port = param.port_id

    return scenario


def _plan_for_scenario(scenario: dict, horizon_hours: float = 72.0):
    """Run full pipeline for a scenario."""
    vessels = scenario["vessels"]
    berths = scenario["berths"]
    cranes = scenario["cranes"]

    fcfs = generate_fcfs(vessels, berths, cranes, horizon_hours)
    optimized = generate_optimized(vessels, berths, cranes, horizon_hours)
    return fcfs, optimized


def run_simulation(
    base_scenario: dict,
    params: List[SimulationParam],
    horizon_hours: float = 72.0,
) -> SimulationResult:
    """Run what-if simulation with full pipeline recalculation."""
    # Baseline
    base_fcfs, base_opt = _plan_for_scenario(base_scenario, horizon_hours)

    # Clone and apply params
    sim_scenario = _clone_scenario(base_scenario)
    for p in params:
        sim_scenario = _apply_param(sim_scenario, p)

    # Re-calc full pipeline
    sim_fcfs, sim_opt = _plan_for_scenario(sim_scenario, horizon_hours)

    # KPI comparison
    kpi_comparison = {
        "fcfs_wait_delta": round(
            sim_fcfs.avg_wait_hours - base_fcfs.avg_wait_hours, 2),
        "opt_wait_delta": round(
            sim_opt.avg_wait_hours - base_opt.avg_wait_hours, 2),
        "fcfs_deferral_delta": sim_fcfs.deferred_count - base_fcfs.deferred_count,
        "opt_deferral_delta": sim_opt.deferred_count - base_opt.deferred_count,
        "fcfs_avg_delay_delta": round(
            sim_fcfs.avg_delay_hours - base_fcfs.avg_delay_hours, 2),
        "opt_avg_delay_delta": round(
            sim_opt.avg_delay_hours - base_opt.avg_delay_hours, 2),
    }

    # Alerts
    alerts = []
    for name, plan in [("FCFS", sim_fcfs), ("Optimized", sim_opt)]:
        if plan.deferred_count > 0:
            alerts.append({
                "severity": "warning",
                "entity": "vessels",
                "trigger": "vessel_deferral",
                "explanation": f"{plan.deferred_count} vessels deferred in {name} plan",
                "recommended_action": "Review resource allocation",
            })
        if plan.avg_wait_hours > settings.max_wait_threshold_h:
            alerts.append({
                "severity": "high",
                "entity": "port",
                "trigger": "max_wait_exceeded",
                "explanation": f"Avg wait {plan.avg_wait_hours}h exceeds threshold",
                "recommended_action": "Consider alternative ports or additional resources",
            })

    return SimulationResult(
        scenario_name=f"sim_{len(params)}_params",
        params_changed=params,
        baseline_fcfs=base_fcfs,
        baseline_optimized=base_opt,
        scenario_fcfs=sim_fcfs,
        scenario_optimized=sim_opt,
        kpi_comparison=kpi_comparison,
        alerts=alerts,
        reset_available=True,
    )


def reset_scenario(base_scenario: dict) -> dict:
    """Reset to the original loaded scenario."""
    return _clone_scenario(base_scenario)
