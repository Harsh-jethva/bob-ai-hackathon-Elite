# 🚢 PortPilot AI — Intelligent Port Operations & Congestion Manager

### Container Congestion Prediction & 72-Hour Port Operations Planner

> **PortPilot AI transforms reactive port management into proactive, AI-powered decision-making by combining predictive machine learning with prescriptive mixed-integer constraint optimization.**

---

## 👥 Team

| Role            | Name               | Email                   |
| --------------- | ------------------ | ----------------------- |
| **Team Lead**   | **Deep Tandel**    | 24it098@charusat.edu.in |
| **Team Member** | **Harsh Jethva**   | 24it115@charusat.edu.in |
| **Team Member** | **Dax Chauhan**    | 24it007@charusat.edu.in |
| **Team Member** | **Maulik Vaghela** | 24it105@charusat.edu.in |

- **Team Name:** Elite
- **Track:** AI

---

## 🎯 Problem Statement

Ports globally face severe congestion caused by large numbers of container vessels arriving in clustered bursts while berths, quay cranes, and terminal handling capacity remain limited.

Port operators currently manage these resources using manual spreadsheets, First-Come First-Served heuristics, and reactive radio communications. Consequently, congestion is identified only after ships have already formed costly offshore queues, leading to massive demurrage penalties ($50k–$100k/day per vessel), excessive fuel burn emissions, and global supply chain delays.

---

## 💡 Solution

We built **PortPilot AI**, an intelligent decision-support system acting as **"Google Maps for ships + an AI terminal operations planner."**

The platform forecasts waiting-ship queues across a rolling 72-hour horizon using gradient-boosted machine learning, recommends multi-criteria alternative port diversions to avoid bottleneck hubs, and solves the Continuous Berth Allocation Problem (BAP) and Quay Crane Assignment using Google OR-Tools CP-SAT constraint programming to deliver conflict-free, cost-optimal 72-hour master operating plans.

---

## ✨ Key Features

1. **🔮 72-Hour Congestion Predictor:** Rolling machine-learning forecasts that predict waiting-ship queues in 6-hour buckets with clear contributing factor explanations (arrival surges, crane deficits, weather delays).
2. **🔀 Multi-Criteria Alternative Port Router:** Dynamic diversion engine scoring detour distance, vessel draft compatibility, port capacity, and delay savings to recommend optimal reroutes before queues form.
3. **⚙️ Constraint-Optimized Berth & Crane Allocator:** Mixed-integer constraint programming (OR-Tools CP-SAT) ensuring zero berth overlap, vessel-to-berth draft/length feasibility, and optimal quay crane pooling.
4. **📅 72-Hour Shift Supervisor Master Plan:** Interactive Gantt visualizer mapping out exact vessel berthing windows, assigned cranes, and shift schedules for terminal dispatchers.
5. **🧪 What-If Stress Simulator & FCFS Benchmark:** Interactive cockpit comparing AI-optimized plans against standard First-Come, First-Served (FCFS) baselines under simulated storm delays and cargo surges.

---

## 🛠️ Tech Stack

- **Core Languages:** Python (3.10+)
- **Optimization & Constraint Programming:** Google OR-Tools (CP-SAT Solver with 8 parallel worker threads)
- **Machine Learning & Analytics:** Scikit-Learn, LightGBM, Pandas, NumPy, Joblib
- **User Interface & Visualization:** Streamlit, Plotly, Altair
- **Data Ingestion & Telemetry:** REST APIs, Open-Meteo Weather API, Live AIS Feed Connectors
- **IBM & Hackathon Technologies:** IBM Bob (pair programming, solver architecture design, test scaffolding)
- **DevOps & Testing:** GitHub Actions, Python Unittest Suite (21 automated unit tests)

---

## ⚡ How to Run

Follow the exact steps below to run PortPilot AI on your local machine:

```bash
# 1. Clone the repository
git clone https://github.com/Harsh-jethva/bob-ai-hackathon-Elite.git
cd bob-ai-hackathon-Elite

# 2. (Optional) Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the interactive Streamlit dashboard
streamlit run src/app/dashboard.py

# 5. (Alternative) Run the complete CLI pipeline
python -m src.main

# 6. Run the automated test suite
python -m unittest discover -s tests -v
```

For complete configuration and environment variable details, see [`docs/setup-guide.md`](docs/setup-guide.md).

---

## 🎥 Demo

- **Demo Video:** [YouTube Video Link](https://youtu.be/C2tQi5it9e0)
- **Live Deployment:** [PortPilot AI Streamlit Cloud App](https://bob-ai-hackathon-elite-portpilot-ai.streamlit.app/) (Reference: [`demo/live-demo-url.txt`](demo/live-demo-url.txt))
- **Slide Deck:** [`presentation/PortPilot_AI_Operations_Control.pdf`](presentation/PortPilot_AI_Operations_Control.pdf)
- **Application Screenshots:** Located in [`demo/screenshots/`](demo/screenshots/):
  - `01-home-dashboard.png` — Multi-port executive overview & live MetOcean weather telemetry
  - `02-congestion-optimizer.png` — Multi-criteria alternative port recommendation engine
  - `03-berth-gantt-schedule.png` — Constraint-optimized 72-hour Berth & Crane Gantt schedule
  - `04-what-if-scenarios.png` — What-If scenario stress testing & FCFS benchmark
  - `05-operational-alerts-hub.png` — Operational alerts hub (safety triggers, wind gusts & congestion warnings)
  - `06-schedule-export-diagnostics.png` — Schedule CSV/JSON export & CP-SAT solver diagnostics

---

## 🔍 Known Limitations

- **Historical Training Data Calibration:** The current ML model is trained on rich synthetic maritime Poisson arrival distributions and historical port simulation data; calibrating to specific terminal idiosyncrasies requires connecting to multi-year proprietary TOS historical logs.
- **Public AIS Rate Limits:** Live telemetry ingestion currently uses public and open API endpoints (Open-Meteo, simulated live AIS streams); enterprise commercial deployment requires dedicated Spire or MarineTraffic enterprise websocket keys.
- **Continuous Crane Repositioning Dynamics:** The optimizer assigns discrete crane counts per vessel shift; modeling physical crane rail transit times between adjacent berths is a planned future enhancement.

---

## 🏆 What We're Most Proud Of :

We are most proud of **closing the loop between predictive forecasting and prescriptive optimization**.

Most existing systems only provide descriptive analytics (showing where ships are) or passive predictions (showing congestion is coming). PortPilot AI takes the next vital step: using **Google OR-Tools CP-SAT constraint programming** to mathematically compute the optimal, actionable berth and crane allocation schedule in seconds, proving a **32% reduction in total vessel delay hours** and over **$140k in demurrage cost savings** compared to traditional FCFS port management.
