"""Port definitions and regional port clusters for PortPilot AI."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


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
    # Port-Specific Penalties, Tariffs & Harbor Dues
    port_dues_fixed_usd: float = 12000.0          # Fixed Port Entry & Harbor Navigation Dues
    pilotage_tug_fee_usd: float = 5000.0          # Mandatory Pilotage & Tugboat Assist Fee
    diversion_penalty_fixed_usd: float = 10000.0  # Customs / Manifest Alteration / Rerouting Penalty
    crane_hourly_rate_usd: float = 350.0           # STS Quay Crane Hourly Tariff ($/crane-hour)
    congestion_surcharge_usd: float = 6000.0      # Congestion surcharge if port wait > 6h


@dataclass
class OccupiedBerth:
    """Represents a berth already in use at planning start (T+0)."""
    berth_id: str
    vessel_name: str        # Name of the ship currently docked
    free_at_hours: float    # When the berth becomes available (hours from T+0)
    cargo_type: str = "Container"


@dataclass
class PortLiveState:
    """Realistic pre-existing occupancy state for a port at planning start."""
    occupied_berths: List[OccupiedBerth] = field(default_factory=list)
    crane_busy_until: Dict[str, float] = field(default_factory=dict)  # crane_id -> free_at_hours
    berth_occupancy_pct: float = 0.0  # e.g. 0.5 = 50% occupied

    def get_occupied_berth_ids(self) -> List[str]:
        return [ob.berth_id for ob in self.occupied_berths]

    def get_free_berths_count(self, total_berths: int) -> int:
        return total_berths - len(self.occupied_berths)

    def get_berth_free_time(self, berth_id: str) -> float:
        """Return when a specific berth becomes free (0.0 if already free)."""
        for ob in self.occupied_berths:
            if ob.berth_id == berth_id:
                return ob.free_at_hours
        return 0.0


# ---------------------------------------------------------------------------
# PORT_LIVE_STATES: realistic pre-existing occupancy for every cluster/port
# Keys: cluster_key -> port_id -> PortLiveState
# ---------------------------------------------------------------------------
PORT_LIVE_STATES: Dict[str, Dict[str, PortLiveState]] = {
    "india": {
        "P1": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P1-1", "MV Chambal Express",  free_at_hours=4.5,  cargo_type="Container"),
                OccupiedBerth("B-P1-2", "MV Mumbai Trader",    free_at_hours=8.0,  cargo_type="Bulk"),
            ],
            crane_busy_until={
                "C-P1-1": 4.5,
                "C-P1-2": 8.0,
                "C-P1-3": 2.0,
                "C-P1-4": 0.0,
                "C-P1-5": 0.0,
                "C-P1-6": 0.0,
            },
            berth_occupancy_pct=0.50,   # 2/4 berths occupied
        ),
        "P2": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P2-1", "MV Gateway Trader",   free_at_hours=5.0,  cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P2-1": 5.0,
                "C-P2-2": 0.0,
                "C-P2-3": 0.0,
                "C-P2-4": 0.0,
            },
            berth_occupancy_pct=0.33,   # 1/3 berths occupied
        ),
        "P3": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P3-1", "MV Surat Merchant",   free_at_hours=6.0,  cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P3-1": 6.0,
                "C-P3-2": 2.5,
                "C-P3-3": 0.0,
                "C-P3-4": 0.0,
                "C-P3-5": 0.0,
            },
            berth_occupancy_pct=0.33,   # 1/3 berths occupied
        ),
        "P4": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P4-1", "MV Gujarat Star",     free_at_hours=3.0,  cargo_type="Container"),
                OccupiedBerth("B-P4-2", "MV Mundra Pioneer",   free_at_hours=11.5, cargo_type="Liquid Bulk"),
            ],
            crane_busy_until={
                "C-P4-1": 3.0,
                "C-P4-2": 11.5,
                "C-P4-3": 1.5,
                "C-P4-4": 0.0,
                "C-P4-5": 0.0,
                "C-P4-6": 0.0,
                "C-P4-7": 0.0,
                "C-P4-8": 0.0,
            },
            berth_occupancy_pct=0.40,   # 2/5 berths occupied
        ),
        "P5": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P5-1", "MV Kutch Logistics",  free_at_hours=4.0,  cargo_type="Bulk"),
                OccupiedBerth("B-P5-2", "MV Gulf Carrier",     free_at_hours=9.0,  cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P5-1": 4.0,
                "C-P5-2": 9.0,
                "C-P5-3": 0.0,
                "C-P5-4": 0.0,
                "C-P5-5": 0.0,
                "C-P5-6": 0.0,
            },
            berth_occupancy_pct=0.50,   # 2/4 berths occupied
        ),
    },

    "europe": {
        "P1": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P1-1", "MSC Maxima",          free_at_hours=5.0,  cargo_type="Container"),
                OccupiedBerth("B-P1-2", "Ever Govern",         free_at_hours=9.5,  cargo_type="Container"),
                OccupiedBerth("B-P1-3", "Rotterdam Bulk One",  free_at_hours=2.5,  cargo_type="Bulk"),
            ],
            crane_busy_until={
                "C-P1-1": 5.0,  "C-P1-2": 9.5,  "C-P1-3": 2.5,
                "C-P1-4": 0.0,  "C-P1-5": 0.0,  "C-P1-6": 0.0,
                "C-P1-7": 0.0,  "C-P1-8": 0.0,
            },
            berth_occupancy_pct=0.60,   # 3/5 berths occupied
        ),
        "P2": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P2-1", "CMA CGM Antares",     free_at_hours=7.0,  cargo_type="Container"),
                OccupiedBerth("B-P2-2", "Antwerp Logistics I",  free_at_hours=3.0,  cargo_type="General"),
            ],
            crane_busy_until={
                "C-P2-1": 7.0,  "C-P2-2": 3.0,
                "C-P2-3": 0.0,  "C-P2-4": 0.0,
                "C-P2-5": 0.0,  "C-P2-6": 0.0,
            },
            berth_occupancy_pct=0.50,   # 2/4 berths occupied
        ),
        "P3": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P3-1", "Hamburg Express",     free_at_hours=12.0, cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P3-1": 12.0, "C-P3-2": 4.0,
                "C-P3-3": 0.0,  "C-P3-4": 0.0,  "C-P3-5": 0.0,
            },
            berth_occupancy_pct=0.33,   # 1/3 berths occupied
        ),
    },

    "us_west": {
        "P1": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P1-1", "Yang Ming Accord",    free_at_hours=6.0,  cargo_type="Container"),
                OccupiedBerth("B-P1-2", "ONE Collaboration",   free_at_hours=10.0, cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P1-1": 6.0,  "C-P1-2": 10.0, "C-P1-3": 3.0,
                "C-P1-4": 0.0,  "C-P1-5": 0.0,
                "C-P1-6": 0.0,  "C-P1-7": 0.0,
            },
            berth_occupancy_pct=0.50,   # 2/4 berths occupied
        ),
        "P2": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P2-1", "COSCO Shipping Mars", free_at_hours=4.0,  cargo_type="Container"),
                OccupiedBerth("B-P2-2", "LB Pacific Carrier",  free_at_hours=8.5,  cargo_type="Bulk"),
            ],
            crane_busy_until={
                "C-P2-1": 4.0,  "C-P2-2": 8.5,
                "C-P2-3": 0.0,  "C-P2-4": 0.0,
                "C-P2-5": 0.0,  "C-P2-6": 0.0,
            },
            berth_occupancy_pct=0.50,   # 2/4 berths occupied
        ),
        "P3": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P3-1", "Oakland Bay Freighter", free_at_hours=5.5, cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P3-1": 5.5,  "C-P3-2": 2.0,
                "C-P3-3": 0.0,  "C-P3-4": 0.0,
            },
            berth_occupancy_pct=0.33,   # 1/3 berths occupied
        ),
    },

    "southeast_asia": {
        "P1": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P1-1", "Evergreen Efficiency", free_at_hours=3.0,  cargo_type="Container"),
                OccupiedBerth("B-P1-2", "PSA Lion City",        free_at_hours=6.5,  cargo_type="Container"),
                OccupiedBerth("B-P1-3", "APL Singapore",        free_at_hours=11.0, cargo_type="Container"),
                OccupiedBerth("B-P1-4", "Maersk Sentosa",       free_at_hours=1.5,  cargo_type="Tanker"),
            ],
            crane_busy_until={
                "C-P1-1": 3.0,  "C-P1-2": 6.5,  "C-P1-3": 11.0,
                "C-P1-4": 1.5,  "C-P1-5": 0.0,
                "C-P1-6": 0.0,  "C-P1-7": 0.0,  "C-P1-8": 0.0,
            },
            berth_occupancy_pct=0.80,   # 4/5 berths occupied
        ),
        "P2": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P2-1", "Klang Valley Star",    free_at_hours=7.0,  cargo_type="Container"),
                OccupiedBerth("B-P2-2", "Malaysia Merchant",    free_at_hours=3.5,  cargo_type="Bulk"),
            ],
            crane_busy_until={
                "C-P2-1": 7.0,  "C-P2-2": 3.5,
                "C-P2-3": 0.0,  "C-P2-4": 0.0,
                "C-P2-5": 0.0,  "C-P2-6": 0.0,
            },
            berth_occupancy_pct=0.50,   # 2/4 berths occupied
        ),
        "P3": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P3-1", "PTP Throughput I",    free_at_hours=5.0,  cargo_type="Container"),
                OccupiedBerth("B-P3-2", "Straits Connector",   free_at_hours=9.0,  cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P3-1": 5.0,  "C-P3-2": 9.0,
                "C-P3-3": 0.0,  "C-P3-4": 0.0,
                "C-P3-5": 0.0,  "C-P3-6": 0.0,
            },
            berth_occupancy_pct=0.50,   # 2/4 berths occupied
        ),
    },

    "global_demo": {
        "P1": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P1-1", "Alpha Pioneer",       free_at_hours=5.0,  cargo_type="Container"),
            ],
            crane_busy_until={
                "C-P1-1": 5.0,  "C-P1-2": 2.0,
                "C-P1-3": 0.0,  "C-P1-4": 0.0,  "C-P1-5": 0.0,
            },
            berth_occupancy_pct=0.33,
        ),
        "P2": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P2-1", "Beta Carrier",        free_at_hours=6.0,  cargo_type="Bulk"),
            ],
            crane_busy_until={
                "C-P2-1": 6.0,  "C-P2-2": 1.5,
                "C-P2-3": 0.0,  "C-P2-4": 0.0,
            },
            berth_occupancy_pct=0.50,
        ),
        "P3": PortLiveState(
            occupied_berths=[
                OccupiedBerth("B-P3-1", "Gamma Express",       free_at_hours=4.0,  cargo_type="Container"),
                OccupiedBerth("B-P3-2", "Gamma Bulk Hauler",   free_at_hours=9.0,  cargo_type="Bulk"),
            ],
            crane_busy_until={
                "C-P3-1": 4.0,  "C-P3-2": 9.0,
                "C-P3-3": 0.0,  "C-P3-4": 0.0,
                "C-P3-5": 0.0,  "C-P3-6": 0.0,
            },
            berth_occupancy_pct=0.50,
        ),
    },
}


# Regional Port Clusters
PORT_CLUSTERS: Dict[str, Dict[str, Any]] = {
    "india": {
        "cluster_name": "🇮🇳 West Coast India Corridor (Mumbai & Gujarat Hubs)",
        "ports": [
            PortSpec("P1", "Port of JNPT (Nhava Sheva / Mumbai)", 4, 6, 370.0, 15.0, 16.0, 0.88, 42.0, 60.0, 18.95, 72.95,
                     port_dues_fixed_usd=16500.0, pilotage_tug_fee_usd=6200.0, diversion_penalty_fixed_usd=14000.0, crane_hourly_rate_usd=380.0, congestion_surcharge_usd=10000.0),
            PortSpec("P2", "Mumbai Port (MbPA Harbor)",           3, 4, 300.0, 12.5, 18.0, 0.84, 39.0, 52.0, 18.93, 72.85,
                     port_dues_fixed_usd=9500.0,  pilotage_tug_fee_usd=4800.0, diversion_penalty_fixed_usd=8500.0,  crane_hourly_rate_usd=330.0, congestion_surcharge_usd=6000.0),
            PortSpec("P3", "Port of Hazira (Surat / Gujarat)",    3, 5, 340.0, 14.0, 15.0, 0.90, 40.0, 56.0, 21.10, 72.63,
                     port_dues_fixed_usd=12000.0, pilotage_tug_fee_usd=5500.0, diversion_penalty_fixed_usd=9500.0,  crane_hourly_rate_usd=350.0, congestion_surcharge_usd=7500.0),
            PortSpec("P4", "Port of Mundra (Kutch / Gujarat)",    5, 8, 400.0, 16.5, 14.0, 0.92, 38.0, 55.0, 22.74, 69.70,
                     port_dues_fixed_usd=18000.0, pilotage_tug_fee_usd=7000.0, diversion_penalty_fixed_usd=12500.0, crane_hourly_rate_usd=390.0, congestion_surcharge_usd=8000.0),
            PortSpec("P5", "Deendayal Port (Kandla / Gujarat)",   4, 6, 360.0, 14.5, 16.0, 0.87, 36.0, 50.0, 23.01, 70.22,
                     port_dues_fixed_usd=10500.0, pilotage_tug_fee_usd=4200.0, diversion_penalty_fixed_usd=7000.0,  crane_hourly_rate_usd=310.0, congestion_surcharge_usd=5000.0),
        ],
    },
    "europe": {
        "cluster_name": "🇪🇺 European Mega-Hubs (Rotterdam / Antwerp / Hamburg)",
        "ports": [
            PortSpec("P1", "Port of Rotterdam (Netherlands)", 5, 8, 400.0, 17.0, 14.0, 0.94, 50.0, 75.0, 51.92, 4.48,
                     port_dues_fixed_usd=26000.0, pilotage_tug_fee_usd=8500.0, diversion_penalty_fixed_usd=22000.0, crane_hourly_rate_usd=450.0, congestion_surcharge_usd=14000.0),
            PortSpec("P2", "Port of Antwerp (Belgium)",       4, 6, 380.0, 15.5, 16.0, 0.89, 48.0, 70.0, 51.22, 4.40,
                     port_dues_fixed_usd=21000.0, pilotage_tug_fee_usd=7200.0, diversion_penalty_fixed_usd=17500.0, crane_hourly_rate_usd=420.0, congestion_surcharge_usd=11000.0),
            PortSpec("P3", "Port of Hamburg (Germany)",       3, 5, 350.0, 14.5, 18.0, 0.86, 46.0, 68.0, 53.55, 9.99,
                     port_dues_fixed_usd=23500.0, pilotage_tug_fee_usd=7800.0, diversion_penalty_fixed_usd=19000.0, crane_hourly_rate_usd=410.0, congestion_surcharge_usd=12500.0),
        ],
    },
    "us_west": {
        "cluster_name": "🇺🇸 US West Coast Corridor (LA / Long Beach / Oakland)",
        "ports": [
            PortSpec("P1", "Port of Los Angeles (California)",    4, 7, 400.0, 16.0, 15.0, 0.87, 55.0, 80.0, 33.74, -118.27,
                     port_dues_fixed_usd=28000.0, pilotage_tug_fee_usd=9000.0, diversion_penalty_fixed_usd=25000.0, crane_hourly_rate_usd=480.0, congestion_surcharge_usd=16000.0),
            PortSpec("P2", "Port of Long Beach (California)",     4, 6, 390.0, 15.5, 16.0, 0.88, 52.0, 78.0, 33.75, -118.22,
                     port_dues_fixed_usd=27000.0, pilotage_tug_fee_usd=8800.0, diversion_penalty_fixed_usd=24000.0, crane_hourly_rate_usd=470.0, congestion_surcharge_usd=15000.0),
            PortSpec("P3", "Port of Oakland (San Francisco Bay)", 3, 4, 340.0, 14.0, 18.0, 0.82, 48.0, 72.0, 37.80, -122.27,
                     port_dues_fixed_usd=18500.0, pilotage_tug_fee_usd=6500.0, diversion_penalty_fixed_usd=16000.0, crane_hourly_rate_usd=400.0, congestion_surcharge_usd=10000.0),
        ],
    },
    "southeast_asia": {
        "cluster_name": "🇸🇬 Southeast Asia Straits (Singapore / Port Klang / PTP)",
        "ports": [
            PortSpec("P1", "Port of Singapore (PSA)",           5, 8, 400.0, 17.5, 13.0, 0.95, 45.0, 65.0,  1.29, 103.85,
                     port_dues_fixed_usd=22000.0, pilotage_tug_fee_usd=7500.0, diversion_penalty_fixed_usd=18000.0, crane_hourly_rate_usd=440.0, congestion_surcharge_usd=12000.0),
            PortSpec("P2", "Port Klang (Malaysia)",             4, 6, 370.0, 15.0, 16.0, 0.86, 38.0, 55.0,  3.00, 101.40,
                     port_dues_fixed_usd=13500.0, pilotage_tug_fee_usd=5000.0, diversion_penalty_fixed_usd=9000.0,  crane_hourly_rate_usd=340.0, congestion_surcharge_usd=6500.0),
            PortSpec("P3", "Port of Tanjung Pelepas (PTP)",    4, 6, 380.0, 16.0, 15.0, 0.89, 40.0, 58.0,  1.36, 103.55,
                     port_dues_fixed_usd=14000.0, pilotage_tug_fee_usd=5200.0, diversion_penalty_fixed_usd=9500.0,  crane_hourly_rate_usd=350.0, congestion_surcharge_usd=7000.0),
        ],
    },
    "global_demo": {
        "cluster_name": "🌐 Global Demo Ports (Alpha / Beta / Gamma)",
        "ports": [
            PortSpec("P1", "Port Alpha", 3, 5, 350.0, 12.0, 18.0, 0.85, 45.0, 65.0, 18.95,  72.85,
                     port_dues_fixed_usd=15000.0, pilotage_tug_fee_usd=5500.0, diversion_penalty_fixed_usd=12000.0, crane_hourly_rate_usd=360.0, congestion_surcharge_usd=8000.0),
            PortSpec("P2", "Port Beta",  2, 4, 300.0, 10.0, 22.0, 0.70, 38.0, 55.0,  1.29, 103.85,
                     port_dues_fixed_usd=11000.0, pilotage_tug_fee_usd=4500.0, diversion_penalty_fixed_usd=8000.0,  crane_hourly_rate_usd=320.0, congestion_surcharge_usd=5000.0),
            PortSpec("P3", "Port Gamma", 4, 6, 400.0, 14.0, 16.0, 0.90, 50.0, 75.0, 51.92,   4.48,
                     port_dues_fixed_usd=20000.0, pilotage_tug_fee_usd=7000.0, diversion_penalty_fixed_usd=16000.0, crane_hourly_rate_usd=420.0, congestion_surcharge_usd=10000.0),
        ],
    },
}

DEFAULT_PORTS = PORT_CLUSTERS["india"]["ports"]


def get_ports_for_cluster(cluster_key: str = "india") -> List[PortSpec]:
    """Return port list for the chosen regional cluster."""
    cluster = PORT_CLUSTERS.get(cluster_key, PORT_CLUSTERS["india"])
    return cluster["ports"]


def get_live_state(cluster_key: str, port_id: str) -> PortLiveState:
    """Return live occupancy state for a specific port in a cluster."""
    cluster_states = PORT_LIVE_STATES.get(cluster_key, PORT_LIVE_STATES["global_demo"])
    return cluster_states.get(port_id, PortLiveState())


def get_coordinates_for_cluster(cluster_key: str = "india") -> Dict[str, Dict[str, Any]]:
    """Return port coordinates mapping for live Open-Meteo weather API."""
    ports = get_ports_for_cluster(cluster_key)
    return {
        p.port_id: {"name": p.port_name, "lat": p.lat, "lon": p.lon}
        for p in ports
    }


# Inter-port distances in nautical miles (1 NM = 1.852 km)
PORT_DISTANCES_NM: Dict[str, Dict[tuple, float]] = {
    "india": {
        ("P1", "P2"): 12.0,   # JNPT <-> Mumbai Port (Harbor sister ports)
        ("P1", "P3"): 135.0,  # JNPT <-> Hazira (South Gujarat)
        ("P1", "P4"): 480.0,  # JNPT <-> Mundra (Gulf of Kutch)
        ("P1", "P5"): 495.0,  # JNPT <-> Kandla (Gulf of Kutch)
        ("P2", "P3"): 130.0,  # Mumbai Port <-> Hazira
        ("P2", "P4"): 475.0,  # Mumbai Port <-> Mundra
        ("P2", "P5"): 490.0,  # Mumbai Port <-> Kandla
        ("P3", "P4"): 280.0,  # Hazira <-> Mundra
        ("P3", "P5"): 250.0,  # Hazira <-> Kandla
        ("P4", "P5"): 35.0,   # Mundra <-> Kandla (Gulf of Kutch sister ports)
    },
    "europe": {
        ("P1", "P2"): 95.0,   # Rotterdam <-> Antwerp
        ("P1", "P3"): 295.0,  # Rotterdam <-> Hamburg
        ("P2", "P3"): 335.0,  # Antwerp <-> Hamburg
    },
    "us_west": {
        ("P1", "P2"): 12.0,   # LA <-> Long Beach (adjacent bay)
        ("P1", "P3"): 365.0,  # LA <-> Oakland
        ("P2", "P3"): 370.0,  # Long Beach <-> Oakland
    },
    "southeast_asia": {
        ("P1", "P2"): 210.0,  # Singapore <-> Port Klang
        ("P1", "P3"): 35.0,   # Singapore <-> PTP (Straits corridor)
        ("P2", "P3"): 190.0,  # Port Klang <-> PTP
    },
    "global_demo": {
        ("P1", "P2"): 250.0,
        ("P1", "P3"): 450.0,
        ("P2", "P3"): 350.0,
    },
}


def get_port_distance_nm(cluster_key: str, port_a: str, port_b: str) -> float:
    """Return maritime distance in nautical miles between two ports in a cluster."""
    if port_a == port_b:
        return 0.0
    cluster_dist = PORT_DISTANCES_NM.get(cluster_key, PORT_DISTANCES_NM["global_demo"])
    key = (port_a, port_b) if (port_a, port_b) in cluster_dist else (port_b, port_a)
    return cluster_dist.get(key, 250.0)