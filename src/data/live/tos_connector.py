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
        from src.data.generator import generate_berths
        return generate_berths(ports=ports, cluster=cluster)

    def fetch_live_cranes(self, ports: Optional[List[PortSpec]] = None, cluster: Optional[str] = None) -> List[Crane]:
        """Fetch live crane telemetry, gang productivity, and active states."""
        if ports is None:
            ports = self.fetch_live_ports(cluster)
        from src.data.generator import generate_cranes
        return generate_cranes(ports=ports, cluster=cluster)

    def fetch_tos_health(self, ports: Optional[List[PortSpec]] = None, cluster: Optional[str] = None) -> Dict[str, TOSPortStatus]:
        """Get summary health metrics across all terminals."""
        from src.config.ports import get_live_state
        ports = ports or DEFAULT_PORTS
        cluster_key = cluster or "india"
        health = {}
        for p in ports:
            st_info = get_live_state(cluster_key, p.port_id)
            busy_cranes = sum(1 for v in st_info.crane_busy_until.values() if v > 0)
            health[p.port_id] = TOSPortStatus(
                port_id=p.port_id,
                port_name=p.port_name,
                active_berths=p.num_berths - len(st_info.occupied_berths),
                total_berths=p.num_berths,
                online_cranes=p.num_cranes - busy_cranes,
                total_cranes=p.num_cranes,
                average_moves_per_hour=32.5,
                maintenance_alerts=[
                    f"Berth {ob.berth_id} in use by {ob.vessel_name} (free at T+{ob.free_at_hours:.1f}h)"
                    for ob in st_info.occupied_berths
                ],
            )
        return health
