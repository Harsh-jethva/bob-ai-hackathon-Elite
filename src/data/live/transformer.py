"""Data Transformer and Normalizer for Live Ingestion Streams.

Transforms raw AIS, TOS, and Weather telemetry into validated
PortPilot AI core dataclasses (Vessel, Berth, Crane, PortSpec).
"""

from typing import List, Dict, Any, Tuple
from src.data.generator import Vessel, Berth, Crane, PortSpec
from src.data.live.ais_connector import LiveAISVessel
from src.data.live.weather_connector import PortWeather


def transform_live_vessels(
    ais_vessels: List[LiveAISVessel],
    weather_by_port: Dict[str, PortWeather],
) -> List[Vessel]:
    """Convert LiveAISVessel stream into normalized Vessel objects with weather adjustments."""
    normalized: List[Vessel] = []

    for idx, av in enumerate(ais_vessels):
        vid = f"V-{av.imo[-4:]}"
        # Compute baseline service duration based on cargo and crane productivity
        base_dur = max(6.0, round(av.cargo_teu_estimate / (av.required_cranes * 35.0), 1))

        # Check weather adjustment at destination
        dest_weather = weather_by_port.get(av.destination_port)
        weather_mult = 1.0
        if dest_weather:
            if dest_weather.crane_shutoff_risk:
                weather_mult = 1.4  # Wind delays
            elif dest_weather.pilotage_delay_risk:
                weather_mult = 1.2

        service_dur = round(base_dur * weather_mult, 2)

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
        ))

    normalized.sort(key=lambda v: v.arrival_time)
    return normalized
