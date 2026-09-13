"""End-to-end pipeline: generate data -> train model -> build 72h plan.
Run from project root:  python -m src.main"""
import pandas as pd
from src.data.generator import generate_all
from src.simulation.port_sim import simulate_port
from src.data.features import build_training_table
from src.models.congestion_model import CongestionModel
from src.optimization.planner import build_plan
from src.scenarios.demo import load_scenario
from src.config.ports import PORTS, DIVERSION_COST_H


def train(days: int = 90) -> CongestionModel:
    start = pd.Timestamp("2024-01-01")
    vessels = generate_all(days=days, start=start)
    tables = [
        build_training_table(vessels, simulate_port(vessels, pid, cfg, start, days * 24)[1], pid)
        for pid, cfg in PORTS.items()
    ]
    model = CongestionModel()
    model.fit(pd.concat(tables).sort_values("ts"))
    model.save()
    return model


def main():
    model = train()
    now, live, inbound = load_scenario()
    plan = build_plan(now, live, inbound, model, PORTS, DIVERSION_COST_H)

    print("=== KPIs (optimized vs FCFS baseline) ===")
    for k, v in plan["kpis"].items():
        print(f"  {k:24s} {v}")
    print("\n=== Recommended diversions ===")
    print(plan["recs"] if len(plan["recs"]) else "  None needed — all ports within capacity.")
    print("\n=== 72h schedule (first 10) ===")
    print(plan["schedule"].head(10).to_string(index=False))


if __name__ == "__main__":
    main()