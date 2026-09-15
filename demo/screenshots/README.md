# Screenshots Gallery

This directory contains application screenshots showing **PortPilot AI** (AI Port Manager & 72-Hour Operations Planner) in action.

---

## 📸 Screenshots Overview

| Screenshot | File | Description |
|---|---|---|
| **01** | [`01-home-dashboard.png`](01-home-dashboard.png) | **Executive Operations Cockpit** — Multi-port status cards for Port Alpha, Beta, and Gamma, average waiting time reduction metrics (-34%), berth utilization gauges, cumulative demurrage savings ($142k+), and vessel live traffic tracker. |
| **02** | [`02-congestion-optimizer.png`](02-congestion-optimizer.png) | **72-Hour Congestion Heatmap & Dynamic Rerouting** — Rolling horizon congestion forecasts across 6h/12h/24h buckets, paired with prescriptive vessel diversion recommendation ('Ever Titan' rerouted to save 18 hours with multi-criteria utility score breakdown). |
| **03** | [`03-berth-gantt-schedule.png`](03-berth-gantt-schedule.png) | **72-Hour Berth & Crane Gantt Schedule** — Constraint-optimized schedule assigning vessels to physical berths and quay cranes with zero overlap, optimal turnaround time, and shift supervisor assignment schedule. |
| **04** | [`04-what-if-scenarios.png`](04-what-if-scenarios.png) | **What-If Scenario Stress Testing & FCFS Baseline Comparison** — Interactive comparative analytics demonstrating delay reduction (-32%), idle time minimization (-45%), and crane productivity gains across severe weather and arrival surge scenarios. |

---

## 🖥️ Reproduction

To launch the live dashboard locally:
```bash
streamlit run src/app/dashboard.py
```
See [`docs/setup-guide.md`](../../docs/setup-guide.md) for full instructions.
