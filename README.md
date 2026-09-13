# 🚢 PortIQ — AI Port Manager

### Container Congestion Prediction & 72-Hour Operations Planner

> **PortIQ transforms reactive port management into proactive, AI-powered decision-making.**

---

## 👥 Team Elite

| Role | Name | Email |
|---|---|---|
| Team Lead | **Deep Tandel** | 24it098@charusat.edu.in |
| Member | **Harsh Jethva** | 24it115@charusat.edu.in |
| Member | **Dax Chauhan** | 24it007@charusat.edu.in |
| Member | **Maulik Vaghela** | 24it105@charusat.edu.in |

**Track:** AI

---

## 🎯 Problem Statement

Ports regularly face situations where large numbers of cargo ships wait offshore while berths, cranes, and yard capacity remain limited.

Port operators often manage these resources using manual processes and spreadsheets. As a result, congestion may only become visible after vessels are already queued, leading to increased waiting time, fuel consumption, operational costs, and supply-chain delays.

The core challenge is to move from **reactive congestion management** to **predictive and prescriptive port operations**.

---

## 💡 Our Solution

### PortIQ — AI Port Manager

PortIQ acts like **"Google Maps for ships + an AI port manager."**

The platform combines machine learning, constraint optimization, simulation, and interactive visualization to help port operators make decisions before congestion becomes critical.

PortIQ:

- 🔮 Predicts congestion up to **72 hours ahead**
- 🔀 Recommends alternate ports when congestion is predicted
- ⚙️ Optimizes berth and quay-crane allocation
- 📅 Generates a complete **72-hour operating plan**
- 🧪 Provides what-if scenario analysis
- 📊 Compares AI-assisted planning against an FCFS baseline

The result is a system designed to support **proactive, prescriptive decision-making** rather than simply reporting congestion after it occurs.

---

# ✨ Key Features

## 🔮 1. Congestion Prediction

A gradient-boosting machine-learning model forecasts the expected waiting-ship queue for each port in **6-hour buckets across the next 72 hours**.

The model uses features such as:

- Vessel ETA schedules
- Berth occupancy
- Crane utilization
- Historical operational lags
- Vessel arrival patterns
- Port capacity

Predicted congestion is classified into:

```text
LOW
MEDIUM
HIGH



---

## ⚡ How to Run

```bash
# 1. Clone the repo
git clone https://github.com/Harsh-jethva/bob-ai-hackathon-Elite.git
cd bob-ai-hackathon-Elite

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full pipeline (generates data, trains the congestion model,
#    optimizes the 72h plan, prints KPIs vs FCFS baseline)
python -m src.main

# 4. Open the dashboard (http://localhost:8501)
streamlit run src/app/dashboard.py