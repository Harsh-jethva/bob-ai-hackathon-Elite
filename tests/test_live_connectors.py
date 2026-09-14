"""Unit tests for live data connectors, weather, AIS, and transformer."""

import unittest
from src.data.live.weather_connector import WeatherConnector, PortWeather
from src.data.live.ais_connector import AISConnector, LiveAISVessel
from src.data.live.tos_connector import TOSConnector
from src.data.live.transformer import transform_live_vessels
from src.data.live.live_manager import get_live_data_manager
from src.data.features import validate_vessels, validate_ports


class TestLiveConnectors(unittest.TestCase):

    def test_weather_connector(self):
        connector = WeatherConnector()
        weather = connector.fetch_port_weather("P1")
        self.assertIsInstance(weather, PortWeather)
        self.assertEqual(weather.port_id, "P1")
        self.assertGreaterEqual(weather.wind_speed_kmh, 0.0)
        self.assertGreaterEqual(weather.wind_speed_knots, 0.0)
        self.assertTrue(len(weather.condition_summary) > 0)

    def test_ais_connector(self):
        connector = AISConnector()
        vessels = connector.fetch_live_vessels(15)
        self.assertEqual(len(vessels), 15)
        for v in vessels:
            self.assertIsInstance(v, LiveAISVessel)
            self.assertGreaterEqual(v.eta_relative_hours, 0.0)
            self.assertGreater(v.length_m, 0.0)
            self.assertGreater(v.draft_m, 0.0)

    def test_tos_connector(self):
        connector = TOSConnector()
        ports = connector.fetch_live_ports()
        berths = connector.fetch_live_berths(ports)
        cranes = connector.fetch_live_cranes(ports)
        self.assertTrue(len(ports) > 0)
        self.assertTrue(len(berths) > 0)
        self.assertTrue(len(cranes) > 0)

    def test_live_transformer_and_validation(self):
        ais_conn = AISConnector()
        weather_conn = WeatherConnector()
        raw_vessels = ais_conn.fetch_live_vessels(12)
        weather_map = weather_conn.fetch_all_ports_weather()

        norm_vessels = transform_live_vessels(raw_vessels, weather_map)
        self.assertEqual(len(norm_vessels), 12)

        # Validate with existing validation layer
        is_valid, warnings = validate_vessels(norm_vessels)
        self.assertTrue(is_valid)
        error_warnings = [w for w in warnings if w.severity == "error"]
        self.assertEqual(len(error_warnings), 0)

    def test_live_data_manager_package(self):
        mgr = get_live_data_manager()
        pkg = mgr.get_live_scenario(num_vessels=10, force_refresh=True)
        self.assertEqual(pkg["scenario"], "live_operational_stream")
        self.assertEqual(len(pkg["vessels"]), 10)
        self.assertIn("weather", pkg)
        self.assertIn("health", pkg)
        self.assertIn("last_synced_dt", pkg)


if __name__ == "__main__":
    unittest.main()
