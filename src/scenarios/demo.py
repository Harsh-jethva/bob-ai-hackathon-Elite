import pandas as pd
from datetime import timedelta
from src.data.generator import generate_vessels
from src.config.ports import PORTS

def load_scenario(seed=11, add_burst=True):
    now = pd.Timestamp("2024-04-01 09:00")
    inbound = pd.concat([
        generate_vessels("PORT_A", now - timedelta(hours=12), 5, PORTS["PORT_A"]["base_arrivals_per_day"], seed),
        generate_vessels("PORT_B", now - timedelta(hours=12), 5, PORTS["PORT_B"]["base_arrivals_per_day"], seed + 1),
    ])
    if add_burst:  # inject the "11 AM pile-up" from the problem statement
        burst = [dict(vessel_id=f"PORT_A-BST{i}", name=f"MV Burst-{i}", port="PORT_A",
                      eta=now + timedelta(hours=h), teu=teu, length_m=l, draft_m=d,
                      priority=p, status="inbound")
                 for i, (h, teu, l, d, p) in enumerate([
                     (2.0, 2000, 180, 9.2, 1), (3.0, 3000, 230, 11.0, 2),
                     (3.5, 2500, 205, 10.0, 2), (4.0, 3500, 255, 12.0, 1)])]
        inbound = pd.concat([inbound, pd.DataFrame(burst)], ignore_index=True)

    # live state: ships already waiting + 2 berths currently occupied
    waiting = {pid: int(((inbound.port == pid) & (inbound.eta <= now)).sum()) for pid in PORTS}
    live = {pid: dict(waiting_now=waiting[pid], berth_occupancy_pct=60, crane_util_pct=70,
                      yard_occupancy_pct=45,
                      occupied=[dict(vessel_id=f"{pid}-OCC1", berth_index=0,
                                     start=now - timedelta(hours=6),
                                     end=now + timedelta(hours=7), cranes=2),
                                dict(vessel_id=f"{pid}-OCC2", berth_index=1,
                                     start=now - timedelta(hours=3),
                                     end=now + timedelta(hours=11), cranes=2)])
             for pid in PORTS}
    return now, live, inbound[inbound.eta <= now + timedelta(hours=76)]