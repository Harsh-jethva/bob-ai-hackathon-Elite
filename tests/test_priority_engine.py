"""Unit tests for Dynamic Multi-Factor Vessel Priority Engine & Economic Cost Comparison."""

import unittest
from src.data.generator import Vessel, Berth, Crane, generate_scenario
from src.optimization.priority_engine import (
    evaluate_vessel_priority, apply_priority_scoring, CARGO_PROFILES
)
from src.optimization.planner import generate_fcfs, generate_optimized, compare_plans


class TestPriorityEngine(unittest.TestCase):
    """Test suite for multi-factor priority scoring and classification."""

    def setUp(self):
        self.berths = [
            Berth(berth_id="B1", port_id="P1", max_vessel_length_m=350.0, max_vessel_draft_m=14.0),
            Berth(berth_id="B2", port_id="P1", max_vessel_length_m=220.0, max_vessel_draft_m=10.0),
        ]
        self.cranes = [
            Crane(crane_id="C1", port_id="P1"),
            Crane(crane_id="C2", port_id="P1"),
            Crane(crane_id="C3", port_id="P1"),
        ]

    def test_high_value_perishable_vessel_gets_priority_1(self):
        """Vessels with high-value reefer cargo and tight laycan must receive Priority 1."""
        v = Vessel(
            vessel_id="V001",
            vessel_name="Pharma Express",
            arrival_time=2.0,
            estimated_arrival_time=2.0,
            service_duration_h=10.0,
            cargo_volume=12000.0,
            priority=3,  # Initial dummy
            vessel_length_m=330.0,
            vessel_draft_m=13.5,  # Fits only deep-water berth B1
            required_cranes=3,
            origin_port="P2",
            destination_port="P1",
            preferred_port="P1",
            status="scheduled",
            cargo_type="Reefer / Pharmaceuticals",
            cargo_value_usd=65_000_000.0,
            holding_cost_per_hour_usd=2800.0,
            laycan_end_h=12.0,  # 10h laytime tolerance
            demurrage_rate_per_hour_usd=1900.0,
            vessel_daily_charter_usd=38000.0,
        )

        pb = evaluate_vessel_priority(v, self.berths, self.cranes)
        self.assertGreaterEqual(pb.composite_score, 70.0)
        self.assertEqual(pb.priority_level, 1)
        self.assertTrue(len(pb.reasons) > 0)

    def test_bulk_cargo_flexible_vessel_gets_priority_3(self):
        """Vessels with low-value bulk cargo and relaxed deadlines receive Priority 3."""
        v = Vessel(
            vessel_id="V002",
            vessel_name="Coal Feeder",
            arrival_time=15.0,
            estimated_arrival_time=15.0,
            service_duration_h=12.0,
            cargo_volume=2000.0,
            priority=1,  # Initial dummy
            vessel_length_m=140.0,
            vessel_draft_m=6.5,  # Fits all berths
            required_cranes=1,
            origin_port="P2",
            destination_port="P1",
            preferred_port="P1",
            status="scheduled",
            cargo_type="Dry Bulk & Minerals",
            cargo_value_usd=3_000_000.0,
            holding_cost_per_hour_usd=220.0,
            laycan_end_h=45.0,  # 30h laytime tolerance
            demurrage_rate_per_hour_usd=700.0,
            vessel_daily_charter_usd=18000.0,
        )

        pb = evaluate_vessel_priority(v, self.berths, self.cranes)
        self.assertLess(pb.composite_score, 50.0)
        self.assertEqual(pb.priority_level, 3)

    def test_apply_priority_scoring_updates_vessels(self):
        """apply_priority_scoring should update priority, priority_score, and reasons."""
        scenario = generate_scenario("congestion", num_vessels=10, cluster="india")
        vessels = scenario["vessels"]
        berths = scenario["berths"]
        cranes = scenario["cranes"]

        vessels = apply_priority_scoring(vessels, berths, cranes)
        for v in vessels:
            self.assertIn(v.priority, (1, 2, 3))
            self.assertGreaterEqual(v.priority_score, 0.0)
            self.assertLessEqual(v.priority_score, 100.0)
            self.assertIsInstance(v.priority_reasons, list)

    def test_priority_optimizer_vs_fcfs_cost_savings(self):
        """Priority-optimized schedule must achieve lower or equal total cost compared to FCFS."""
        scenario = generate_scenario("high_arrival", num_vessels=12, cluster="india")
        vessels = scenario["vessels"]
        berths = scenario["berths"]
        cranes = scenario["cranes"]

        fcfs_plan = generate_fcfs(vessels, berths, cranes, horizon_hours=72.0)
        opt_plan = generate_optimized(vessels, berths, cranes, horizon_hours=72.0)

        comparison = compare_plans(fcfs_plan, opt_plan, vessels)
        self.assertIsInstance(comparison.net_savings_usd, float)
        self.assertGreaterEqual(comparison.net_savings_usd, 0.0)
        self.assertEqual(len(comparison.vessel_details), len(vessels))


if __name__ == "__main__":
    unittest.main()
