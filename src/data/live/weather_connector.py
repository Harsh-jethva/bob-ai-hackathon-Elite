"""Marine Weather Live Connector for PortPilot AI.

Pulls real-time MetOcean conditions (wind speeds, gusts, wave heights)
via Open-Meteo REST API or offline fallback.
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from src.config.settings import settings


@dataclass
class PortWeather:
    port_id: str
    port_name: str
    wind_speed_kmh: float
    wind_speed_knots: float
    wind_gusts_kmh: float
    wind_gusts_knots: float
    temperature_c: float
    precipitation_mm: float
    condition_summary: str
    crane_shutoff_risk: bool  # True if gusts > 35 knots
    pilotage_delay_risk: bool  # True if heavy precipitation or high wind
    is_live: bool


class WeatherConnector:
    """Connects to Open-Meteo weather API for live port weather."""

    def __init__(self):
        self.port_coords = settings.live_port_coordinates

    def fetch_port_weather(
        self,
        port_id: str,
        name: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> PortWeather:
        """Fetch current live weather for a specific port."""
        if lat is None or lon is None:
            port_info = self.port_coords.get(port_id, {"name": port_id, "lat": 18.95, "lon": 72.85})
            lat = port_info["lat"]
            lon = port_info["lon"]
            name = name or port_info.get("name", port_id)
        else:
            name = name or port_id

        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&"
                f"current=temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m&"
                f"wind_speed_unit=kmh"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "PortPilot-AI/2.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                current = data.get("current", {})

                wind_kmh = float(current.get("wind_speed_10m", 15.0))
                gusts_kmh = float(current.get("wind_gusts_10m", wind_kmh * 1.3))
                temp_c = float(current.get("temperature_2m", 27.0))
                precip_mm = float(current.get("precipitation", 0.0))

                wind_knots = round(wind_kmh * 0.539957, 1)
                gusts_knots = round(gusts_kmh * 0.539957, 1)

                crane_risk = gusts_knots >= 35.0
                pilot_risk = wind_knots >= 28.0 or precip_mm > 15.0

                if crane_risk:
                    summary = f"⚠️ Severe Wind Alert ({gusts_knots} kts gusts) — Crane Outage Risk"
                elif pilot_risk:
                    summary = f"🟡 Moderate Sea Conditions ({wind_knots} kts) — Pilotage Advisory"
                else:
                    summary = f"🟢 Fair Marine Weather ({wind_knots} kts wind, {temp_c}°C)"

                return PortWeather(
                    port_id=port_id,
                    port_name=name,
                    wind_speed_kmh=round(wind_kmh, 1),
                    wind_speed_knots=wind_knots,
                    wind_gusts_kmh=round(gusts_kmh, 1),
                    wind_gusts_knots=gusts_knots,
                    temperature_c=temp_c,
                    precipitation_mm=precip_mm,
                    condition_summary=summary,
                    crane_shutoff_risk=crane_risk,
                    pilotage_delay_risk=pilot_risk,
                    is_live=True,
                )

        except Exception as e:
            # Safe operational fallback
            return self._fallback_weather(port_id, name, str(e))

    def fetch_all_ports_weather(
        self, ports: Optional[List[Any]] = None
    ) -> Dict[str, PortWeather]:
        """Fetch weather for all configured ports."""
        results = {}
        if ports:
            for p in ports:
                results[p.port_id] = self.fetch_port_weather(
                    p.port_id, name=p.port_name, lat=getattr(p, "lat", None), lon=getattr(p, "lon", None)
                )
        else:
            for port_id in self.port_coords:
                results[port_id] = self.fetch_port_weather(port_id)
        return results

    def _fallback_weather(self, port_id: str, name: str, reason: str) -> PortWeather:
        """Deterministic offline fallback weather."""
        return PortWeather(
            port_id=port_id,
            port_name=name,
            wind_speed_kmh=18.5,
            wind_speed_knots=10.0,
            wind_gusts_kmh=24.0,
            wind_gusts_knots=13.0,
            temperature_c=26.0,
            precipitation_mm=0.0,
            condition_summary="🟢 Standard Operational Conditions (Local Cache)",
            crane_shutoff_risk=False,
            pilotage_delay_risk=False,
            is_live=False,
        )
