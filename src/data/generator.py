"""Deterministic demo data generation for PortPilot AI.

Uses fixed random seeds for reproducibility (PRD 11.2).
Generates vessels, ports, berths, cranes for multiple scenarios.
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional

from dataclasses import dataclass, field

from src.config.ports import PortSpec, DEFAULT_PORTS
from src.config.settings import settings


@dataclass
class Vessel:
    vessel_id: str
    vessel_name: str
    arrival_time: float  # hours from planning start
    estimated_arrival_time: float
    service_duration_h: float
    cargo_volume: float  # TEU
    priority: int  # 1=highest
    vessel_length_m: float
    vessel_draft_m: float
    required_cranes: int
    origin_port: str
    destination_port: str
    preferred_port: str
    status: str  # scheduled | delayed | deferred | diverted


@dataclass
class Berth:
    berth_id: str
    port_id: str
    max_vessel_length_m: float
    max_vessel_draft_m: float
    available_from: float = 0.0
    available_to: float = 72.0
    maintenance_windows: List[tuple] = field(default_factory=list)


@dataclass
class Crane:
    crane_id: str
    port_id: str
    available_from: float = 0.0
    available_to: float = 72.0
    maintenance_windows: List[tuple] = field(default_factory=list)
    productivity_teu_per_h: float = 50.0


def _seed_rng() -> random.Random:
    rng = random.Random(settings.random_seed)
    return rng


def generate_ports(num_ports: int = 3, cluster: Optional[str] = None) -> List[PortSpec]:
    """Return the first N ports for a given cluster."""
    if cluster:
        from src.config.ports import get_ports_for_cluster
        return get_ports_for_cluster(cluster)[:num_ports]
    return DEFAULT_PORTS[:num_ports]


def generate_berths(ports: List[PortSpec]) -> List[Berth]:
    berths = []
    for p in ports:
        for i in range(p.num_berths):
            berths.append(Berth(
                berth_id=f"B-{p.port_id}-{i+1}",
                port_id=p.port_id,
                max_vessel_length_m=p.max_vessel_length_m * 0.95,
                max_vessel_draft_m=p.max_vessel_draft_m * 0.95,
            ))
    return berths


def generate_cranes(ports: List[PortSpec]) -> List[Crane]:
    cranes = []
    for p in ports:
        for i in range(p.num_cranes):
            cranes.append(Crane(
                crane_id=f"C-{p.port_id}-{i+1}",
                port_id=p.port_id,
                productivity_teu_per_h=p.avg_service_time_h * 10,
            ))
    return cranes


def generate_vessels(
    num_vessels: int = 20,
    scenario: str = "normal",
    ports: Optional[List[PortSpec]] = None,
) -> List[Vessel]:
    """Generate vessels deterministically for a given scenario."""
    rng = _seed_rng()
    if ports is None:
        ports = generate_ports()

    # Scenario adjustments
    arrival_spread = {"normal": 48, "high_arrival": 24, "weather_disruption": 36}.get(
        scenario, 48
    )
    service_mult = {"normal": 1.0, "high_arrival": 1.0, "crane_outage": 1.3,
                    "berth_maintenance": 1.0, "weather_disruption": 1.5,
                    "congestion": 1.2}.get(scenario, 1.0)

    vessels = []
    for i in range(num_vessels):
        vid = f"V{i+1:03d}"
        vname = f"Vessel-{chr(65 + i % 26)}{i+1}"
        arrival = rng.uniform(0, arrival_spread)
        service = rng.uniform(6, 24) * service_mult
        cargo = rng.uniform(1000, 20000)
        priority = rng.choices([1, 2, 3], weights=[0.2, 0.3, 0.5])[0]
        vlen = rng.uniform(100, 350)
        vdraft = rng.uniform(5, 13)
        cranes = rng.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
        origin = rng.choice(ports).port_id
        dest = rng.choice(ports).port_id
        preferred = rng.choice(ports).port_id
        vessels.append(Vessel(
            vessel_id=vid, vessel_name=vname,
            arrival_time=round(arrival, 2),
            estimated_arrival_time=round(arrival, 2),
            service_duration_h=round(service, 2),
            cargo_volume=round(cargo, 1),
            priority=priority,
            vessel_length_m=round(vlen, 1),
            vessel_draft_m=round(vdraft, 1),
            required_cranes=cranes,
            origin_port=origin, destination_port=dest, preferred_port=preferred,
            status="scheduled",
        ))
    # Sort by arrival for deterministic FCFS
    vessels.sort(key=lambda v: v.arrival_time)
    return vessels


def generate_scenario(
    scenario: str = "normal",
    num_vessels: int = 20,
    cluster: Optional[str] = None,
    ports: Optional[List[PortSpec]] = None,
) -> dict:
    """Generate a full demo scenario dict."""
    if ports is None:
        ports = generate_ports(cluster=cluster)
    berths = generate_berths(ports)
    cranes = generate_cranes(ports)
    vessels = generate_vessels(num_vessels, scenario, ports)
    return {
        "scenario": scenario,
        "ports": ports,
        "berths": berths,
        "cranes": cranes,
        "vessels": vessels,
    }

