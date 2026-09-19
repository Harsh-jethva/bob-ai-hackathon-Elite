"""Deterministic demo data generation for PortPilot AI.

Uses fixed random seeds for reproducibility (PRD 11.2).
Generates vessels, ports, berths, cranes for multiple scenarios.
Berths and cranes are generated with realistic pre-existing occupancy
pulled from PORT_LIVE_STATES in src.config.ports.
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional

from dataclasses import dataclass, field

from src.config.ports import PortSpec, DEFAULT_PORTS, PortLiveState, get_live_state
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
    available_from: float = 0.0       # T+0 = free; >0 = occupied until that hour
    available_to: float = 72.0
    maintenance_windows: List[tuple] = field(default_factory=list)
    # Occupancy metadata (for UI display)
    currently_occupied: bool = False
    occupying_vessel: str = ""         # vessel name currently docked
    free_at_hours: float = 0.0        # same as available_from when occupied


@dataclass
class Crane:
    crane_id: str
    port_id: str
    available_from: float = 0.0       # T+0 = free; >0 = busy until that hour
    available_to: float = 72.0
    maintenance_windows: List[tuple] = field(default_factory=list)
    productivity_teu_per_h: float = 50.0
    # Occupancy metadata
    currently_busy: bool = False
    busy_until_hours: float = 0.0


def _seed_rng() -> random.Random:
    rng = random.Random(settings.random_seed)
    return rng


def generate_ports(num_ports: int = 3, cluster: Optional[str] = None) -> List[PortSpec]:
    """Return the first N ports for a given cluster."""
    if cluster:
        from src.config.ports import get_ports_for_cluster
        return get_ports_for_cluster(cluster)[:num_ports]
    return DEFAULT_PORTS[:num_ports]


def generate_berths(
    ports: List[PortSpec],
    cluster: Optional[str] = None,
    live_states: Optional[dict] = None,
) -> List[Berth]:
    """Generate berths with realistic pre-existing occupancy from PORT_LIVE_STATES.

    Args:
        ports: list of PortSpec objects.
        cluster: cluster key string to look up live states (e.g. "india").
        live_states: optional override dict {port_id: PortLiveState}.

    Each berth that has an existing ship docked gets available_from set to the
    time the current ship will finish (free_at_hours), making it unavailable to
    incoming vessels until then.
    """
    berths = []
    for p in ports:
        # Resolve live state for this port
        state: PortLiveState
        if live_states and p.port_id in live_states:
            state = live_states[p.port_id]
        elif cluster:
            state = get_live_state(cluster, p.port_id)
        else:
            state = PortLiveState()

        occupied_map = {ob.berth_id: ob for ob in state.occupied_berths}

        for i in range(p.num_berths):
            berth_id = f"B-{p.port_id}-{i+1}"
            ob = occupied_map.get(berth_id)

            if ob:
                # This berth is already occupied — not available until ob.free_at_hours
                berths.append(Berth(
                    berth_id=berth_id,
                    port_id=p.port_id,
                    max_vessel_length_m=p.max_vessel_length_m * 0.95,
                    max_vessel_draft_m=p.max_vessel_draft_m * 0.95,
                    available_from=ob.free_at_hours,
                    available_to=72.0,
                    currently_occupied=True,
                    occupying_vessel=ob.vessel_name,
                    free_at_hours=ob.free_at_hours,
                ))
            else:
                berths.append(Berth(
                    berth_id=berth_id,
                    port_id=p.port_id,
                    max_vessel_length_m=p.max_vessel_length_m * 0.95,
                    max_vessel_draft_m=p.max_vessel_draft_m * 0.95,
                    available_from=0.0,
                    available_to=72.0,
                    currently_occupied=False,
                    occupying_vessel="",
                    free_at_hours=0.0,
                ))
    return berths


def generate_cranes(
    ports: List[PortSpec],
    cluster: Optional[str] = None,
    live_states: Optional[dict] = None,
) -> List[Crane]:
    """Generate cranes with realistic pre-existing busy state from PORT_LIVE_STATES.

    Cranes listed in crane_busy_until get available_from = that hour,
    so the optimizer won't assign them to new ships before they're free.
    """
    cranes = []
    for p in ports:
        state: PortLiveState
        if live_states and p.port_id in live_states:
            state = live_states[p.port_id]
        elif cluster:
            state = get_live_state(cluster, p.port_id)
        else:
            state = PortLiveState()

        for i in range(p.num_cranes):
            crane_id = f"C-{p.port_id}-{i+1}"
            busy_until = state.crane_busy_until.get(crane_id, 0.0)
            cranes.append(Crane(
                crane_id=crane_id,
                port_id=p.port_id,
                available_from=busy_until,
                available_to=72.0,
                productivity_teu_per_h=p.avg_service_time_h * 10,
                currently_busy=(busy_until > 0.0),
                busy_until_hours=busy_until,
            ))
    return cranes


def generate_vessels(
    num_vessels: int = 20,
    scenario: str = "normal",
    ports: Optional[List[PortSpec]] = None,
    target_port_id: Optional[str] = None,
) -> List[Vessel]:
    """Generate vessels deterministically for a given scenario.

    Args:
        target_port_id: if set, all vessels get preferred_port = target_port_id,
                        simulating ships inbound to the selected port.
    """
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
        cranes_req = rng.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
        origin = rng.choice(ports).port_id
        dest = rng.choice(ports).port_id
        preferred = target_port_id if target_port_id else rng.choice(ports).port_id
        vessels.append(Vessel(
            vessel_id=vid, vessel_name=vname,
            arrival_time=round(arrival, 2),
            estimated_arrival_time=round(arrival, 2),
            service_duration_h=round(service, 2),
            cargo_volume=round(cargo, 1),
            priority=priority,
            vessel_length_m=round(vlen, 1),
            vessel_draft_m=round(vdraft, 1),
            required_cranes=cranes_req,
            origin_port=origin,
            destination_port=dest if not target_port_id else target_port_id,
            preferred_port=preferred,
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
    target_port_id: Optional[str] = None,
) -> dict:
    """Generate a full demo scenario dict.

    Args:
        target_port_id: if set, generate data focused on a single port
                        (vessels all headed there, berths/cranes for that port).
    """
    if ports is None:
        ports = generate_ports(cluster=cluster)

    berths = generate_berths(ports, cluster=cluster)
    cranes = generate_cranes(ports, cluster=cluster)
    vessels = generate_vessels(num_vessels, scenario, ports, target_port_id=target_port_id)
    return {
        "scenario": scenario,
        "ports": ports,
        "berths": berths,
        "cranes": cranes,
        "vessels": vessels,
    }
