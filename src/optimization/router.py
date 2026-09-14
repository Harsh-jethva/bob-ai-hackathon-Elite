"""Alternative-port recommendation engine (PRD 11.8).

Uses transparent, configurable weighted scoring.
Never invents ports, capacities, distances, costs, or live conditions.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from src.data.generator import Vessel, PortSpec
from src.models.congestion_model import CongestionForecast
from src.config.settings import settings


@dataclass
class AlternativePortRecommendation:
    vessel_id: str
    recommended_port_id: str
    recommended_port_name: str
    score: float
    components: Dict[str, float]
    rationale: str
    advantages: List[str]
    disadvantages: List[str]
    confidence: float


def score_alternative_port(
    vessel: Vessel,
    candidate: PortSpec,
    congestion_forecasts: List[CongestionForecast],
) -> Dict[str, float]:
    """Score a candidate port for a vessel using configurable weights."""
    weights = settings.alt_port_weights

    # Expected delay component (lower is better → invert)
    forecast = next((f for f in congestion_forecasts
                     if f.port_id == candidate.port_id), None)
    congestion_q = forecast.predicted_queue_length if forecast else 0.0
    expected_delay_score = max(0, 1.0 - congestion_q)

    # Feasibility (vessel compatibility)
    feasible = (vessel.vessel_length_m <= candidate.max_vessel_length_m
                and vessel.vessel_draft_m <= candidate.max_vessel_draft_m)
    feasibility_score = 1.0 if feasible else 0.0

    # Diversion cost (lower cost = higher score)
    max_cost = max(candidate.handling_cost_per_teu, 1.0)
    diversion_score = max(0, 1.0 - (candidate.diversion_cost_per_teu
                                     / max_cost * 0.5))

    # Congestion risk (lower queue = better)
    congestion_score = max(0, 1.0 - congestion_q)

    # Reliability
    reliability_score = candidate.reliability_score

    components = {
        "expected_delay": expected_delay_score,
        "feasibility": feasibility_score,
        "diversion_cost": diversion_score,
        "congestion_risk": congestion_score,
        "reliability": reliability_score,
    }

    total = sum(components[k] * weights.get(k, 0) for k in weights)
    return {"score": round(total, 4), **components}


def recommend_alternative_ports(
    vessel: Vessel,
    all_ports: List[PortSpec],
    forecasts: List[CongestionForecast],
    top_n: int = 2,
) -> List[AlternativePortRecommendation]:
    """Recommend alternative ports for a vessel.

    Excludes incompatible ports outright (PRD 11.8).
    """
    # Filter incompatible
    candidates = [
        p for p in all_ports
        if p.port_id != vessel.preferred_port
        and vessel.vessel_length_m <= p.max_vessel_length_m
        and vessel.vessel_draft_m <= p.max_vessel_draft_m
    ]
    if not candidates:
        return []

    scored = []
    for p in candidates:
        result = score_alternative_port(vessel, p, forecasts)
        advantages = []
        disadvantages = []
        if result["feasibility"] >= 1.0:
            advantages.append("Vessel physically compatible")
        else:
            disadvantages.append("Vessel may not fit berth")
        if result["congestion_risk"] > 0.5:
            advantages.append("Lower congestion risk")
        if result["diversion_cost"] > 0.5:
            disadvantages.append("Higher diversion cost")
        if result["reliability"] > 0.8:
            advantages.append("High reliability score")

        rationale = (f"Score {result['score']:.3f} based on "
                      f"delay={result['expected_delay']:.2f}, "
                      f"feasibility={result['feasibility']:.2f}")

        scored.append(AlternativePortRecommendation(
            vessel_id=vessel.vessel_id,
            recommended_port_id=p.port_id,
            recommended_port_name=p.port_name,
            score=result["score"],
            components=result,
            rationale=rationale,
            advantages=advantages,
            disadvantages=disadvantages,
            confidence=round(result["score"], 2),
        ))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_n]
