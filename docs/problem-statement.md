# Problem Statement

## 1. Background & Context

Global maritime trade accounts for over 80% of total world merchandise transportation. Over the last two decades, container shipping has seen explosive growth alongside the rapid introduction of ultra-large container vessels (ULCVs) carrying upwards of 20,000 TEU. 

However, physical port terminal capacity—specifically continuous quay length, deep-water berths, and specialized ship-to-shore (STS) quay cranes—cannot scale at the same pace. When multiple mega-vessels arrive simultaneously or experience adverse weather delays, ports face severe congestion bottlenecks.

---

## 2. The Problem

Port operators and marine terminal supervisors regularly experience high congestion caused by:
1. **Uncoordinated Offshore Queuing:** Multiple container vessels arriving in clustered arrival bursts, forcing ships to drop anchor offshore for days.
2. **Berth & Crane Bottlenecks:** Limited physical berths, strict vessel length and draft constraints, and finite quay crane resources.
3. **Reactive Decision Making:** Congestion is typically identified only *after* ships have already anchored offshore, at which point alternative routing or operational adjustments are too late to execute.
4. **Inefficient Heuristics:** Allocation is largely managed using First-Come, First-Served (FCFS) policies or manual spreadsheet schedules that fail to optimize turnaround time or crane resource pooling.

---

## 3. Who is Affected

- **Port Terminal Shift Supervisors & Planners:** Responsible for generating 24-to-72-hour berth allocations under high operational stress, changing weather conditions, and incomplete data.
- **Vessel Dispatchers & Shipping Line Fleet Managers:** Incur massive financial penalties and schedule disruption when their ships are stuck at anchorage with no visibility into alternative regional ports.
- **Port Authorities:** Suffer from terminal reputation loss, inefficient infrastructure utilization, and local environmental emissions from idling vessels.
- **Global Supply Chains & End Customers:** Experience inventory stockouts, delayed cargo delivery, and volatile freight rates.

---

## 4. Quantified Pain & Economic Impact

- **Demurrage & Anchorage Penalties:** Daily idle vessel operating costs and charter demurrage range from **$50,000 to $100,000+ per day per vessel**.
- **Severe Time Losses:** At congested hub ports, average anchorage waiting times frequently exceed **24 to 72 hours** before berthing can even begin.
- **Environmental & Carbon Footprint:** Auxiliary engine operations while idling at anchor burn metric tons of heavy fuel oil daily, creating localized emissions and failing IMO decarbonization targets.
- **Labor & Crane Inefficiencies:** Misaligned crane assignments lead to up to **30–40% berth idle gaps** between ship departures and next berthing windows.

---

## 5. Why Existing Solutions Fall Short

| Traditional Approach | Core Limitation |
|---|---|
| **Manual Spreadsheets & Whiteboards** | Cannot handle combinatorial constraints (vessel draft, length, crane capacity, tide windows) across dozens of vessels in real time. |
| **First-Come, First-Served (FCFS)** | Ignores vessel service duration, cargo priority, and crane flexibility, causing cascade delays when a large vessel is delayed. |
| **Siloed Terminal Operating Systems (TOS)** | TOS platforms manage local terminal execution well, but lack predictive multi-port congestion awareness and cross-port dynamic diversion algorithms. |
| **Pure AIS Tracking Dashboards** | Merely display where ships currently are (descriptive) without predicting future bottleneck queues or prescribing optimal operational schedules. |

---

## 6. Why This Problem Matters Now

With supply chains becoming increasingly lean, even minor port delays propagate rapidly into upstream manufacturing and retail disruptions. By moving from reactive firefighting to **predictive machine learning and constraint-based prescriptive optimization**, ports can cut waiting times, minimize demurrage costs, and optimize terminal throughput.
