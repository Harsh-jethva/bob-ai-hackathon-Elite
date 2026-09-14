"""Unit tests for alternative port recommender and weighted scoring (PRD 11.8)."""

import unittest
from src.data.generator import generate_scenario
from src.models.congestion_model import predict_congestion
from src.optimization.router import recommend_alternative_ports, score_alternative_port


class TestRouter(unittest.TestCase):

    def test_recommend_alternative_ports(self):
        scenario = generate_scenario("normal", 20)
        vessels = scenario["vessels"]
        ports = scenario["ports"]
        forecasts = predict_congestion(vessels, scenario["berths"], scenario["cranes"], 72.0)

        v = vessels[0]
        recs = recommend_alternative_ports(v, ports, forecasts, top_n=2)
        # Should return candidates not equal to preferred port
        for r in recs:
            self.assertNotEqual(r.recommended_port_id, v.preferred_port)
            self.assertGreaterEqual(r.score, 0.0)
            self.assertLessEqual(r.score, 1.0)
            self.assertTrue(len(r.rationale) > 0)
            self.assertIn("expected_delay", r.components)
            self.assertIn("feasibility", r.components)


if __name__ == "__main__":
    unittest.main()
