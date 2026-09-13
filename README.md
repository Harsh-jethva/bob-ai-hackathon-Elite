# 🚢 PortIQ — AI Port Manager

### Container Congestion Prediction & 72-Hour Operations Planner

> **PortIQ transforms reactive port management into proactive, AI-powered decision-making.**

Ports can face severe congestion when large numbers of cargo ships wait offshore while berth, crane, and yard capacity remains limited. PortIQ predicts congestion before queues form, recommends alternate-port diversions, optimizes berth and crane allocation, and generates a supervisor-ready 72-hour operating plan.

---

## 👥 Team Elite

| Role | Name | Email |
|---|---|---|
| Team Lead | **Deep Tandel** | 24it098@charusat.edu.in |
| Member | **Harsh Jethva** | — |
| Member | **Dax Chauhan** | — |
| Member | **Maulik Vaghela** | — |

**Track:** AI

---

# 🎯 Problem Statement

Ports regularly face situations where large numbers of cargo ships wait offshore while berths, cranes, and yard capacity remain limited.

Port operators often manage these resources using manual processes and spreadsheets. As a result, congestion may only become visible after vessels are already queued, leading to increased waiting time, fuel consumption, operational costs, and supply-chain delays.

The core challenge is to move from **reactive congestion management** to **predictive and prescriptive port operations**.

---

# 💡 Our Solution

## PortIQ — AI Port Manager

PortIQ acts like **"Google Maps for ships + an AI port manager."**

The platform combines machine learning, constraint optimization, simulation, and interactive visualization to help port operators make decisions before congestion becomes critical.

PortIQ:

1. 🔮 Predicts port congestion up to **72 hours ahead**
2. 🔀 Recommends alternate ports when congestion is predicted
3. ⚙️ Optimizes berth and quay-crane allocation
4. 📅 Generates a complete **72-hour operating plan**
5. 🧪 Provides what-if scenario analysis
6. 📊 Compares AI-assisted planning against a traditional FCFS baseline

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
