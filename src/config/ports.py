"""Port definitions and regional port clusters for PortPilot AI."""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class PortSpec:
    port_id: str
    port_name: str
    num_berths: int
    num_cranes: int
    max_vessel_length_m: float
    max_vessel_draft_m: float
    avg_service_time_h: float
    reliability_score: float  # 0-1
    handling_cost_per_teu: float
    diversion_cost_per_teu: float
    lat: float = 18.95
    lon: float = 72.85


# Regional Port Clusters
PORT_CLUSTERS: Dict[str, Dict[str, Any]] = {
    "india": {
        "cluster_name": "🇮🇳 Indian Major Ports (JNPT / Mundra / Cochin)",
        "ports": [
            PortSpec("P1", "Port of JNPT (Mumbai)", 4, 6, 370.0, 15.0, 16.0, 0.88, 42.0, 60.0, 18.95, 72.95),
            PortSpec("P2", "Port of Mundra (Gujarat)", 5, 8, 400.0, 16.5, 14.0, 0.92, 38.0, 55.0, 22.74, 69.70),
            PortSpec("P3", "Port of Cochin (Kerala)", 3, 4, 320.0, 13.5, 19.0, 0.80, 45.0, 65.0, 9.96, 76.26),
        ],
    },
    "europe": {
        "cluster_name": "🇪🇺 European Mega-Hubs (Rotterdam / Antwerp / Hamburg)",
        "ports": [
            PortSpec("P1", "Port of Rotterdam (Netherlands)", 5, 8, 400.0, 17.0, 14.0, 0.94, 50.0, 75.0, 51.92, 4.48),
            PortSpec("P2", "Port of Antwerp (Belgium)", 4, 6, 380.0, 15.5, 16.0, 0.89, 48.0, 70.0, 51.22, 4.40),
            PortSpec("P3", "Port of Hamburg (Germany)", 3, 5, 350.0, 14.5, 18.0, 0.86, 46.0, 68.0, 53.55, 9.99),
        ],
    },
    "us_west": {
        "cluster_name": "🇺🇸 US West Coast Corridor (LA / Long Beach / Oakland)",
        "ports": [
            PortSpec("P1", "Port of Los Angeles (California)", 4, 7, 400.0, 16.0, 15.0, 0.87, 55.0, 80.0, 33.74, -118.27),
            PortSpec("P2", "Port of Long Beach (California)", 4, 6, 390.0, 15.5, 16.0, 0.88, 52.0, 78.0, 33.75, -118.22),
            PortSpec("P3", "Port of Oakland (San Francisco Bay)", 3, 4, 340.0, 14.0, 18.0, 0.82, 48.0, 72.0, 37.80, -122.27),
        ],
    },
    "southeast_asia": {
        "cluster_name": "🇸🇬 Southeast Asia Straits (Singapore / Port Klang / PTP)",
        "ports": [
            PortSpec("P1", "Port of Singapore (PSA)", 5, 8, 400.0, 17.5, 13.0, 0.95, 45.0, 65.0, 1.29, 103.85),
            PortSpec("P2", "Port Klang (Malaysia)", 4, 6, 370.0, 15.0, 16.0, 0.86, 38.0, 55.0, 3.00, 101.40),
            PortSpec("P3", "Port of Tanjung Pelepas (PTP)", 4, 6, 380.0, 16.0, 15.0, 0.89, 40.0, 58.0, 1.36, 103.55),
        ],
    },
    "global_demo": {
        "cluster_name": "🌐 Global Demo Ports (Alpha / Beta / Gamma)",
        "ports": [
            PortSpec("P1", "Port Alpha", 3, 5, 350.0, 12.0, 18.0, 0.85, 45.0, 65.0, 18.95, 72.85),
            PortSpec("P2", "Port Beta", 2, 4, 300.0, 10.0, 22.0, 0.70, 38.0, 55.0, 1.29, 103.85),
            PortSpec("P3", "Port Gamma", 4, 6, 400.0, 14.0, 16.0, 0.90, 50.0, 75.0, 51.92, 4.48),
        ],
    },
}

DEFAULT_PORTS = PORT_CLUSTERS["india"]["ports"]


def get_ports_for_cluster(cluster_key: str = "india") -> List[PortSpec]:
    """Return port list for the chosen regional cluster."""
    cluster = PORT_CLUSTERS.get(cluster_key, PORT_CLUSTERS["india"])
    return cluster["ports"]


def get_coordinates_for_cluster(cluster_key: str = "india") -> Dict[str, Dict[str, Any]]:
    """Return port coordinates mapping for live Open-Meteo weather API."""
    ports = get_ports_for_cluster(cluster_key)
    return {
        p.port_id: {"name": p.port_name, "lat": p.lat, "lon": p.lon}
        for p in ports
    }