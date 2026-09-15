# Screenshots Gallery

This directory contains application screenshots showing **PortPilot AI** (AI Port Manager & 72-Hour Operations Planner) in action.

---

## 📸 Screenshots Overview

| Screenshot | File | Description |
|---|---|---|
| **01** | [`01-home-dashboard.png`](01-home-dashboard.png) | **Executive Operations Cockpit** — Multi-port status cards for Indian Major Ports (JNPT, Mundra, Cochin), Live MetOcean weather telemetry via Open-Meteo, active berth & crane capacity counters, and live stream status. |
| **02** | [`02-congestion-optimizer.png`](02-congestion-optimizer.png) | **Alternative Port Recommendation Engine** — Multi-criteria weighted scoring engine evaluating vessel draft/length compatibility, expected travel delays, diversion costs, and candidate port reliability scores. |
| **03** | [`03-berth-gantt-schedule.png`](03-berth-gantt-schedule.png) | **72-Hour Berth & Crane Allocation Schedule** — OR-Tools CP-SAT constraint-optimized berth allocation visualizer with priority metrics, solver wall-time, and FCFS baseline comparison controls. |
| **04** | [`04-what-if-scenarios.png`](04-what-if-scenarios.png) | **What-If Simulation Sandbox** — Interactive scenario stress testing allowing real-time parameter modifications (berth count, crane outages, weather disruptions) and dynamic pipeline re-execution. |
| **05** | [`05-operational-alerts-hub.png`](05-operational-alerts-hub.png) | **Operational Alerts Hub** — Severity-coded warning cards enforcing 5 mandatory fields (Severity, Entity, Trigger, Explanation, Recommended Action) for high congestion, crane shutoff risks, and weather events. |
| **06** | [`06-schedule-export-diagnostics.png`](06-schedule-export-diagnostics.png) | **Schedule Export & Solver Diagnostics** — One-click CSV/JSON schedule export buttons for operational terminal dispatch along with full OR-Tools CP-SAT solver diagnostic metadata. |

---

## 🖥️ Reproduction

To launch the live dashboard locally:
```bash
python -m streamlit run src/app/dashboard.py
```
See [`docs/setup-guide.md`](../../docs/setup-guide.md) for full setup and telemetry configuration instructions.
