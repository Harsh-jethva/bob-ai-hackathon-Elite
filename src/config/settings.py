"""Centralized configuration for PortPilot AI.

All configuration lives here (PRD Section 18) — visible in documentation,
not scattered across the codebase.
"""

from dataclasses import dataclass, field


@dataclass
class Settings:
    # Planning horizon
    planning_horizon_hours: int = 72
    planning_start_hour: int = 0

    # Solver
    solver_time_limit_seconds: int = 5
    solver_workers: int = 8  # 8 parallel workers for CP-SAT
    solver_feasible_acceptable: bool = True

    # Congestion thresholds (queue length fraction of berth capacity)
    congestion_low: float = 0.3
    congestion_medium: float = 0.6
    congestion_high: float = 0.85

    # Alternative-port scoring weights (must sum to 1.0)
    alt_port_weights: dict = field(default_factory=lambda: {
        "expected_delay": 0.30,
        "feasibility": 0.25,
        "diversion_cost": 0.20,
        "congestion_risk": 0.15,
        "reliability": 0.10,
    })

    # Random seed for reproducibility
    random_seed: int = 42

    # Data mode
    data_mode: str = "synthetic"  # synthetic | historical | live

    # Live Data Stream Configuration
    live_polling_interval_s: int = 300
    live_cache_ttl_s: int = 60
    ais_provider: str = "auto"  # auto | spire | marinetraffic | aishub | simulated_live
    ais_api_key: str = ""
    tos_endpoint: str = ""
    tos_api_key: str = ""
    weather_provider: str = "open-meteo"  # open-meteo | noaa | mock
    live_port_coordinates: dict = field(default_factory=lambda: {
        "P1": {"name": "Port Alpha (Mumbai / West Coast)", "lat": 18.95, "lon": 72.85},
        "P2": {"name": "Port Beta (Singapore / Strait)", "lat": 1.29, "lon": 103.85},
        "P3": {"name": "Port Gamma (Rotterdam / North Sea)", "lat": 51.92, "lon": 4.48},
    })

    # Fallback policy when solver fails
    fallback_policy: str = "fcfs"  # fcfs | defer

    # Maximum wait threshold for alerting (hours)
    max_wait_threshold_h: float = 24.0

    # Demo data
    default_num_vessels: int = 20
    default_num_ports: int = 3
    default_berths_per_port: int = 3
    default_cranes_per_port: int = 5

    # Streamlit
    dashboard_title: str = "PortPilot AI — Explainable Port Congestion & 72-Hour Planning"
    demo_data_banner: str = "⚠️ DEMO DATA — NOT REAL-TIME PORT DATA"
    live_data_banner: str = "🟢 LIVE OPERATIONAL STREAM — REAL-TIME INGESTION ACTIVE"


settings = Settings()
