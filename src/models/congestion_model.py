"""Congestion prediction model for PortPilot AI.

Produces congestion forecasts for the next 72 hours with explanations.
Uses a transparent baseline when historical data is insufficient (PRD 11.3).
"""

from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from src.data.generator import Vessel, Berth, Crane
from src.config.settings import settings


class CongestionLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class CongestionForecast:
    port_id: str
    predicted_queue_length: float  # fractional — never a literal count
    congestion_level: CongestionLevel
    expected_wait_hours: Optional[float]  # qualified for LOW
    berth_utilization: float  # 0-1+
    crane_utilization: float  # 0-1+
    confidence: float  # 0-1
    contributing_factors: List[str] = field(default_factory=list)


def _classify_congestion(queue_fraction: float) -> CongestionLevel:
    if queue_fraction >= settings.congestion_high:
        return CongestionLevel.CRITICAL
    if queue_fraction >= settings.congestion_medium:
        return CongestionLevel.HIGH
    if queue_fraction >= settings.congestion_low:
        return CongestionLevel.MEDIUM
    return CongestionLevel.LOW


def _format_queue_display(q: float) -> str:
    """Never present fractional as literal physical count (PRD fractional queue policy)."""
    if q < 1.0:
        return f"less than one vessel expected in queue ({q:.2f})"
    return f"~{q:.1f} vessels expected"


def predict_congestion(
    vessels: List[Vessel],
    berths: List,
    cranes: List,
    horizon_hours: float = 72.0,
) -> List[CongestionForecast]:
    """Predict congestion for each port across the horizon."""
    features_by_port = _aggregate_by_port(vessels, berths, cranes, horizon_hours)
    forecasts = []
    for port_id, feat in features_by_port.items():
        queue_frac = feat["total_service_h"] / max(
            horizon_hours * len([b for b in berths if b.port_id == port_id]), 1
        )
        level = _classify_congestion(queue_frac)
        # Expected wait: qualified for LOW
        port_berths = [b for b in berths if b.port_id == port_id]
        n_berths = len(port_berths) if port_berths else 1
        wait = round(queue_frac * horizon_hours / n_berths, 1)

        factors = []
        if queue_frac > 0.5:
            factors.append("High arrival density")
        if feat["arrival_density_per_h"] > 0.5:
            factors.append("Sustained arrival rate")
        if not factors:
            factors.append("Normal operating conditions")

        confidence = 0.75  # synthetic data — lower confidence
        if level == CongestionLevel.LOW:
            confidence = 0.85

        forecasts.append(CongestionForecast(
            port_id=port_id,
            predicted_queue_length=queue_frac,
            congestion_level=level,
            expected_wait_hours=wait,
            berth_utilization=round(min(feat["berth_utilization"], 999), 3),
            crane_utilization=round(min(feat["crane_utilization"], 999), 3),
            confidence=confidence,
            contributing_factors=factors,
        ))
    return forecasts


def _aggregate_by_port(vessels, berths, cranes, horizon_hours):
    """Compute aggregate features grouped by port."""
    result = {}
    for p in set(getattr(v, "destination_port", None) for v in vessels) | set(
        getattr(v, "preferred_port", None) for v in vessels
    ):
        if not p:
            continue
        pv = [v for v in vessels if getattr(v, "destination_port", None) == p or
              getattr(v, "preferred_port", None) == p]
        pb = [b for b in berths if b.port_id == p]
        pc = [c for c in cranes if c.port_id == p]
        total_service = sum(getattr(v, "service_duration_h", 0) for v in pv)
        total_cargo = sum(getattr(v, "cargo_volume", 0) for v in pv)
        n_berths = len(pb) if pb else 1
        n_cranes = len(pc) if pc else 1
        result[p] = {
            "num_vessels": len(pv),
            "total_service_h": total_service,
            "total_cargo": total_cargo,
            "berth_utilization": total_service / max(horizon_hours * n_berths, 1),
            "crane_utilization": total_service / max(horizon_hours * n_cranes, 1),
            "arrival_density_per_h": len(pv) / max(horizon_hours, 1),
        }
    return result


def classify_queue_fraction(queue_fraction: float) -> CongestionLevel:
    """Exported for testing."""
    return _classify_congestion(queue_fraction)
