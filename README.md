🚢 PortIQ — AI Port Manager: Congestion Prediction & 72-Hour Operations Planner
👥 Team
Field	Value
Team Name	Elite
Track	AI / Open
Team Lead  Deep Tandel — 24it098@charusat.edu.in
Members	Harsh Jethva , Dax Chauhan , Muliak Vaghela 
🎯 Problem Statement
Ports regularly face situations where 100+ cargo ships wait to enter while berths, cranes,and yard space remain limited. Port operators still manage these resources manually withspreadsheets, so congestion is discovered only after ships are already queued — wastingfuel, money, and time for shipping lines and ports alike.

💡 Solution
We built an AI port manager that acts like "Google Maps for ships + an AI port manager."It predicts congestion up to 72 hours ahead (ML), recommends diverting ships toalternate ports before queues form, optimally assigns berths and cranes (constraintoptimization), and generates a supervisor-ready 72-hour operating plan — turningreactive spreadsheet management into proactive, prescriptive decision-making.

✨ Key Features
🔮 Congestion prediction: Gradient-boosting model forecasts waiting-ship queue perport in 6-hour buckets over the next 72h, classified LOW / MEDIUM / HIGH using ETAschedules, berth occupancy, crane utilization, and historical lags.
🔀 Alternate-route recommendations: When Port A is predicted to overload, the routerselects which inbound ships to divert to Port B (checking berth compatibility, extrasteaming cost, and destination-port slack) — with a human-readable reason for each call.
⚙️ Berth & crane optimization: Google OR-Tools CP-SAT solves the berth allocation +quay crane assignment problem — respecting berth length/depth limits, one-ship-per-berth,and shared crane capacity. Waiting beyond the 12h service target is a weighted penalty(soft constraint), so a feasible plan always exists even under overload.
📅 72-hour operations planner: Full schedule (ship → berth → cranes → start/end),congestion forecast, diversions, and KPIs — visualized as a Gantt chart and exportable as CSV.
🧪 What-if analysis: Live dashboard controls to simulate crane outages, weatherslowdowns, and arrival bursts — the plan re-optimizes instantly.
📊 Measurable impact: Compares the AI plan against a FCFS "spreadsheet" baseline andreports the improvement in average vessel waiting time (observed: [XX] % in demo scenario).
🛠️ Tech Stack
Category	Technologies
Languages	Python 3.10–3.12
ML / Optimization	scikit-learn (HistGradientBoosting), Google OR-Tools (CP-SAT)
Frameworks	Streamlit, Plotly
Data	pandas, NumPy; joblib (model artifacts); calibrated port simulator for training data
IBM Technologies	[N/A — or list what you used]
Other	PowerShell/CI-ready CLI (python -m src.main one-command pipeline)
📁 Repository Structure
├── src/
│ ├── app/dashboard.py # Streamlit dashboard (forecast, Gantt, recommendations)
│ ├── config/ # settings + port/berth/crane definitions
│ ├── data/ # vessel schedule generation + ML feature builder
│ ├── models/ # congestion model + training script
│ ├── optimization/ # diversion router, CP-SAT berth/crane allocator, 72h planner
│ ├── scenarios/demo.py # demo scenario (arrival burst, live port state)
│ └── simulation/port_sim.py # FCFS port simulator (training data + KPI baseline)
├── docs/ # problem-statement, solution-overview, architecture, setup-guide
├── demo/
│ ├── screenshots/ # dashboard screenshots
│ ├── demo-video-link.txt
│ └── live-demo-url.txt
├── presentation/
├── check_structure.py # project layout validator
├── requirements.txt
└── README.md

text


---

## ⚡ How to Run

```bash
# 1. Clone the repo
git clone https://github.com/harsh-jethva/bob-ai-hackathon-Elite.git
cd bob-ai-hackathon-Elite

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full pipeline (generates data, trains the congestion model,
#    optimizes the 72h plan, prints KPIs vs FCFS baseline)
python -m src.main

# 4. Open the dashboard (http://localhost:8501)
streamlit run src/app/dashboard.py
No environment variables required. Python 3.10–3.12 recommended (OR-Tools wheels).

🖥️ Demo
Artifact
Link
📹 Demo Video	See demo/demo-video-link.txt
🌐 Live Demo	See demo/live-demo-url.txt
🖼️ Screenshots	See demo/screenshots/
📊 Presentation	See presentation/

⚠️ Known Limitations
Training data is simulator-generated (calibrated to real port parameters: berth
dimensions, crane rates, vessel size mix, arrival peaks) — berth-level operational data
from real ports is not publicly available.
Congestion labels reflect a FCFS operating policy, so predictions are conditional on
"operating like today" — the optimizer then improves on exactly that baseline.
No live AIS feed yet — the system consumes a synthetic ETA feed; the upgrade path
(MarineCadastre AIS + port EDI) is documented in docs/architecture.md.
Single-shot planning — the demo generates one 72h plan; production use would
re-optimize on a rolling 6-hour horizon as new ETAs arrive.
🏅 What We're Most Proud Of
This is prescriptive analytics, not just prediction: an ML forecast feeds a
constraint-programming optimizer that makes the actual decisions (berth, crane, timing,
diversion), producing a plan a supervisor can act on immediately. We're especially proud
of two engineering decisions: (1) the 12-hour waiting target is a soft weighted penalty
rather than a hard rule — a rigid deadline makes schedules mathematically infeasible under
arrival bursts, which is exactly the trap real port planners fall into; (2) every
recommendation ships with its reasoning ("peak queue X vs Y berths at time T"), keeping the
human supervisor in control. And it runs end-to-end with a single command.
