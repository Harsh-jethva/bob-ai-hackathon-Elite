# Solution Overview

## 1. What We Built

**PortPilot AI** is an AI-powered maritime operations decision-support platform designed to act like **"Google Maps for ships + an AI terminal operations planner."**

Instead of merely visualizing vessel GPS locations or reacting when anchorage queues have already formed, PortPilot AI combines **machine learning forecasting** with **mixed-integer constraint programming (OR-Tools CP-SAT)** to predict congestion up to 72 hours in advance and generate optimal, conflict-free berth and crane allocation schedules.

---

## 2. How It Works: Step-by-Step Core Mechanism

```
[ Multi-Source Data Stream ]
 (AIS GPS Telemetry + TOS Berth Status + Marine Weather Forecasts)
               ↓
[ Rolling Feature Engineering Pipeline ]
 (ETA Windows, Berth Occupancy, Crane Workloads, Arrival Density)
               ↓
[ Predictive ML Engine (Gradient Boosting) ]
 (Forecasts 6-hour Queue Lengths & Risk Levels across 72h)
               ↓
  ┌─────────────────────────────────────────────────┐
  │         Decision & Prescriptive Layer           │
  ├────────────────────────┬────────────────────────┤
  │  Alternative Port      │  OR-Tools CP-SAT       │
  │  Diversion Router      │  Berth & Crane Solver  │
  └────────────────────────┴────────────────────────┘
               ↓
[ Interactive Operations Cockpit & 72-Hour Gantt Visualizer ]
 (Actionable Schedule, Shift Supervisor Assignments & What-If Simulator)
```

### Core Workflow:

1. **Multi-Source Data Ingestion:** Ingests vessel telemetry (AIS), terminal capacity (berth counts, length, draft limits, crane speeds), and marine weather conditions (wind, swell) via pluggable streaming connectors.
2. **Predictive Congestion Forecasting:** Computes rolling operational lag features and feeds them into a trained Gradient Boosting model that forecasts expected waiting ship queues for each port in **6-hour discrete intervals across the next 72 hours**, categorizing risk as `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.
3. **Multi-Criteria Vessel Rerouting:** If a destination port exceeds severe congestion thresholds, the engine computes alternative regional port diversions by scoring detour transit costs, port handling capacity, expected waiting times, and delay reduction.
4. **Mixed-Integer Constraint Optimization (CP-SAT):** Evaluates all scheduled vessel arrivals and solves the Continuous Berth Allocation Problem (BAP) and Quay Crane Assignment (QCA) to find the global minimum turnaround time while enforcing physical constraints (zero berth overlap, draft/length compatibility, crane capacity limits).
5. **72-Hour Operations Master Plan:** Outputs an interactive Gantt chart schedule for shift supervisors, complete with vessel berthing windows, assigned quay cranes, and quantitative KPI delta comparisons against an FCFS baseline.

---

## 3. What Makes PortPilot AI Different

| Feature | Naive / Traditional Systems | PortPilot AI |
|---|---|---|
| **Horizon** | Reactive (current day or current shift) | **Proactive 72-Hour Rolling Horizon** |
| **Logic** | Static First-Come, First-Served (FCFS) | **Mathematical Constraint Optimization (CP-SAT)** |
| **Congestion Management** | Queuing ships offshore at anchor | **Multi-Criteria Intelligent Port Diversion** |
| **Explainability** | Black-box or manual guesswork | **Feature-Level Contributing Factor Explanations** |
| **Decision Support** | Static spreadsheet tables | **Interactive Gantt Cockpit & What-If Stress Testing** |

---

## 4. Key Design Decisions

| Design Decision | Technical Rationale |
|---|---|
| **OR-Tools CP-SAT Solver** | The Berth Allocation Problem with crane limits is NP-hard. CP-SAT finds provably optimal or high-quality feasible schedules in < 5 seconds using parallel multi-core search. |
| **6-Hour Rolling Time Buckets** | Strikes the ideal balance between actionable granularity for port shift supervisors (8h/12h shifts) and statistical stability for ML feature aggregation. |
| **Pluggable Ingestion Architecture** | Decouples data sources (`synthetic`, `historical`, `live`) so the system can run standalone for demos, offline simulations, or connected to real AIS streams. |
| **Graceful FCFS Fallback Policy** | In mission-critical port operations, if a solver timeout occurs under pathological conditions, the system immediately returns a validated FCFS fallback plan. |
| **Streamlit Interactive UI** | Enables zero-friction deployment with rich interactive Gantt charts, real-time what-if parameter sliders, and side-by-side KPI comparison views. |

---

## 5. IBM Technologies & AI Acceleration

- **IBM Bob Integration:** Utilized IBM Bob as an intelligent pair-programming assistant throughout the project lifecycle:
  - Co-designing the CP-SAT interval variable formulation and non-overlapping constraint models.
  - Generating synthetic vessel arrival datasets adhering to real-world maritime Poisson distribution patterns.
  - Constructing a 100% passing automated unit test suite covering optimization bounds, feature extraction, and simulation invariants.
- **Explainable AI Integration:** Modeled after enterprise AI principles to ensure every congestion prediction surfaces its primary contributing factors (e.g., arrival surge, crane deficit, severe weather) directly to terminal supervisors.
