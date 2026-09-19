"""Demo Scenario Ingestion and Loader.

Provides standardized scenario loading for offline evaluation and testing.
"""

from typing import Dict, Any, Tuple, List
import pandas as pd
from datetime import datetime, timedelta

from src.data.generator import generate_scenario, Vessel, Berth, Crane, PortSpec
from src.config.ports import PORT_CLUSTERS, DEFAULT_PORTS, get_live_state


def load_scenario(
    cluster: str = "india",
    scenario_name: str = "normal",
    num_vessels: int = 20,
    add_burst: bool = False,
) -> Dict[str, Any]:
    """Load a fully structured simulation scenario package."""
    scenario = generate_scenario(
        scenario=scenario_name,
        num_vessels=num_vessels,
        cluster=cluster,
    )
    
    if add_burst:
        # Inject sudden arrival surge of 4 priority vessels
        base_vessels = scenario["vessels"]
        burst_vessels = [
            Vessel(
                vessel_id=f"BST-{i+1:03d}",
                vessel_name=f"MV Priority Surge {i+1}",
                arrival_time=round(1.5 + (i * 0.8), 2),
                estimated_arrival_time=round(1.5 + (i * 0.8), 2),
                service_duration_h=12.0,
                cargo_volume=14500.0,
                priority=1,
                vessel_length_m=340.0,
                vessel_draft_m=12.5,
                required_cranes=3,
                origin_port="P3",
                destination_port="P1",
                preferred_port="P1",
                status="scheduled",
            )
            for i in range(4)
        ]
        scenario["vessels"] = sorted(base_vessels + burst_vessels, key=lambda v: v.arrival_time)

    return scenario


def load_scenario_as_dataframe(cluster: str = "india", num_vessels: int = 20) -> pd.DataFrame:
    """Load scenario vessel fleet formatted as a pandas DataFrame."""
    sc = load_scenario(cluster=cluster, num_vessels=num_vessels)
    rows = [v.__dict__ for v in sc["vessels"]]
    return pd.DataFrame(rows)


if __name__ == "__main__":
    sc = load_scenario()
    print(f"Loaded demo scenario with {len(sc['vessels'])} vessels across {len(sc['ports'])} ports.")