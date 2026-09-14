"""Unit tests for what-if simulation engine and alert completeness."""

import unittest
from src.data.generator import generate_scenario
from src.simulation.port_sim import run_simulation, SimulationParam
from src.app.dashboard import _generate_all_system_alerts
from src.models.congestion_model import predict_congestion
from src.optimization.planner import generate_optimized


class TestSimulationAndAlerts(unittest.TestCase):

    def test_simulation_recalculates_full_pipeline(self):
        base_scenario = generate_scenario("normal", 15)
        param = SimulationParam(
            param_type="arrival_surge",
            change_value=2.0
        )
        sim_res = run_simulation(base_scenario, [param], 72.0)
        self.assertIsNotNone(sim_res.scenario_fcfs)
        self.assertIsNotNone(sim_res.scenario_optimized)
        self.assertIn("fcfs_wait_delta", sim_res.kpi_comparison)
        self.assertIn("opt_wait_delta", sim_res.kpi_comparison)

    def test_all_alerts_have_five_mandatory_fields(self):
        # PRD 11.10: severity, affected entity, trigger, explanation, and recommended action
        scenario = generate_scenario("congestion", 12)
        forecasts = predict_congestion(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        opt = generate_optimized(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        sim_res = run_simulation(
            scenario,
            [SimulationParam(param_type="weather_disruption")],
            72.0
        )
        alerts = _generate_all_system_alerts(forecasts, opt, sim_res)

        mandatory_fields = ["severity", "entity", "trigger", "explanation", "recommended_action"]
        for a in alerts:
            for field in mandatory_fields:
                self.assertIn(field, a, f"Alert missing mandatory field '{field}': {a}")
                self.assertTrue(len(str(a[field])) > 0, f"Alert field '{field}' is empty: {a}")


if __name__ == "__main__":
    unittest.main()
