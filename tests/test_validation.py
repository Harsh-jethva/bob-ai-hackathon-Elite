"""Unit tests for data validation, generator, and feature extraction."""

import unittest
from src.data.generator import generate_scenario, generate_ports, generate_vessels, Vessel
from src.data.features import validate_vessels, validate_ports, build_congestion_features


class TestDataValidationAndGenerator(unittest.TestCase):

    def test_default_scenario_generation(self):
        scenario = generate_scenario("normal", 15)
        self.assertEqual(len(scenario["vessels"]), 15)
        self.assertEqual(len(scenario["ports"]), 3)
        self.assertTrue(len(scenario["berths"]) > 0)
        self.assertTrue(len(scenario["cranes"]) > 0)

    def test_vessel_validation_valid(self):
        scenario = generate_scenario("normal", 10)
        is_valid, warnings = validate_vessels(scenario["vessels"])
        self.assertTrue(is_valid)
        error_warnings = [w for w in warnings if w.severity == "error"]
        self.assertEqual(len(error_warnings), 0)

    def test_vessel_validation_duplicate_id(self):
        v1 = Vessel("V001", "Ship 1", 10.0, 10.0, 8.0, 5000.0, 1, 200.0, 10.0, 2, "P1", "P1", "P1", "scheduled")
        v2 = Vessel("V001", "Ship 2", 12.0, 12.0, 8.0, 5000.0, 1, 200.0, 10.0, 2, "P1", "P1", "P1", "scheduled")
        is_valid, warnings = validate_vessels([v1, v2])
        self.assertFalse(is_valid)
        self.assertTrue(any("Duplicate vessel_id" in w.message for w in warnings))

    def test_vessel_validation_negative_arrival(self):
        v = Vessel("V001", "Ship 1", -5.0, -5.0, 8.0, 5000.0, 1, 200.0, 10.0, 2, "P1", "P1", "P1", "scheduled")
        is_valid, warnings = validate_vessels([v])
        self.assertFalse(is_valid)
        self.assertTrue(any("Negative arrival_time" in w.message for w in warnings))

    def test_port_validation(self):
        ports = generate_ports()
        is_valid, warnings = validate_ports(ports)
        self.assertTrue(is_valid)


if __name__ == "__main__":
    unittest.main()
