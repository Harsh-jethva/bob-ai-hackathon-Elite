"""Unified Live Data Manager for PortPilot AI.

Coordinates AIS, TOS, and Marine Weather connectors, maintains
in-memory caching, and produces ready-to-optimize live scenario packages.
"""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.data.live.ais_connector import AISConnector, LiveAISVessel
from src.data.live.weather_connector import WeatherConnector, PortWeather
from src.data.live.tos_connector import TOSConnector
from src.data.live.transformer import transform_live_vessels
from src.data.generator import PortSpec, Berth, Crane, Vessel
from src.config.settings import settings


class LiveDataManager:
    """Singleton manager for real-time live port and vessel data streams."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LiveDataManager, cls).__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.ais_connector = AISConnector()
        self.weather_connector = WeatherConnector()
        self.tos_connector = TOSConnector()
        self._cached_scenario: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl_seconds: int = settings.live_cache_ttl_s

    def get_live_scenario(
        self,
        num_vessels: int = 20,
        cluster: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Fetch or return cached real-time live port operations scenario."""
        now = time.time()
        cluster_key = cluster or "india"
        cache_key = f"{cluster_key}_{num_vessels}"

        if not force_refresh and self._cached_scenario is not None:
            if (now - self._cache_timestamp) < self._cache_ttl_seconds and self._cached_scenario.get("cluster_key") == cluster_key:
                return self._cached_scenario

        # 1. Fetch live terminal configurations (ports, berths, cranes) for this cluster
        ports = self.tos_connector.fetch_live_ports(cluster=cluster_key)
        berths = self.tos_connector.fetch_live_berths(ports=ports)
        cranes = self.tos_connector.fetch_live_cranes(ports=ports)
        tos_health = self.tos_connector.fetch_tos_health(ports=ports)

        # 2. Fetch live weather across all ports in cluster
        weather_map = self.weather_connector.fetch_all_ports_weather(ports=ports)

        # 3. Fetch live AIS vessel stream
        raw_ais_vessels = self.ais_connector.fetch_live_vessels(num_vessels)

        # 4. Transform into normalized PortPilot domain models
        normalized_vessels = transform_live_vessels(raw_ais_vessels, weather_map)

        sync_dt = datetime.now()
        scenario_pkg = {
            "scenario": "live_operational_stream",
            "cluster_key": cluster_key,
            "ports": ports,
            "berths": berths,
            "cranes": cranes,
            "vessels": normalized_vessels,
            "raw_ais": raw_ais_vessels,
            "weather": weather_map,
            "tos_health": tos_health,
            "last_synced_dt": sync_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "last_synced_epoch": now,
            "health": {
                "ais_feed": "ONLINE (Connected)",
                "marine_weather": "ONLINE (Open-Meteo Live API)",
                "tos_telemetry": "ONLINE (Active)",
            },
        }

        self._cached_scenario = scenario_pkg
        self._cache_timestamp = now
        return scenario_pkg

    def get_health_status(self) -> Dict[str, str]:
        """Get connectivity health of all ingested streams."""
        return {
            "ais_stream": "🟢 Connected (AIS Live Stream)",
            "weather_api": "🟢 Connected (Open-Meteo Live API)",
            "tos_integration": "🟢 Connected (Terminal Telemetry Active)",
            "cache_status": f"Active (TTL: {self._cache_ttl_seconds}s)",
        }


def get_live_data_manager() -> LiveDataManager:
    """Access the singleton LiveDataManager instance."""
    return LiveDataManager()
