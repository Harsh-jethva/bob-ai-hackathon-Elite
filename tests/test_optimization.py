"""Unit tests for OR-Tools CP-SAT berth allocator and hard constraints."""

import unittest
from src.data.generator import generate_scenario
from src.models.congestion_model import predict_congestion
from src.optimization.berth_allocator import solve_berth_allocation, SolverStatus


class TestBerthOptimization(unittest.TestCase):

    def test_cpsat_solver_execution(self):
        scenario = generate_scenario("normal", 15)
        forecasts = predict_congestion(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        res = solve_berth_allocation(
            scenario["vessels"], scenario["berths"], scenario["cranes"], forecasts, 72.0
        )
        self.assertIn(res.status, [SolverStatus.OPTIMAL, SolverStatus.FEASIBLE])
        self.assertEqual(res.method, "OR-Tools CP-SAT")
        self.assertFalse(res.fallback_used)
        self.assertGreater(res.runtime_seconds, 0.0)
        self.assertEqual(len(res.assignments), 15)

    def test_hard_constraints_no_berth_overlap(self):
        scenario = generate_scenario("normal", 20)
        forecasts = predict_congestion(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        res = solve_berth_allocation(
            scenario["vessels"], scenario["berths"], scenario["cranes"], forecasts, 72.0
        )
        scheduled = [a for a in res.assignments if not a.deferred]

        # Group by berth and check intervals
        by_berth = {}
        for a in scheduled:
            by_berth.setdefault(a.berth_id, []).append(a)

        for b_id, b_assignments in by_berth.items():
            sorted_b = sorted(b_assignments, key=lambda x: x.start_time)
            for i in range(len(sorted_b) - 1):
                # end time of current must be <= start time of next (with small float tolerance)
                self.assertLessEqual(
                    sorted_b[i].end_time,
                    sorted_b[i+1].start_time + 0.01,
                    f"Berth overlap detected on berth {b_id} between {sorted_b[i].vessel_id} and {sorted_b[i+1].vessel_id}"
                )

    def test_start_after_arrival_constraint(self):
        scenario = generate_scenario("normal", 15)
        vessels_by_id = {v.vessel_id: v for v in scenario["vessels"]}
        forecasts = predict_congestion(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        res = solve_berth_allocation(
            scenario["vessels"], scenario["berths"], scenario["cranes"], forecasts, 72.0
        )
        for a in res.assignments:
            if not a.deferred:
                v = vessels_by_id[a.vessel_id]
                self.assertGreaterEqual(
                    a.start_time,
                    v.arrival_time - 0.01,
                    f"Vessel {v.vessel_id} started before arrival time"
                )


if __name__ == "__main__":
    unittest.main()
