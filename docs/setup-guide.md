# Setup & Reproduction Guide

> **This guide provides exact, step-by-step instructions to set up, test, and run PortPilot AI locally.**

---

## 1. Prerequisites

Ensure you have the following software installed on your machine:

- **Python:** Version `3.10`, `3.11`, `3.12`, or `3.13`
- **Git:** Version `2.30+`
- **Pip:** Package installer for Python (`python -m pip install --upgrade pip`)
- **Web Browser:** Modern browser (Chrome, Firefox, Edge, Safari) for the Streamlit dashboard

---

## 2. Environment Variables

Create your local `.env` configuration by copying `.env.example`:

```bash
# On Linux / macOS / Git Bash:
cp .env.example .env

# On Windows (Command Prompt):
copy .env.example .env

# On Windows (PowerShell):
Copy-Item .env.example .env
```

### Configuration Variables Reference:

| Variable | Default Value | Description | Required |
|---|---|---|---|
| `DATA_MODE` | `synthetic` | Ingestion mode: `synthetic` \| `historical` \| `live` | No (defaults to synthetic) |
| `AIS_PROVIDER` | `auto` | AIS feed source: `auto` \| `spire` \| `marinetraffic` \| `aishub` \| `simulated_live` | No |
| `AIS_API_KEY` | *(empty)* | Optional API key for live AIS data provider | No |
| `TOS_ENDPOINT` | *(empty)* | Optional endpoint for Terminal Operating System | No |
| `TOS_API_KEY` | *(empty)* | Optional API key for TOS integration | No |
| `WEATHER_PROVIDER` | `open-meteo` | Weather API: `open-meteo` \| `noaa` \| `mock` | No |
| `SOLVER_TIME_LIMIT_SECONDS` | `5` | Maximum CP-SAT solver optimization search time | No |
| `SOLVER_WORKERS` | `8` | Parallel search threads for OR-Tools CP-SAT | No |

---

## 3. Installation

Clone the repository and install the project dependencies:

```bash
# 1. Clone the repository
git clone https://github.com/Harsh-jethva/bob-ai-hackathon-Elite.git
cd bob-ai-hackathon-Elite

# 2. (Optional but recommended) Create and activate a virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
.venv\Scripts\activate.bat

# 3. Install all required dependencies
pip install -r requirements.txt
```

---

## 4. Running the Application

### Option A: Launch Interactive Dashboard (Recommended)

To start the full PortPilot AI operations cockpit and simulation dashboard:

```bash
streamlit run src/app/dashboard.py
```

Once started, open your web browser at:
👉 **`http://localhost:8501`**

### Option B: Run End-to-End Pipeline via Main Entry Point

To run the complete data generation, model training, CP-SAT optimization, and terminal summary via CLI:

```bash
python -m src.main
```

### Option C: Retrain the Congestion ML Model

To generate fresh training data across historical simulation runs and train the LightGBM/GBDT model:

```bash
python -m src.models.train
```

---

## 5. Running Automated Unit Tests

Verify the complete test suite across optimization, simulation, features, and live connectors:

```bash
# Run all tests using Python's built-in unittest framework:
python -m unittest discover -s tests -v
```

**Expected output:**
```text
Ran 21 tests in ~11s
OK
```

---

## 6. How to Verify It Is Working

1. **Dashboard Check:** When you open `http://localhost:8501`, you should see the **PortPilot AI** dashboard header with multi-port cards for Port Alpha, Port Beta, and Port Gamma.
2. **Congestion Forecast Check:** Navigate to the **72-Hour Congestion Forecast** tab to verify that queue lengths and risk levels are dynamically displayed.
3. **Berth Allocation Gantt:** Navigate to the **Berth & Crane Schedule** tab to inspect the interactive timeline showing conflict-free vessel allocations.
4. **What-If Scenario Check:** Use the sidebar sliders to inject severe weather or arrival surges, then observe real-time recalculation of the schedule and KPI deltas.

---

## 7. Troubleshooting Guide

| Issue / Error | Root Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'ortools'` | Dependencies not installed in current Python environment. | Run `pip install -r requirements.txt` within your active virtual environment. |
| `Address already in use: 8501` | Another Streamlit process is running on port 8501. | Run on a different port: `streamlit run src/app/dashboard.py --server.port 8502` |
| `ImportError: cannot import name 'main' from 'src.app.dashboard'` | PYTHONPATH not set to project root. | Always run commands from the repository root directory (e.g., `python -m src.main`). |
| Solver returns fallback FCFS plan | Constraint problem too tight or time limit exceeded under extreme surge. | Increase `SOLVER_TIME_LIMIT_SECONDS=10` in `.env` or adjust vessel arrival spacing. |
| `ConnectionError` with live weather | No internet connection for Open-Meteo API. | The connector automatically falls back to synthetic weather data. No action required. |
