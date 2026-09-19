# 🚢 PortPilot AI — Intelligent Port Operations & Congestion Manager

### Container Congestion Prediction, Priority Optimization & 72-Hour Port Operations Planner

> **PortPilot AI transforms reactive port management into proactive, AI-powered decision-making by combining predictive machine learning with prescriptive mixed-integer constraint optimization and cargo-weighted dynamic priority scheduling.**

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

Port operators currently manage these resources using manual spreadsheets, First-Come First-Served (FCFS) heuristics, and reactive radio communications. Consequently, congestion is identified only after ships have already formed costly offshore queues, leading to massive demurrage penalties ($50k–$100k/day per vessel), excessive fuel burn emissions, spoilage of time-sensitive cold-chain/pharma cargo, and global supply chain delays.

---

## 💡 Solution

We built **PortPilot AI**, an intelligent decision-support system acting as **"Google Maps for ships + an AI terminal operations planner."**

The platform:
1. **Forecasts waiting-ship queues** across a rolling 72-hour horizon using gradient-boosted machine learning.
2. **Evaluates cargo-weighted dynamic priority** across vessel laycans, perishable cargo valuations, crane requirements, and demurrage risks.
3. **Solves the Continuous Berth Allocation Problem (BAP) and Quay Crane Assignment** using Google OR-Tools CP-SAT constraint programming.
4. **Recommends multi-criteria alternative port diversions** factoring in port tariffs, pilotage/tug fees, crane hourly rates, and diversion penalty models.
5. **Quantifies financial cost savings** between Priority-Optimized vs. FCFS baselines in real time.

---

## ✨ Key Features

1. **🔮 72-Hour Congestion Predictor:** Rolling ML forecasts that predict waiting-ship queues in 6-hour buckets with clear contributing factor explanations (arrival surges, crane deficits, weather delays).
2. **💎 Dynamic Multi-Factor Priority Engine ($P_1, P_2, P_3$):** Mathematically computes a composite priority score ($0–100$) based on cargo value density, laycan urgency, crane demand intensity, and hourly demurrage risk to prioritize critical cold-chain/pharma vessels over flexible dry bulk.
3. **💰 Real-Time Profit & Cost Savings Benchmark:** Automatically calculates itemized cost deltas between Priority Optimizer and FCFS Baseline, including avoided demurrage, charter OPEX savings, inventory holding cost reductions, and $P_1$ urgent wait reductions ($100k–$500k+ saved per scenario).
4. **📊 Dual Comparative Analytics & Gantt Schedules:** Side-by-side comparative visualizations featuring itemized Schedule Cost Breakdown charts, Average Wait Time by Priority Tier, and dual interactive Gantt charts (Priority vs FCFS).
5. **🔀 Target Port Optimizer & Tariff/Penalty Matrix:** Regional matrix comparing alternative ports with port dues, pilotage/tug fees, crane rates, congestion surcharges, and TEU diversion penalties to compute optimal net financial diversion recommendations.
6. **🧪 What-If Stress Simulator:** Interactive cockpit testing operations under simulated storm delays, crane outages, and sudden cargo surges.

---

## 🛠️ Tech Stack & Architecture

- **Core Languages & Runtime:** Python 3.10+
- **Optimization & Constraint Programming:** Google OR-Tools (CP-SAT Solver with 8 parallel worker threads)
- **Machine Learning & Analytics:** Scikit-Learn, LightGBM, Pandas, NumPy, Joblib
- **User Interface & Visualizations:** Streamlit, Plotly Express & Graph Objects, Altair
- **Data Ingestion & Telemetry:** REST APIs, Open-Meteo Weather API, Live AIS Feed & TOS Connectors
- **AI Development & Pair Programming:** IBM Bob
- **Testing & Quality Assurance:** Python Unittest Suite (28 automated unit & integration tests)

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

# 6. Run the automated test suite (28 tests)
python -m unittest discover -s tests -v
```

For complete configuration and environment variable details, see [`docs/setup-guide.md`](docs/setup-guide.md).

---

## 🎥 Demo & Artifacts

- **Demo Video:** [YouTube Video Link](https://youtu.be/C2tQi5it9e0)
- **Live Deployment:** [PortPilot AI Streamlit Cloud App](https://bob-ai-hackathon-elite-portpilot-ai.streamlit.app/) (Reference: [`demo/live-demo-url.txt`](demo/live-demo-url.txt))
- **Slide Deck:** [`presentation/PortPilot_AI_Operations_Control.pdf`](presentation/PortPilot_AI_Operations_Control.pdf)
- **Application Screenshots:** Located in [`demo/screenshots/`](demo/screenshots/):
  - `01-home-dashboard.png` — Multi-port executive overview & live MetOcean weather telemetry
  - `02-congestion-optimizer.png` — Priority engine, cost savings cards & dual Gantt schedules
  - `03-berth-gantt-schedule.png` — Constraint-optimized 72-hour Berth & Crane Gantt schedule
  - `04-what-if-scenarios.png` — Target port optimizer & regional tariff penalty matrix
  - `05-operational-alerts-hub.png` — Operational alerts hub (safety triggers, wind gusts & congestion warnings)
  - `06-schedule-export-diagnostics.png` — Schedule CSV/JSON export & CP-SAT solver diagnostics

---

## 🔍 Priority Algorithm & Mathematical Formulation

### 1. Composite Priority Score Calculation ($0–100$)

$$\text{Score} = w_1 \cdot C_{\text{norm}} + w_2 \cdot L_{\text{urgency}} + w_3 \cdot D_{\text{risk}} + w_4 \cdot K_{\text{demand}}$$

- **Cargo Value ($C_{\text{norm}}$):** High-value refrigerated/pharma cargo receives maximum weight vs. low-value bulk cargo.
- **Laycan Urgency ($L_{\text{urgency}}$):** Tight departure/contractual windows increase score exponentially as the deadline approaches.
- **Demurrage Risk ($D_{\text{risk}}$):** Higher contracted hourly detention rates elevate vessel priority to prevent steep financial penalties.
- **Crane Efficiency ($K_{\text{demand}}$):** Balances crane demand against terminal capacity to optimize throughput.

### 2. Tier Classification
- **Priority 1 (P1 - Urgent):** Score $\ge 70$ (Cold-chain, pharmaceuticals, express freight, narrow laycans).
- **Priority 2 (P2 - Standard):** Score $40 - 69$ (Standard containerized cargo, average handling window).
- **Priority 3 (P3 - Flexible):** Score $< 40$ (Dry bulk, raw materials, flexible delivery terms).

---

## 🏆 What We're Most Proud Of

We are most proud of **closing the loop between predictive forecasting, dynamic cargo prioritization, and prescriptive mathematical optimization**.

Unlike conventional platforms that merely display vessel positions or passive delay warnings, PortPilot AI uses **Google OR-Tools CP-SAT constraint programming** combined with a **financial priority engine** to compute conflict-free berth and crane allocation schedules in seconds — delivering **30%–55% reductions in vessel wait times** and **over \$100k–\$500k in demurrage and OPEX savings** per operational cycle.
