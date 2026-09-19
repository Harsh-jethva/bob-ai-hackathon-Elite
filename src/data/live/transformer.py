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
        vid = f"V-LIVE-{idx+1:03d}"
        # In container shipping, a port call exchange is ~5-15% of total vessel capacity (400-2,000 TEU)
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
