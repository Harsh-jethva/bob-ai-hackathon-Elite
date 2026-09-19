"""Dynamic Multi-Factor Vessel Priority Engine for PortPilot AI.

Evaluates and classifies incoming vessels based on:
1. Cargo Valuation & Perishability (Holding cost per hour, cargo asset value)
2. Contractual Deadlines & Demurrage Risk (Laycan window, demurrage penalty rate)
3. Resource Demand & Turnaround Intensity (Quay cranes required, service duration)
4. Vessel Daily Charter / Capital OPEX (Hourly idle penalty)
5. Physical Berth Scarcity & Draft/Length Constraints (Compatibility tightness)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# Standard Cargo Profiles with realistic financial metrics
CARGO_PROFILES: Dict[str, Dict[str, Any]] = {
    "Reefer / Pharmaceuticals": {
        "unit_value_per_teu": 45000.0,       # High-value temperature sensitive
        "holding_rate_hourly_pct": 0.00015,  # 0.015% per hour of delay (spoilage + capital)
        "demurrage_multiplier": 1.4,
        "urgency_weight": 1.5,
    },
    "High-Value Electronics": {
        "unit_value_per_teu": 38000.0,
        "holding_rate_hourly_pct": 0.00012,
        "demurrage_multiplier": 1.3,
        "urgency_weight": 1.4,
    },
    "Automotive & Machinery": {
        "unit_value_per_teu": 25000.0,
        "holding_rate_hourly_pct": 0.00008,
        "demurrage_multiplier": 1.15,
        "urgency_weight": 1.2,
    },
    "Standard Containerized": {
        "unit_value_per_teu": 12000.0,
        "holding_rate_hourly_pct": 0.00004,
        "demurrage_multiplier": 1.0,
        "urgency_weight": 1.0,
    },
    "Dry Bulk & Minerals": {
        "unit_value_per_teu": 4000.0,
        "holding_rate_hourly_pct": 0.00002,
        "demurrage_multiplier": 0.8,
        "urgency_weight": 0.8,
    },
    "Liquid Bulk / Chemicals": {
        "unit_value_per_teu": 8000.0,
        "holding_rate_hourly_pct": 0.00003,
        "demurrage_multiplier": 0.9,
        "urgency_weight": 0.9,
    },
}


@dataclass
class PriorityBreakdown:
    """Granular factor breakdown for explainable priority scoring."""
    cargo_score: float          # 0 - 100 (Weight: 35%)
    demurrage_score: float      # 0 - 100 (Weight: 30%)
    resource_score: float       # 0 - 100 (Weight: 20%)
    scarcity_score: float       # 0 - 100 (Weight: 15%)
    composite_score: float      # 0 - 100
    priority_level: int         # 1 = Critical, 2 = Standard, 3 = Flexible
    reasons: List[str] = field(default_factory=list)


def evaluate_vessel_priority(
    vessel: Any,
    berths: Optional[List[Any]] = None,
    cranes: Optional[List[Any]] = None,
    planning_horizon_hours: float = 72.0,
) -> PriorityBreakdown:
    """Compute multi-factor priority score and classification for a vessel.

    Factors evaluated:
    - S_cargo: Value of cargo & hourly holding penalty ($2M-$85M range)
    - S_demurrage: Demurrage penalty rate ($/hr) and laycan deadline closeness
    - S_resource: Turnaround efficiency, crane demand & daily charter OPEX
    - S_scarcity: Berth compatibility tightness (deep draft / large LOA)
    """
    cargo_val = getattr(vessel, "cargo_value_usd", 15_000_000.0)
    holding_cost_h = getattr(vessel, "holding_cost_per_hour_usd", 800.0)
    cargo_type = getattr(vessel, "cargo_type", "Standard Containerized")
    demurrage_rate_h = getattr(vessel, "demurrage_rate_per_hour_usd", 1000.0)
    laycan_end_h = getattr(vessel, "laycan_end_h", vessel.arrival_time + 18.0)
    charter_daily = getattr(vessel, "vessel_daily_charter_usd", 25_000.0)
    charter_hourly = charter_daily / 24.0

    reasons = []

    # 1. Cargo Score (Weight: 35%)
    # Scaled against typical shipping values ($5M to $75M) and holding rates ($200 to $3,500/hr)
    val_norm = min(100.0, max(0.0, (cargo_val - 2_000_000.0) / (70_000_000.0 - 2_000_000.0) * 100.0))
    holding_norm = min(100.0, max(0.0, (holding_cost_h - 200.0) / (3000.0 - 200.0) * 100.0))
    cargo_score = round(0.5 * val_norm + 0.5 * holding_norm, 1)

    if cargo_score >= 70.0:
        reasons.append(f"High-value cargo ({cargo_type}, ~${cargo_val/1e6:.1f}M valuation, holding cost ${holding_cost_h:.0f}/h)")
    elif cargo_score >= 40.0:
        reasons.append(f"Standard commercial cargo ({cargo_type}, ~${cargo_val/1e6:.1f}M)")

    # 2. Demurrage & Laycan Urgency Score (Weight: 30%)
    # Closeness of arrival to laycan cancellation window
    laytime_allowance = max(4.0, laycan_end_h - vessel.arrival_time)
    urgency_norm = min(100.0, max(0.0, (36.0 - laytime_allowance) / 30.0 * 100.0))
    demurrage_norm = min(100.0, max(0.0, (demurrage_rate_h - 600.0) / (2200.0 - 600.0) * 100.0))
    demurrage_score = round(0.6 * demurrage_norm + 0.4 * urgency_norm, 1)

    if demurrage_rate_h >= 1400.0:
        reasons.append(f"High demurrage penalty (${demurrage_rate_h:.0f}/h beyond laycan window T+{laycan_end_h:.1f}h)")
    if laytime_allowance <= 14.0:
        reasons.append(f"Tight contractual laycan window ({laytime_allowance:.1f}h tolerance)")

    # 3. Resource & Turnaround Intensity Score (Weight: 20%)
    # High charter rate ($15k - $45k/day) + crane demand
    charter_norm = min(100.0, max(0.0, (charter_hourly - 700.0) / (2000.0 - 700.0) * 100.0))
    crane_norm = min(100.0, max(0.0, (vessel.required_cranes - 1) / 2.0 * 100.0))
    service_norm = min(100.0, max(0.0, (24.0 - vessel.service_duration_h) / 18.0 * 100.0))  # Faster turnaround = higher priority to clear
    resource_score = round(0.5 * charter_norm + 0.3 * crane_norm + 0.2 * service_norm, 1)

    if charter_daily >= 30000.0:
        reasons.append(f"High vessel charter OPEX (${charter_daily:,.0f}/day)")
    if vessel.required_cranes >= 3:
        reasons.append(f"Heavy crane demand ({vessel.required_cranes} STS cranes required)")

    # 4. Physical Berth Scarcity & Draft/Length Constraints (Weight: 15%)
    scarcity_score = 50.0
    if berths:
        target_port = getattr(vessel, "preferred_port", None) or getattr(vessel, "destination_port", None)
        port_berths = [b for b in berths if getattr(b, "port_id", None) == target_port] or berths
        compatible = [
            b for b in port_berths
            if vessel.vessel_length_m <= getattr(b, "max_vessel_length_m", 400.0)
            and vessel.vessel_draft_m <= getattr(b, "max_vessel_draft_m", 20.0)
        ]
        if port_berths:
            comp_ratio = len(compatible) / len(port_berths)
            # Fewer compatible berths = higher scarcity score
            scarcity_score = round((1.0 - comp_ratio) * 100.0, 1)
            if comp_ratio <= 0.35:
                reasons.append(f"Severe physical berth constraints (only {len(compatible)}/{len(port_berths)} berths fit draft {vessel.vessel_draft_m}m / LOA {vessel.vessel_length_m}m)")
            elif comp_ratio <= 0.60:
                reasons.append(f"Restricted berth fit ({len(compatible)}/{len(port_berths)} berths compatible)")

    # Composite Score calculation
    composite = round(
        0.35 * cargo_score +
        0.30 * demurrage_score +
        0.20 * resource_score +
        0.15 * scarcity_score,
        1
    )

    # Classification
    if composite >= 70.0:
        priority_level = 1
    elif composite >= 40.0:
        priority_level = 2
    else:
        priority_level = 3

    if not reasons:
        reasons.append("Standard flexible cargo and operational profile")

    return PriorityBreakdown(
        cargo_score=cargo_score,
        demurrage_score=demurrage_score,
        resource_score=resource_score,
        scarcity_score=scarcity_score,
        composite_score=composite,
        priority_level=priority_level,
        reasons=reasons,
    )


def apply_priority_scoring(
    vessels: List[Any],
    berths: Optional[List[Any]] = None,
    cranes: Optional[List[Any]] = None,
    planning_horizon_hours: float = 72.0,
) -> List[Any]:
    """Calculate and assign multi-factor priority scores to a list of vessels."""
    for v in vessels:
        pb = evaluate_vessel_priority(v, berths, cranes, planning_horizon_hours)
        v.priority_score = pb.composite_score
        v.priority = pb.priority_level
        v.priority_reasons = pb.reasons
    return vessels
