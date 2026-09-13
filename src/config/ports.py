PORTS = {
    # capacity: 6 cranes x 30 TEU/h x 24h = 4,320 TEU/day (~4.3 ships/day)
    "PORT_A": dict(name="Port Alpha",
        berths=[dict(id="A1", length_m=250, depth_m=12.0),
                dict(id="A2", length_m=320, depth_m=14.5),
                dict(id="A3", length_m=180, depth_m=10.0),
                dict(id="A4", length_m=360, depth_m=16.0)],
        n_cranes=6, max_cranes_per_vessel=4, yard_capacity_teu=40000,
        base_arrivals_per_day=3.3),   # ~76% utilization -> congests on burst days
    # capacity: 4 cranes x 30 TEU/h x 24h = 2,880 TEU/day (~2.9 ships/day)
    "PORT_B": dict(name="Port Bravo",
        berths=[dict(id="B1", length_m=300, depth_m=14.0),
                dict(id="B2", length_m=220, depth_m=11.5),
                dict(id="B3", length_m=350, depth_m=15.5)],
        n_cranes=4, max_cranes_per_vessel=3, yard_capacity_teu=25000,
        base_arrivals_per_day=2.2),   # ~76% utilization -> slack for diversions
}
DIVERSION_COST_H = {("PORT_A", "PORT_B"): 9, ("PORT_B", "PORT_A"): 11}