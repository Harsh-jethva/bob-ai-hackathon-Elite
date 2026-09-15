# Presentation Slide Deck

This directory contains the presentation deck for **PortPilot AI: Explainable Port Congestion Prediction & 72-Hour Planning System** developed by **Team Elite** for the **IBM BoB AI Innovation Hackathon 2026** (AI Track).

---

## 📑 Slide Deck Files

- **Primary Slide Deck (PDF):** [`PortPilot_AI_Operations_Control.pdf`](PortPilot_AI_Operations_Control.pdf)

---

## 👥 Team Information

- **Team Name:** Elite
- **Track:** AI Track
- **Hackathon:** IBM BoB AI Innovation Hackathon 2026
- **Team Members:** Harsh, Dax, Maulik, Deep

---

## 🎯 Slide Structure (13 Slides)

1. **Slide 1: Title & Overview**
   - Project: *PortPilot AI — Explainable Port Congestion Prediction & 72-Hour Planning System*
   - Team Elite members, track details, and hackathon banner.

2. **Slide 2: Port Congestion and Inefficient Resource Planning**
   - Core operational bottlenecks: Increasing vessel queues, unpredictable service durations, berth/crane constraints, reactive short-term planning, and vessel handling delays.
   - Core problem statement and industry urgency.

3. **Slide 3: Problem Impact & Main Challenge**
   - The vicious cycle of delayed planning, reduced efficiency, cargo delays, long queues, and escalating operating costs.
   - *Main Challenge:* How port operators can predict congestion and generate actionable operational plans for the rolling 72-hour window.

4. **Slide 4: PortPilot AI Solution Overview**
   - AI-powered decision support system linking predictive congestion analytics with mathematical constraint optimization.
   - Cockpit feature overview: Berth/crane optimization, FCFS comparison, alternative-port routing, and what-if simulation.

5. **Slide 5: Project Objectives**
   - **Predictive Intelligence:** Port congestion prediction and root-cause identification.
   - **Resource Optimization:** Vessel waiting time reduction, berth assignment optimization, and crane capacity allocation.
   - **Decision Support:** 72-hour rolling plan, FCFS benchmarking, alternative decisions, and explainable recommendations.

6. **Slide 6: How PortPilot AI Works (5-Step Pipeline)**
   - **Step 1 — Input Data:** Vessel arrival, service duration, berths, cranes, port capacity.
   - **Step 2 — Congestion Analysis:** Queue estimation, capacity assessment, and explainable classification.
   - **Step 3 — Optimization:** Constraint programming for berth assignment, crane allocation, and conflict resolution.
   - **Step 4 — 72-Hour Planning:** Timeline generation, vessel scheduling, and deferred vessel identification.
   - **Step 5 — Decision Dashboard:** Real-time KPIs, operational alerts, schedule visualizations, and simulations.

7. **Slide 7: PortPilot AI Features**
   - 10 signature capabilities: Congestion Prediction, Explainable Analysis, Berth Allocation Optimization, Crane Allocation, Rolling 72-Hour Planning, FCFS Baseline Comparison, Alternative-Port Recommendations, What-If Simulation, Operational Alerts, and Interactive Streamlit Dashboard.

8. **Slide 8: Technology Used**
   - Stack: Python, Pandas, Machine Learning Components, Google OR-Tools CP-SAT, Streamlit, YAML Configuration, and Data Visualization Tools.
   - *Core Approach:* AI identifies congestion conditions, while optimization determines how available resources should be used.

9. **Slide 9: System Architecture**
   - Architectural flow from multi-source vessel/port data through processing, analysis, dual optimization engines, benchmarking, and interactive reporting.
   - *Main Design Principle:* Convert congestion predictions into feasible, explainable, and actionable operational plans.

10. **Slide 10: Berth and Crane Allocation Engine**
    - Inputs & Constraints: Arrival times, service durations, berth availability, scheduling horizon, crane capacities, and conflict avoidance.
    - Optimization Goals: Minimize waiting time, maximize berth utilization, improve crane efficiency, schedule more vessels, and guarantee feasible schedules.

11. **Slide 11: Understanding Why Congestion Happens (Explainability)**
    - Multi-factor evaluation: Queue size, berth/crane ratios, throughput, and resource saturation.
    - Multi-tier classification (LOW, MEDIUM, HIGH) with human-readable operational explanations for port supervisors.

12. **Slide 12: Short-Term Operational Planning (72-Hour Window)**
    - Rolling 72-hour scheduling matrix displaying berth allocations, crane workloads, scheduled service intervals, and deferred vessel tracking.
    - Proactive visibility to resolve bottleneck surges before compounding delays occur.

13. **Slide 13: Optimized Planning vs. First-Come, First-Served (FCFS)**
    - Side-by-side comparative analysis: Reactive arrival-based queuing vs. proactive constraint-optimized packing.
    - Demonstrates dramatic reductions in idle berth time and waiting hours alongside higher 72-hour vessel throughput.
