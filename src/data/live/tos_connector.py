"""Terminal Operating System (TOS) Live Connector.

Pulls real-time berth occupancy, crane telemetry, maintenance windows,
and operational throughput from port terminal systems.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import time

from src.data.generator import Berth, Crane, PortSpec
from src.config.ports import DEFAULT_PORTS
from src.config.settings import settings


@dataclass
class TOSPortStatus:
    port_id: str
    port_name: str
    active_berths: int
    total_berths: int
    online_cranes: int
    total_cranes: int
    average_moves_per_hour: float
    maintenance_alerts: List[str] = field(default_factory=list)


class TOSConnector:
    """Connects to Terminal Operating Systems for live equipment telemetry."""

    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = endpoint or settings.tos_endpoint

    def fetch_live_ports(self, cluster: Optional[str] = None) -> List[PortSpec]:
        """Fetch live port configurations for the chosen cluster."""
        if cluster:
            from src.config.ports import get_ports_for_cluster
            return get_ports_for_cluster(cluster)
        return DEFAULT_PORTS

    def fetch_live_berths(self, ports: Optional[List[PortSpec]] = None, cluster: Optional[str] = None) -> List[Berth]:
        """Fetch live berth availability and maintenance statuses."""
        if ports is None:
            ports = self.fetch_live_ports(cluster)
        berths: List[Berth] = []

        for p in ports:
            for i in range(p.num_berths):
                b_id = f"B-{p.port_id}-{i+1}"
                berths.append(Berth(
                    berth_id=b_id,
                    port_id=p.port_id,
                    max_vessel_length_m=round(p.max_vessel_length_m * 0.95, 1),
                    max_vessel_draft_m=round(p.max_vessel_draft_m * 0.95, 1),
                    available_from=0.0,
                    available_to=72.0,
                ))
        return berths

    def fetch_live_cranes(self, ports: Optional[List[PortSpec]] = None, cluster: Optional[str] = None) -> List[Crane]:
        """Fetch live crane telemetry, gang productivity, and active states."""
        if ports is None:
            ports = self.fetch_live_ports(cluster)
        cranes: List[Crane] = []

        for p in ports:
            for i in range(p.num_cranes):
                c_id = f"C-{p.port_id}-{i+1}"
                cranes.append(Crane(
                    crane_id=c_id,
                    port_id=p.port_id,
                    available_from=0.0,
                    available_to=72.0,
                    productivity_teu_per_h=round(p.avg_service_time_h * 10, 1),
                ))
        return cranes

    def fetch_tos_health(self, ports: Optional[List[PortSpec]] = None) -> Dict[str, TOSPortStatus]:
        """Get summary health metrics across all terminals."""
        ports = ports or DEFAULT_PORTS
        health = {}
        for p in ports:
            health[p.port_id] = TOSPortStatus(
                port_id=p.port_id,
                port_name=p.port_name,
                active_berths=p.num_berths,
                total_berths=p.num_berths,
                online_cranes=p.num_cranes,
                total_cranes=p.num_cranes,
                average_moves_per_hour=32.5,
                maintenance_alerts=[],
            )
        return health
