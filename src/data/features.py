"""Data validation and feature engineering for PortPilot AI."""

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ValidationWarning:
    field: str
    message: str
    severity: str  # error | warning | info


def validate_vessels(vessels) -> Tuple[bool, List[ValidationWarning]]:
    """Validate vessel records. Returns (is_valid, warnings)."""
    warnings: List[ValidationWarning] = []
    required = [
        "vessel_id", "vessel_name", "arrival_time", "service_duration_h",
        "cargo_volume", "priority", "vessel_length_m", "vessel_draft_m",
        "required_cranes", "origin_port", "destination_port", "preferred_port",
        "status",
    ]
    seen_ids = set()
    for i, v in enumerate(vessels):
        vid = getattr(v, "vessel_id", None) or (v.get("vessel_id") if isinstance(v, dict) else f"row-{i}")
        if vid in seen_ids:
            warnings.append(ValidationWarning("vessel_id", f"Duplicate vessel_id: {vid}", "error"))
        seen_ids.add(vid)

        for field_name in required:
            val = getattr(v, field_name, None) if not isinstance(v, dict) else v.get(field_name)
            if val is None:
                warnings.append(ValidationWarning(field_name, f"Missing value for {vid}.{field_name}", "warning"))

        # Check timestamps
        arr = getattr(v, "arrival_time", None)
        if arr is not None and arr < 0:
            warnings.append(ValidationWarning("arrival_time", f"Negative arrival_time for {vid}", "error"))

        # Check durations
        dur = getattr(v, "service_duration_h", None)
        if dur is not None and dur <= 0:
            warnings.append(ValidationWarning("service_duration_h", f"Non-positive duration for {vid}", "error"))

        # Check resource counts
        cr = getattr(v, "required_cranes", None)
        if cr is not None and cr < 1:
            warnings.append(ValidationWarning("required_cranes", f"Impossible crane count for {vid}", "error"))

    is_valid = not any(w.severity == "error" for w in warnings)
    return is_valid, warnings


def validate_ports(ports) -> Tuple[bool, List[ValidationWarning]]:
    warnings: List[ValidationWarning] = []
    seen = set()
    for p in ports:
        pid = getattr(p, "port_id", None)
        if pid in seen:
            warnings.append(ValidationWarning("port_id", f"Duplicate port_id: {pid}", "error"))
        seen.add(pid)
        for field in ["port_name", "num_berths", "num_cranes", "max_vessel_length_m",
                       "max_vessel_draft_m", "avg_service_time_h", "reliability_score"]:
            val = getattr(p, field, None)
            if val is None:
                warnings.append(ValidationWarning(field, f"Missing {field} for {pid}", "warning"))
    is_valid = not any(w.severity == "error" for w in warnings)
    return is_valid, warnings


def build_congestion_features(
    vessels, berths, cranes, horizon_hours: float = 72.0
) -> Dict[str, Any]:
    """Compute aggregate features used for congestion prediction."""
    total_berth_capacity = len(berths) * horizon_hours
    total_crane_capacity = len(cranes) * horizon_hours
    total_service_h = sum(getattr(v, "service_duration_h", 0) for v in vessels)
    total_cargo = sum(getattr(v, "cargo_volume", 0) for v in vessels)
    arrival_density = len(vessels) / max(horizon_hours, 1)

    return {
        "num_vessels": len(vessels),
        "total_berth_capacity": total_berth_capacity,
        "total_crane_capacity": total_crane_capacity,
        "total_service_h": total_service_h,
        "total_cargo_teu": total_cargo,
        "arrival_density_per_h": round(arrival_density, 3),
        "berth_utilization": min(total_service_h / max(total_berth_capacity, 1), 999),
        "crane_utilization": min(total_service_h / max(total_crane_capacity, 1), 999),
    }
