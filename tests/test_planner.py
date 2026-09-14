"""Unit tests for FCFS baseline, CP-SAT optimized planning, and fair KPI comparison."""

import unittest
from src.data.generator import generate_scenario
from src.optimization.planner import generate_fcfs, generate_optimized, generate_both


class TestPlanner(unittest.TestCase):

    def test_fcfs_and_optimized_plans(self):
        scenario = generate_scenario("normal", 20)
        fcfs, opt = generate_both(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        self.assertEqual(fcfs.vessels_count, 20)
        self.assertEqual(opt.vessels_count, 20)
        self.assertEqual(len(fcfs.assignments), 20)
        self.assertEqual(len(opt.assignments), 20)

        # KPIs should be non-negative
        self.assertGreaterEqual(fcfs.avg_wait_hours, 0.0)
        self.assertGreaterEqual(opt.avg_wait_hours, 0.0)
        self.assertGreaterEqual(fcfs.berth_utilization, 0.0)
        self.assertGreaterEqual(opt.berth_utilization, 0.0)

    def test_consistent_evaluation_population(self):
        scenario = generate_scenario("high_arrival", 15)
        fcfs, opt = generate_both(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        fcfs_ids = set(a.vessel_id for a in fcfs.assignments)
        opt_ids = set(a.vessel_id for a in opt.assignments)
        self.assertEqual(fcfs_ids, opt_ids)


if __name__ == "__main__":
    unittest.main()
