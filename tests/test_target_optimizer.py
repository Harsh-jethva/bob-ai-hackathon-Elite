"""Unit tests for Target Port-Based Congestion Optimization and Voyage Cost Modeling."""

import unittest
from src.data.generator import generate_scenario, generate_ports, generate_berths, generate_cranes, generate_vessels
from src.optimization.voyage_cost import (
    VoyageCostParams,
    compute_target_port_cost,
    compute_diversion_cost,
)
from src.optimization.target_optimizer import (
    run_target_port_optimization,
    RecommendationVerdict,
)


class TestTargetPortOptimizer(unittest.TestCase):

    def setUp(self):
        self.ports = generate_ports(cluster="india")
        self.berths = generate_berths(self.ports, cluster="india")
        self.cranes = generate_cranes(self.ports, cluster="india")
        self.vessels = generate_vessels(10, "normal", self.ports)

    def test_compute_target_port_cost(self):
        v = self.vessels[0]
        port = self.ports[0]
        params = VoyageCostParams(
            vessel_daily_cost_usd=24000.0,
            demurrage_rate_day_usd=24000.0,
            free_laytime_hours=12.0,
        )
        # Case 1: 0 wait hours -> no demurrage, no wait opex
        cost_zero = compute_target_port_cost(v, port, wait_hours=0.0, params=params)
        self.assertEqual(cost_zero.wait_opex_cost, 0.0)
        self.assertEqual(cost_zero.demurrage_cost, 0.0)
        self.assertGreater(cost_zero.total_target_cost, 0.0)

        # Case 2: 24 wait hours -> 1 day wait opex ($24,000) + 12h demurrage ($12,000)
        cost_24 = compute_target_port_cost(v, port, wait_hours=24.0, params=params)
        self.assertAlmostEqual(cost_24.wait_opex_cost, 24000.0, delta=1.0)
        self.assertAlmostEqual(cost_24.demurrage_cost, 12000.0, delta=1.0)
        self.assertGreater(cost_24.total_target_cost, cost_zero.total_target_cost)

    def test_compute_diversion_cost(self):
        v = self.vessels[0]
        target_p = self.ports[0]
        alt_p = self.ports[1]
        params = VoyageCostParams()

        target_cost = compute_target_port_cost(v, target_p, wait_hours=10.0, params=params)
        div_cost = compute_diversion_cost(
            vessel=v,
            target_cost=target_cost,
            candidate_port=alt_p,
            extra_distance_nm=480.0,
            wait_hours_at_alt=2.0,
            params=params,
        )
        self.assertEqual(div_cost.candidate_port_id, alt_p.port_id)
        self.assertGreater(div_cost.extra_sailing_hours, 0.0)
        self.assertGreater(div_cost.extra_sailing_fuel_cost, 0.0)
        self.assertGreater(div_cost.total_diversion_cost, 0.0)

    def test_target_port_optimization_workflow(self):
        target_p = self.ports[0]
        v = self.vessels[0]
        v.preferred_port = target_p.port_id
        v.destination_port = target_p.port_id

        result = run_target_port_optimization(
            vessel=v,
            target_port=target_p,
            all_ports=self.ports,
            all_berths=self.berths,
            all_cranes=self.cranes,
            incoming_fleet=self.vessels,
            cluster_key="india",
        )
        self.assertIn(result.verdict, [RecommendationVerdict.PROCEED_TO_TARGET, RecommendationVerdict.CONSIDER_DIVERSION])
        self.assertGreater(result.confidence, 0.0)
        self.assertEqual(result.target_port.port_id, target_p.port_id)
        self.assertGreater(len(result.alternatives), 0)
        self.assertIsNotNone(result.target_analysis)
        self.assertGreater(result.total_target_cost, 0.0)


if __name__ == "__main__":
    unittest.main()
