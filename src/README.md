# Source Code Organization (`src/`)

This directory contains the entire source codebase for **PortPilot AI** (Container Congestion Predictor & 72-Hour Port Operations Planner).

---

## 📁 Directory Layout

```text
src/
├── config/                  # Centralized configuration & port catalog
│   ├── ports.py             # Port specifications, berth dimensions, and crane capacities
│   └── settings.py          # Global parameters, weights, solver limits, and defaults
│
├── data/                    # Data generation, feature engineering & live connectors
│   ├── generator.py         # Synthetic vessel schedule and operational data generator
│   ├── features.py          # Operational feature matrix builder for ML models
│   └── live/                # Live streaming telemetry connectors
│       ├── ais_connector.py     # Live AIS vessel tracking stream (Spire / MarineTraffic / AISHub)
│       ├── tos_connector.py     # Terminal Operating System (TOS) interface
│       ├── weather_connector.py # Marine weather and sea state API (Open-Meteo)
│       ├── transformer.py       # Raw stream normalization into standard Vessel domain objects
│       └── live_manager.py      # Unified live stream orchestration manager
│
├── models/                  # Machine learning prediction engine
│   ├── congestion_model.py  # Congestion forecasting, queue estimation & risk classification
│   └── train.py             # Model training, temporal validation split & metrics pipeline
│
├── simulation/              # Discrete-event port operations simulation
│   └── port_sim.py          # Continuous simulation engine for vessel arrivals, queues & servicing
│
├── optimization/            # Prescriptive optimization & constraint programming
│   ├── berth_allocator.py   # OR-Tools CP-SAT Mixed-Integer Berth & Quay Crane Allocation Solver
│   ├── router.py            # Multi-criteria alternative port diversion & scoring engine
│   └── planner.py           # 72-hour master operations plan generator & FCFS baseline comparison
│
├── scenarios/               # Stress testing and operational scenarios
│   └── demo.py              # Pre-configured scenarios (Storm Delay, Surge, Baseline)
│
├── app/                     # User interface layer
│   └── dashboard.py         # Streamlit multi-tab operations cockpit & interactive Gantt visualizer
│
├── .env.example             # Template for environment configuration
├── main.py                  # Primary application entry point
└── __init__.py
```

---

## 🚀 Key Modules & Responsibilities

- **`src/config/`**: Single source of truth for port layouts (Port Alpha, Port Beta, Port Gamma), berth constraints, and CP-SAT solver hyperparameters.
- **`src/data/`**: Generates high-fidelity maritime data, extracts rolling operational lag features, and interfaces with live AIS/TOS/Weather APIs.
- **`src/models/`**: Trains and evaluates Gradient Boosting models for 6-hour rolling waiting ship queue prediction across a 72-hour horizon.
- **`src/simulation/`**: Provides discrete-event simulation of port operations to generate realistic ground truth and benchmark heuristic policies.
- **`src/optimization/`**: Uses Google OR-Tools CP-SAT mixed-integer constraint programming to compute non-overlapping berth and quay crane schedules in seconds.
- **`src/app/`**: Delivers a rich, multi-tab Streamlit dashboard designed for port shift supervisors and dispatchers.
- **`src/main.py`**: Launches the complete end-to-end pipeline and starts the dashboard.
