"""Data Transformer and Normalizer for Live Ingestion Streams.

Transforms raw AIS, TOS, and Weather telemetry into validated
PortPilot AI core dataclasses (Vessel, Berth, Crane, PortSpec).
"""

from typing import List, Dict, Any, Tuple, Optional
import random
from src.data.generator import Vessel, Berth, Crane, PortSpec
from src.data.live.ais_connector import LiveAISVessel
from src.data.live.weather_connector import PortWeather
from src.optimization.priority_engine import CARGO_PROFILES, apply_priority_scoring


def transform_live_vessels(
    ais_vessels: List[LiveAISVessel],
    weather_by_port: Dict[str, PortWeather],
    berths: Optional[List[Berth]] = None,
    cranes: Optional[List[Crane]] = None,
) -> List[Vessel]:
    """Convert LiveAISVessel stream into normalized Vessel objects with weather adjustments and multi-factor priority."""
    normalized: List[Vessel] = []
    cargo_types = list(CARGO_PROFILES.keys())
    cargo_weights = [0.15, 0.20, 0.20, 0.25, 0.10, 0.10]
    rng = random.Random(42)

    for idx, av in enumerate(ais_vessels):
        vid = f"V-LIVE-{idx+1:03d}"
        port_call_teu = min(av.cargo_teu_estimate, max(450.0, av.cargo_teu_estimate * 0.08))
        gross_crane_speed = max(1, av.required_cranes) * 28.0  # ~28 container moves per crane/hr
        base_dur = min(24.0, max(6.0, round(port_call_teu / gross_crane_speed, 1)))

        # Check weather adjustment at destination
        dest_weather = weather_by_port.get(av.destination_port)
        weather_mult = 1.0
        if dest_weather:
            if dest_weather.crane_shutoff_risk:
                weather_mult = 1.4  # Wind delays
            elif dest_weather.pilotage_delay_risk:
                weather_mult = 1.2

        service_dur = round(base_dur * weather_mult, 2)

        # Dynamic cargo profile assignment
        ctype = rng.choices(cargo_types, weights=cargo_weights)[0]
        cprof = CARGO_PROFILES[ctype]
        cval = round(av.cargo_teu_estimate * cprof["unit_value_per_teu"] * rng.uniform(0.85, 1.15), 0)
        holding_h = round(cval * cprof["holding_rate_hourly_pct"], 0)
        laycan_window = rng.uniform(8.0, 26.0)
        laycan_end = round(av.eta_relative_hours + laycan_window, 1)
        demurrage_h = round(rng.uniform(800, 1600) * cprof["demurrage_multiplier"], 0)
        charter_day = round(rng.uniform(20000, 40000), 0)

        normalized.append(Vessel(
            vessel_id=vid,
            vessel_name=av.vessel_name,
            arrival_time=av.eta_relative_hours,
            estimated_arrival_time=av.eta_relative_hours,
            service_duration_h=service_dur,
            cargo_volume=av.cargo_teu_estimate,
            priority=av.priority,
            vessel_length_m=av.length_m,
            vessel_draft_m=av.draft_m,
            required_cranes=av.required_cranes,
            origin_port=av.origin_port,
            destination_port=av.destination_port,
            preferred_port=av.preferred_port,
            status="scheduled",
            cargo_type=ctype,
            cargo_value_usd=cval,
            holding_cost_per_hour_usd=holding_h,
            laycan_end_h=laycan_end,
            demurrage_rate_per_hour_usd=demurrage_h,
            vessel_daily_charter_usd=charter_day,
            priority_score=50.0,
            priority_reasons=[],
        ))

    # Apply multi-factor priority scoring
    apply_priority_scoring(normalized, berths, cranes)

    normalized.sort(key=lambda v: v.arrival_time)
    return normalized
