"""PortPilot AI — Streamlit Dashboard.

Explainable Port Congestion Forecasting & Rolling 72-Hour Planning System.
Launch: python -m streamlit run src/app/dashboard.py
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path for Streamlit Cloud deployment
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import io
import csv
import json
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from src.data.generator import generate_scenario, Vessel, Berth, Crane, PortSpec

from src.data.features import validate_vessels, validate_ports
from src.models.congestion_model import (
    predict_congestion, CongestionLevel, _format_queue_display
)
from src.optimization.planner import generate_fcfs, generate_optimized, PlanResult
from src.optimization.router import recommend_alternative_ports, AlternativePortRecommendation
from src.simulation.port_sim import run_simulation, SimulationParam, SimulationResult
from src.config.settings import settings
from src.config.ports import DEFAULT_PORTS, PORT_CLUSTERS, get_live_state, PortLiveState, get_port_distance_nm
from src.data.live.live_manager import get_live_data_manager
from src.optimization.voyage_cost import (
    VoyageCostParams, TargetPortCost, DiversionCost
)
from src.optimization.target_optimizer import (
    run_target_port_optimization, RecommendationVerdict, TargetPortOptimizationResult
)


def _render_custom_css():
    st.markdown("""
        <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: 700;
            color: #0F172A;
            margin-bottom: 0.2rem;
        }
        .sub-header {
            font-size: 1.05rem;
            color: #475569;
            margin-bottom: 1.2rem;
        }
        .demo-badge {
            background-color: #FEF3C7;
            color: #92400E;
            padding: 0.35rem 0.75rem;
            border-radius: 0.375rem;
            font-weight: 600;
            font-size: 0.85rem;
            border: 1px solid #FCD34D;
            display: inline-block;
            margin-bottom: 1rem;
        }
        .live-badge {
            background-color: #DCFCE7;
            color: #166534;
            padding: 0.35rem 0.75rem;
            border-radius: 0.375rem;
            font-weight: 600;
            font-size: 0.85rem;
            border: 1px solid #86EFAC;
            display: inline-block;
            margin-bottom: 1rem;
        }
        .kpi-card {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 0.5rem;
            padding: 1rem;
            text-align: center;
        }
        .kpi-val {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1E293B;
        }
        .kpi-label {
            font-size: 0.82rem;
            color: #64748B;
            text-transform: uppercase;
            font-weight: 600;
            margin-top: 0.25rem;
        }
        .alert-box {
            border-radius: 0.5rem;
            padding: 0.85rem 1.1rem;
            margin-bottom: 0.75rem;
            font-size: 0.92rem;
        }
        .alert-critical {
            background-color: #FEE2E2;
            border-left: 5px solid #EF4444;
            color: #991B1B;
        }
        .alert-warning {
            background-color: #FEF3C7;
            border-left: 5px solid #F59E0B;
            color: #92400E;
        }
        .alert-info {
            background-color: #E0F2FE;
            border-left: 5px solid #0EA5E9;
            color: #075985;
        }
        .berth-tile {
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 8px;
            font-size: 0.87em;
            border: 1px solid #CBD5E1;
        }
        .berth-occupied {
            background-color: #FEE2E2;
            border-left: 4px solid #EF4444;
        }
        .berth-free {
            background-color: #DCFCE7;
            border-left: 4px solid #22C55E;
        }
        .berth-partial {
            background-color: #FEF3C7;
            border-left: 4px solid #F59E0B;
        }
        .port-selector-card {
            background: linear-gradient(135deg, #1E3A5F 0%, #0EA5E9 100%);
            border-radius: 10px;
            padding: 16px 20px;
            color: white;
            margin-bottom: 12px;
        }
        </style>
    """, unsafe_allow_html=True)


def _format_schedule_dataframe(assignments, vessels_by_id):
    rows = []
    for a in assignments:
        v = vessels_by_id.get(a.vessel_id)
        rows.append({
            "Vessel ID": a.vessel_id,
            "Vessel Name": v.vessel_name if v else "N/A",
            "Priority": f"P{v.priority}" if v else "-",
            "Arrival (h)": f"T+{v.arrival_time:.1f}h" if v else "-",
            "Berth": a.berth_id,
            "Crane": a.crane_id,
            "Start (h)": f"T+{a.start_time:.1f}h" if not a.deferred else "-",
            "End (h)": f"T+{a.end_time:.1f}h" if not a.deferred else "-",
            "Wait Time (h)": f"{a.wait_time:.1f}h" if not a.deferred else "-",
            "Status": "⚠️ DEFERRED" if a.deferred else "✅ SCHEDULED",
            "Notes / Reason": a.deferral_reason if a.deferred else "On Schedule",
        })
    return pd.DataFrame(rows)


def _build_gantt_chart(
    assignments,
    vessels_by_id,
    horizon_hours=72.0,
    occupied_berths=None,       # list of OccupiedBerth objects for the selected port
    port_berth_ids=None,        # set of berth IDs for this port
):
    """Build Gantt chart including pre-existing occupied berths as grey blocks."""
    base_time = datetime(2026, 9, 15, 0, 0)
    data = []

    # --- Pre-existing occupied berths (grey blocks) ---
    if occupied_berths:
        for ob in occupied_berths:
            end_dt = base_time + timedelta(hours=ob.free_at_hours)
            data.append({
                "Berth": ob.berth_id,
                "Vessel": f"🔒 {ob.vessel_name} (In Port)",
                "Start": base_time,
                "End": end_dt,
                "Wait": "—",
                "Priority": "Already Docked",
                "Start_H": 0.0,
                "End_H": ob.free_at_hours,
            })

    # --- Newly scheduled vessels ---
    scheduled = [a for a in assignments if not a.deferred and a.end_time > a.start_time]
    # Filter to port berths if specified
    if port_berth_ids:
        scheduled = [a for a in scheduled if a.berth_id in port_berth_ids]

    for a in scheduled:
        v = vessels_by_id.get(a.vessel_id)
        vname = v.vessel_name if v else a.vessel_id
        start_dt = base_time + timedelta(hours=a.start_time)
        end_dt = base_time + timedelta(hours=a.end_time)
        data.append({
            "Berth": a.berth_id,
            "Vessel": f"{a.vessel_id} ({vname})",
            "Start": start_dt,
            "End": end_dt,
            "Wait": f"{a.wait_time:.1f}h",
            "Priority": f"Priority {v.priority}" if v else "Standard",
            "Start_H": a.start_time,
            "End_H": a.end_time,
        })

    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No scheduled vessels within the horizon window", showarrow=False, font=dict(size=14))
        fig.update_layout(height=280)
        return fig

    df_gantt = pd.DataFrame(data)
    fig = px.timeline(
        df_gantt,
        x_start="Start",
        x_end="End",
        y="Berth",
        color="Priority",
        hover_name="Vessel",
        hover_data={"Start_H": ":.1f", "End_H": ":.1f", "Wait": True, "Berth": True, "Start": False, "End": False},
        title="<b>Berth Occupancy Timeline (72-Hour Horizon)</b>",
        category_orders={"Priority": ["Already Docked", "Priority 1", "Priority 2", "Priority 3"]},
        color_discrete_map={
            "Already Docked": "#94A3B8",   # grey for pre-existing ships
            "Priority 1": "#EF4444",
            "Priority 2": "#F59E0B",
            "Priority 3": "#3B82F6",
            "Standard": "#10B981",
        }
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Planning Timeline (Hours from T+0)",
        height=360,
        legend_title="Status / Priority",
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    return fig


def _render_port_status_card(port_spec, live_state: PortLiveState, berths, cranes):
    """Render a rich port status dashboard with berth grid and crane availability."""
    total_berths = port_spec.num_berths
    occupied_count = len(live_state.occupied_berths)
    free_count = total_berths - occupied_count
    occ_pct = live_state.berth_occupancy_pct

    total_cranes = port_spec.num_cranes
    busy_cranes = sum(1 for v in live_state.crane_busy_until.values() if v > 0)
    free_cranes = total_cranes - busy_cranes

    # Color coding
    if occ_pct >= 0.70:
        status_color = "#EF4444"
        status_label = "🔴 High Occupancy"
    elif occ_pct >= 0.40:
        status_color = "#F59E0B"
        status_label = "🟡 Moderate Occupancy"
    else:
        status_color = "#22C55E"
        status_label = "🟢 Low Occupancy"

    st.markdown(f"""
    <div style="background: linear-gradient(135deg,#1E3A5F,#0369A1);
                border-radius:12px; padding:18px 24px; color:white; margin-bottom:16px;">
        <div style="font-size:1.4em; font-weight:800; margin-bottom:4px;">
            🏗️ {port_spec.port_name}
        </div>
        <div style="font-size:0.95em; opacity:0.85; margin-bottom:10px;">Port ID: {port_spec.port_id} &nbsp;|&nbsp;
            Max Draft: {port_spec.max_vessel_draft_m}m &nbsp;|&nbsp;
            Max Length: {port_spec.max_vessel_length_m}m &nbsp;|&nbsp;
            Reliability: {port_spec.reliability_score:.0%}
        </div>
        <div style="display:flex; gap:20px; flex-wrap:wrap;">
            <div style="background:rgba(255,255,255,0.15); border-radius:8px; padding:10px 16px; text-align:center; min-width:110px;">
                <div style="font-size:1.8em; font-weight:700;">{total_berths}</div>
                <div style="font-size:0.78em; opacity:0.85;">Total Berths</div>
            </div>
            <div style="background:rgba(239,68,68,0.35); border-radius:8px; padding:10px 16px; text-align:center; min-width:110px;">
                <div style="font-size:1.8em; font-weight:700;">{occupied_count}</div>
                <div style="font-size:0.78em; opacity:0.85;">Occupied Now</div>
            </div>
            <div style="background:rgba(34,197,94,0.35); border-radius:8px; padding:10px 16px; text-align:center; min-width:110px;">
                <div style="font-size:1.8em; font-weight:700;">{free_count}</div>
                <div style="font-size:0.78em; opacity:0.85;">Free Berths</div>
            </div>
            <div style="background:rgba(255,255,255,0.15); border-radius:8px; padding:10px 16px; text-align:center; min-width:110px;">
                <div style="font-size:1.8em; font-weight:700;">{total_cranes}</div>
                <div style="font-size:0.78em; opacity:0.85;">Total Cranes</div>
            </div>
            <div style="background:rgba(239,68,68,0.35); border-radius:8px; padding:10px 16px; text-align:center; min-width:110px;">
                <div style="font-size:1.8em; font-weight:700;">{busy_cranes}</div>
                <div style="font-size:0.78em; opacity:0.85;">Cranes Busy</div>
            </div>
            <div style="background:rgba(34,197,94,0.35); border-radius:8px; padding:10px 16px; text-align:center; min-width:110px;">
                <div style="font-size:1.8em; font-weight:700;">{free_cranes}</div>
                <div style="font-size:0.78em; opacity:0.85;">Cranes Free</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Berth Grid
    st.markdown("##### 🏷️ Berth Status Grid")
    berth_cols = st.columns(min(total_berths, 4))
    for i, berth in enumerate([b for b in berths if b.port_id == port_spec.port_id]):
        with berth_cols[i % min(total_berths, 4)]:
            if berth.currently_occupied:
                css = "berth-occupied"
                icon = "🔴"
                status_txt = f"<b>{berth.occupying_vessel}</b><br>🕐 Free at T+{berth.free_at_hours:.1f}h"
            else:
                css = "berth-free"
                icon = "🟢"
                status_txt = "<b>Available Now</b><br>Ready for assignment"
            st.markdown(f"""
            <div class="berth-tile {css}">
                <div style="font-weight:700;">{icon} {berth.berth_id}</div>
                <div style="margin-top:4px; font-size:0.85em;">{status_txt}</div>
                <div style="margin-top:4px; font-size:0.78em; opacity:0.8;">
                    Max: {berth.max_vessel_length_m:.0f}m / {berth.max_vessel_draft_m:.1f}m draft
                </div>
            </div>""", unsafe_allow_html=True)

    # Crane Timeline Strip
    st.markdown("##### 🦾 Crane Availability at T+0")
    port_cranes = [c for c in cranes if c.port_id == port_spec.port_id]
    crane_cols = st.columns(min(len(port_cranes), 6))
    for i, crane in enumerate(port_cranes):
        with crane_cols[i % min(len(port_cranes), 6)]:
            if crane.currently_busy:
                badge = f"🔴 Busy until T+{crane.busy_until_hours:.1f}h"
                bg = "#FEE2E2"
                border = "#EF4444"
            else:
                badge = "🟢 Free Now"
                bg = "#DCFCE7"
                border = "#22C55E"
            st.markdown(f"""
            <div style="background:{bg}; border:1px solid {border}; border-radius:6px;
                        padding:8px 10px; margin-bottom:6px; text-align:center; font-size:0.82em;">
                <div style="font-weight:700;">{crane.crane_id}</div>
                <div>{badge}</div>
            </div>""", unsafe_allow_html=True)


def _generate_all_system_alerts(forecasts, opt_plan, sim_result=None, live_weather=None) -> List[Dict[str, Any]]:
    alerts = []
    # 0. Live Weather Alerts
    if live_weather:
        for port_id, w in live_weather.items():
            if w.crane_shutoff_risk:
                alerts.append({
                    "severity": "critical",
                    "entity": f"Port {port_id} Weather",
                    "trigger": f"High Wind Alert ({w.wind_gusts_knots} kts gusts)",
                    "explanation": f"Extreme wind conditions exceed crane safety limits (threshold 35 kts). Crane shutoffs likely.",
                    "recommended_action": "Pause crane operations on high-tier container stacks and secure ship-to-shore booms.",
                })
            elif w.pilotage_delay_risk:
                alerts.append({
                    "severity": "warning",
                    "entity": f"Port {port_id} Weather",
                    "trigger": f"Adverse Sea State ({w.wind_speed_knots} kts wind)",
                    "explanation": "Elevated sea swell and wind may cause pilot boarding delays.",
                    "recommended_action": "Notify incoming masters of potential pilotage window adjustments.",
                })

    # 1. Congestion Alerts
    for f in forecasts:
        if f.congestion_level in (CongestionLevel.CRITICAL, CongestionLevel.HIGH):
            sev = "critical" if f.congestion_level == CongestionLevel.CRITICAL else "warning"
            alerts.append({
                "severity": sev,
                "entity": f"Port {f.port_id}",
                "trigger": f"High Congestion ({f.congestion_level.value})",
                "explanation": f"Forecasted queue fraction {f.predicted_queue_length:.2f} with berth utilization {f.berth_utilization:.0%}. {', '.join(f.contributing_factors)}",
                "recommended_action": "Evaluate alternative ports or reschedule incoming feeder vessels.",
            })

    # 2. Optimization / Deferral Alerts
    if opt_plan:
        if opt_plan.deferred_count > 0:
            alerts.append({
                "severity": "warning",
                "entity": "Vessel Fleet",
                "trigger": "Vessel Deferrals Detected",
                "explanation": f"{opt_plan.deferred_count} vessel(s) could not be accommodated inside the 72h horizon window.",
                "recommended_action": "Check alternative ports or consider increasing crane allocations.",
            })
        if opt_plan.solver_result and opt_plan.solver_result.fallback_used:
            alerts.append({
                "severity": "info",
                "entity": "Optimization Solver",
                "trigger": "Solver Fallback Engaged",
                "explanation": f"CP-SAT solver triggered fallback: {opt_plan.solver_result.fallback_reason}",
                "recommended_action": "Verify solver timeout limits in configuration.",
            })

    # 3. Simulation Alerts
    if sim_result and sim_result.alerts:
        alerts.extend(sim_result.alerts)

    return alerts


def _assignments_to_csv(assignments) -> str:
    if not assignments:
        return ""
    buf = io.StringIO()
    fields = list(assignments[0].__dataclass_fields__.keys())
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for a in assignments:
        writer.writerow(a.__dict__)
    return buf.getvalue()


def _assignments_to_json(assignments) -> str:
    return json.dumps([a.__dict__ for a in assignments], indent=2)


def main():
    st.set_page_config(
        page_title="PortPilot AI — Port Congestion & 72-Hour Planning",
        page_icon="🚢",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _render_custom_css()

    # Header
    st.markdown('<div class="main-header">🚢 PortPilot AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Explainable Port Congestion Forecasting & Rolling 72-Hour Constraint-Aware Planning System</div>', unsafe_allow_html=True)

    # ── Sidebar: Data Stream Mode ────────────────────────────────────────────
    st.sidebar.header("📡 Data Stream Mode")
    mode_selection = st.sidebar.radio(
        "Ingestion Source",
        ["🟢 Live Operational Stream (Real-Time Ingestion)", "🟡 Synthetic Demo Scenarios"],
        index=0,
    )
    is_live_mode = "Live" in mode_selection

    if is_live_mode:
        st.markdown(f'<div class="live-badge">🟢 {settings.live_data_banner}</div>', unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ {settings.demo_data_banner}")

    # ── Sidebar: Cluster selection ───────────────────────────────────────────
    st.sidebar.header("🌍 Port Region & Hubs")
    selected_cluster_key = st.sidebar.selectbox(
        "Port Region Cluster",
        list(PORT_CLUSTERS.keys()),
        format_func=lambda k: PORT_CLUSTERS[k]["cluster_name"],
        index=0,
    )

    # ── Sidebar: Planning controls ───────────────────────────────────────────
    st.sidebar.header("🕹️ Planning Horizon Controls")
    horizon = st.sidebar.slider("Planning Horizon (Hours)", 12, 168, settings.planning_horizon_hours, step=6)
    num_vessels = st.sidebar.slider("Monitored Vessel Fleet Size", 5, 50, settings.default_num_vessels, step=1)

    # ── Load scenario (live or synthetic) ───────────────────────────────────
    live_mgr = get_live_data_manager()
    live_weather = None

    if is_live_mode:
        if st.sidebar.button("🔄 Sync Live Streams Now", use_container_width=True):
            scenario = live_mgr.get_live_scenario(num_vessels, cluster=selected_cluster_key, force_refresh=True)
            st.toast("Live AIS, TOS & Weather streams refreshed!", icon="✅")
        else:
            scenario = live_mgr.get_live_scenario(num_vessels, cluster=selected_cluster_key)

        vessels = scenario["vessels"]
        berths = scenario["berths"]
        cranes = scenario["cranes"]
        ports = scenario["ports"]
        live_weather = scenario.get("weather")
        last_sync = scenario.get("last_synced_dt", "N/A")
        scenario_name = f"Live AIS Feed ({last_sync})"

        with st.sidebar.expander("🌐 Live Streams Health", expanded=True):
            st.caption(f"**Last Synchronized:** `{last_sync}`")
            health = scenario.get("health", {})
            for k, v in health.items():
                st.write(f"• **{k.replace('_', ' ').title()}:** `{v}`")

    else:
        scenario_name = st.sidebar.selectbox(
            "Operational Scenario",
            ["normal", "high_arrival", "crane_outage", "berth_maintenance",
             "weather_disruption", "congestion"],
            format_func=lambda x: {
                "normal": "🟢 Normal Flow (Balanced Arrivals)",
                "high_arrival": "🟡 High Arrival Surge (Compressed Waves)",
                "crane_outage": "🔴 Crane Outage (Reduced Crane Productivity)",
                "berth_maintenance": "🛠️ Berth Maintenance (Restricted Capacity)",
                "weather_disruption": "⛈️ Weather Disruption (Extended Service Time)",
                "congestion": "🚨 High Congestion Stress Test",
            }.get(x, x),
        )
        scenario = generate_scenario(scenario_name, num_vessels, cluster=selected_cluster_key)
        vessels = scenario["vessels"]
        berths = scenario["berths"]
        cranes = scenario["cranes"]
        ports = scenario["ports"]

    # ── Sidebar: PORT SELECTION ──────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.header("🏗️ Select Target Port")
    st.sidebar.caption("Choose a port to view its current occupancy state and run berth/crane allocation for incoming ships.")

    # Build port options with live occupancy badge
    def _port_option_label(p: PortSpec) -> str:
        live_st = get_live_state(selected_cluster_key, p.port_id)
        occ_pct = live_st.berth_occupancy_pct
        occ_label = f"{occ_pct:.0%} occupied ({len(live_st.occupied_berths)}/{p.num_berths} berths)"
        if occ_pct >= 0.70:
            badge = "🔴"
        elif occ_pct >= 0.40:
            badge = "🟡"
        else:
            badge = "🟢"
        return f"{badge} {p.port_name} — {occ_label}"

    selected_port_id = st.sidebar.selectbox(
        "Port",
        [p.port_id for p in ports],
        format_func=lambda pid: _port_option_label(next(p for p in ports if p.port_id == pid)),
    )

    selected_port_spec: PortSpec = next(p for p in ports if p.port_id == selected_port_id)
    selected_live_state: PortLiveState = get_live_state(selected_cluster_key, selected_port_id)

    # ── Filter berths, cranes, vessels for selected port ────────────────────
    port_berths = [b for b in berths if b.port_id == selected_port_id]
    port_cranes = [c for c in cranes if c.port_id == selected_port_id]
    port_berth_ids = {b.berth_id for b in port_berths}

    # Vessels headed to or preferred at the selected port
    port_vessels = [
        v for v in vessels
        if v.preferred_port == selected_port_id or v.destination_port == selected_port_id
    ]
    # Fallback: if no vessels match, show a subset of all vessels targeting this port
    if len(port_vessels) < 2:
        port_vessels = vessels[:max(5, num_vessels // len(ports))]
        for v in port_vessels:
            v.preferred_port = selected_port_id
            v.destination_port = selected_port_id

    vessels_by_id = {v.vessel_id: v for v in vessels}

    # ── Data Validation ──────────────────────────────────────────────────────
    v_valid, v_warnings = validate_vessels(vessels)
    p_valid, p_warnings = validate_ports(ports)
    with st.sidebar.expander("🛡️ Data Integrity & Quality", expanded=False):
        st.write(f"Vessel Records: {'✅ Valid' if v_valid else '❌ Warnings'}")
        st.write(f"Port Specifications: {'✅ Valid' if p_valid else '❌ Warnings'}")
        if v_warnings or p_warnings:
            for w in (v_warnings + p_warnings):
                st.caption(f"**[{w.severity.upper()}]** `{w.field}`: {w.message}")
        else:
            st.caption("All ingested records passed constraint checks.")

    # ── Live Weather Cards ───────────────────────────────────────────────────
    if is_live_mode and live_weather:
        st.markdown("#### 🌊 Live MetOcean & Weather Telemetry (Open-Meteo)")
        w_cols = st.columns(len(live_weather))
        for idx, (pid, w) in enumerate(live_weather.items()):
            with w_cols[idx]:
                st.markdown(f"""
                <div style="background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 6px; padding: 10px 14px; margin-bottom: 10px;">
                    <div style="font-weight: 700; color: #1E293B; font-size: 0.95em;">{w.port_name}</div>
                    <div style="font-size: 0.85em; color: #475569; margin-top: 2px;">
                        💨 <b>Wind:</b> {w.wind_speed_knots} kts (Gusts: {w.wind_gusts_knots} kts) | 🌡️ {w.temperature_c}°C
                    </div>
                    <div style="font-size: 0.82em; margin-top: 2px;">{w.condition_summary}</div>
                </div>
                """, unsafe_allow_html=True)

    # ── PORT STATUS DASHBOARD ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 🏗️ Port Status Dashboard")
    _render_port_status_card(selected_port_spec, selected_live_state, berths, cranes)

    # ── Top Overview KPIs (fleet-wide) ───────────────────────────────────────
    forecasts = predict_congestion(vessels, berths, cranes, horizon)
    port_forecast = next((f for f in forecasts if f.port_id == selected_port_id), None)
    avg_berth_util = sum(f.berth_utilization for f in forecasts) / max(len(forecasts), 1)
    high_cong_count = sum(1 for f in forecasts if f.congestion_level in (CongestionLevel.HIGH, CongestionLevel.CRITICAL))

    st.markdown("#### 📊 Fleet-Wide Overview KPIs")
    col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
    with col_k1:
        st.metric("Total Vessels", f"{len(vessels)} ships", delta="Live AIS" if is_live_mode else scenario_name)
    with col_k2:
        st.metric("Active Berths", f"{len(berths)} berths across {len(ports)} ports")
    with col_k3:
        st.metric("Operational Cranes", f"{len(cranes)} cranes")
    with col_k4:
        st.metric("Congestion Pressure", f"{high_cong_count} Hotspot(s)", delta_color="inverse", delta="Critical/High" if high_cong_count > 0 else "Normal")
    with col_k5:
        st.metric("Mean Berth Load", f"{avg_berth_util:.0%}")

    # Selected port KPIs
    if port_forecast:
        st.markdown(f"#### 🎯 Selected Port — {selected_port_spec.port_name}")
        sk1, sk2, sk3, sk4 = st.columns(4)
        with sk1:
            st.metric("Incoming Vessels", f"{len(port_vessels)} ships")
        with sk2:
            occ_pct = selected_live_state.berth_occupancy_pct
            st.metric("Current Occupancy", f"{occ_pct:.0%}", delta=f"{len(selected_live_state.occupied_berths)}/{selected_port_spec.num_berths} berths busy")
        with sk3:
            st.metric("Congestion Level", port_forecast.congestion_level.value,
                      delta=f"Berth util: {port_forecast.berth_utilization:.0%}")
        with sk4:
            free_berths = selected_port_spec.num_berths - len(selected_live_state.occupied_berths)
            st.metric("Free Berths Now", f"{free_berths}", delta=f"{len(port_cranes)} cranes available")

    st.markdown("---")

    # ── Main Tabs ────────────────────────────────────────────────────────────
    tab_forecast, tab_plans, tab_router, tab_sim, tab_alerts, tab_export = st.tabs([
        "📊 1. Congestion Forecasts",
        "⚡ 2. Berth & Crane Allocation",
        "🎯 3. Target Port Optimizer",
        "🧪 4. What-If Simulation Engine",
        "🚨 5. Operational Alerts Hub",
        "💾 6. Schedule Export & Metadata",
    ])

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 1: CONGESTION FORECASTS
    # ──────────────────────────────────────────────────────────────────────────
    with tab_forecast:
        st.subheader(f"Port Congestion Forecast — {selected_port_spec.port_name} (Primary) + Network View")
        st.caption("Transparent baseline congestion modeling. Selected port shown in detail; other ports shown for comparison.")

        # Primary selected port — full detail card
        if port_forecast:
            pf = port_forecast
            level_color = {
                CongestionLevel.LOW: "🟢",
                CongestionLevel.MEDIUM: "🟡",
                CongestionLevel.HIGH: "🟠",
                CongestionLevel.CRITICAL: "🔴",
            }.get(pf.congestion_level, "⚪")

            st.markdown(f"""
            <div style="background:#EFF6FF; border:2px solid #3B82F6; border-radius:10px; padding:18px 22px; margin-bottom:16px;">
                <h3 style="margin:0 0 10px 0; color:#1E3A5F;">
                    🎯 {selected_port_spec.port_name} <span style="font-size:0.7em; color:#64748B;">({pf.port_id})</span>
                </h3>
                <div style="display:flex; gap:24px; flex-wrap:wrap;">
                    <div><b>Status:</b> {level_color} {pf.congestion_level.value}</div>
                    <div><b>Queue Fraction:</b> {pf.predicted_queue_length:.2f} &nbsp;—&nbsp; <i>{_format_queue_display(pf.predicted_queue_length)}</i></div>
                    <div><b>Expected Wait:</b> {'Minimal (<0.5h)' if pf.congestion_level == CongestionLevel.LOW else f'{pf.expected_wait_hours:.1f}h'}</div>
                    <div><b>Berth Utilization:</b> {pf.berth_utilization:.0%}</div>
                    <div><b>Crane Utilization:</b> {pf.crane_utilization:.0%}</div>
                    <div><b>Confidence:</b> {pf.confidence:.0%}</div>
                </div>
                <div style="margin-top:10px; font-size:0.88em; color:#475569;">
                    <b>Contributing Factors:</b> {', '.join(pf.contributing_factors)}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Other ports comparison
        other_forecasts = [f for f in forecasts if f.port_id != selected_port_id]
        if other_forecasts:
            st.markdown("#### 🌐 Other Ports in Cluster (Comparison)")
            port_cols = st.columns(len(other_forecasts))
            for idx, f in enumerate(other_forecasts):
                port_obj = next((p for p in ports if p.port_id == f.port_id), None)
                port_name = port_obj.port_name if port_obj else f.port_id
                level_color = {
                    CongestionLevel.LOW: "🟢",
                    CongestionLevel.MEDIUM: "🟡",
                    CongestionLevel.HIGH: "🟠",
                    CongestionLevel.CRITICAL: "🔴",
                }.get(f.congestion_level, "⚪")

                with port_cols[idx]:
                    st.markdown(f"""
                    <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                        <h5 style="margin: 0 0 6px 0; color: #1E293B;">{port_name} <span style="font-size:0.8em; color:#64748B;">({f.port_id})</span></h5>
                        <p style="margin: 3px 0; font-size: 1em; font-weight: 600;">{level_color} {f.congestion_level.value}</p>
                        <p style="margin: 3px 0; color: #475569;"><b>Queue:</b> {f.predicted_queue_length:.2f}</p>
                        <p style="margin: 3px 0; color: #475569;"><b>Berth Util:</b> {f.berth_utilization:.0%}</p>
                        <p style="margin: 3px 0; font-size: 0.82em; color: #64748B;"><i>{', '.join(f.contributing_factors)}</i></p>
                    </div>
                    """, unsafe_allow_html=True)

        # Network utilization chart
        df_cong = pd.DataFrame([
            {
                "Port": f"{next((p.port_name for p in ports if p.port_id == f.port_id), f.port_id)} ({f.port_id})",
                "Selected": "🎯 Selected" if f.port_id == selected_port_id else "Other Ports",
                "Queue Fraction": round(f.predicted_queue_length, 2),
                "Berth Utilization %": round(f.berth_utilization * 100, 1),
                "Crane Utilization %": round(f.crane_utilization * 100, 1),
                "Congestion Level": f.congestion_level.value,
            }
            for f in forecasts
        ])
        fig_cong = px.bar(
            df_cong,
            x="Port",
            y=["Berth Utilization %", "Crane Utilization %"],
            barmode="group",
            title="<b>Port Network — Resource Utilization & Saturation</b>",
            color_discrete_sequence=["#3B82F6", "#8B5CF6"],
        )
        fig_cong.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_cong, use_container_width=True)

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2: BERTH & CRANE ALLOCATION (single-port focused)
    # ──────────────────────────────────────────────────────────────────────────
    with tab_plans:
        st.subheader(f"Berth & Crane Allocation — {selected_port_spec.port_name}")
        st.caption(
            f"Allocating {len(port_vessels)} incoming vessels across "
            f"{selected_port_spec.num_berths} berths "
            f"({selected_port_spec.num_berths - len(selected_live_state.occupied_berths)} currently free) "
            f"with {selected_port_spec.num_cranes} cranes. "
            "Grey blocks = ships already docked. Colored blocks = new assignments."
        )

        # Occupancy summary banner
        occ_n = len(selected_live_state.occupied_berths)
        free_n = selected_port_spec.num_berths - occ_n
        if len(port_vessels) > free_n:
            st.info(
                f"ℹ️ **{len(port_vessels)} incoming ships** vs **{free_n} free berths** → "
                f"{len(port_vessels) - free_n} ship(s) will queue and be allocated as berths free up."
            )

        # Show occupied berths detail
        if selected_live_state.occupied_berths:
            with st.expander("🔒 Currently Docked Ships (Pre-existing Occupancy)", expanded=True):
                occ_data = [{
                    "Berth": ob.berth_id,
                    "Vessel Docked": ob.vessel_name,
                    "Cargo Type": ob.cargo_type,
                    "Berth Free At": f"T+{ob.free_at_hours:.1f}h",
                } for ob in selected_live_state.occupied_berths]
                st.dataframe(pd.DataFrame(occ_data), use_container_width=True, hide_index=True)

        # Plan generation buttons
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            if st.button("▶️ Run FCFS Baseline", use_container_width=True):
                st.session_state["fcfs"] = generate_fcfs(port_vessels, port_berths, port_cranes, horizon)
        with col_btn2:
            if st.button("🚀 Solve with OR-Tools CP-SAT", type="primary", use_container_width=True):
                st.session_state["optimized"] = generate_optimized(port_vessels, port_berths, port_cranes, horizon)
        with col_btn3:
            if st.button("🔄 Generate & Compare Both Plans", use_container_width=True):
                st.session_state["fcfs"] = generate_fcfs(port_vessels, port_berths, port_cranes, horizon)
                st.session_state["optimized"] = generate_optimized(port_vessels, port_berths, port_cranes, horizon)

        # Auto-generate on first load
        if "fcfs" not in st.session_state:
            st.session_state["fcfs"] = generate_fcfs(port_vessels, port_berths, port_cranes, horizon)
        if "optimized" not in st.session_state:
            st.session_state["optimized"] = generate_optimized(port_vessels, port_berths, port_cranes, horizon)

        fcfs_p: PlanResult = st.session_state.get("fcfs")
        opt_p: PlanResult = st.session_state.get("optimized")

        # KPI comparison
        st.markdown("#### Plan Performance Metrics")
        mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
        with mcol1:
            wait_diff = round(opt_p.avg_wait_hours - fcfs_p.avg_wait_hours, 1)
            st.metric("Average Wait Time", f"{opt_p.avg_wait_hours:.1f} h",
                      delta=f"{wait_diff} h vs FCFS ({fcfs_p.avg_wait_hours:.1f}h)", delta_color="inverse")
        with mcol2:
            delay_diff = round(opt_p.avg_delay_hours - fcfs_p.avg_delay_hours, 1)
            st.metric("Average Delay", f"{opt_p.avg_delay_hours:.1f} h",
                      delta=f"{delay_diff} h vs FCFS", delta_color="inverse")
        with mcol3:
            def_diff = opt_p.deferred_count - fcfs_p.deferred_count
            st.metric("Deferred Vessels", f"{opt_p.deferred_count} / {len(port_vessels)}",
                      delta=f"{def_diff} vs FCFS ({fcfs_p.deferred_count})", delta_color="inverse")
        with mcol4:
            st.metric("Berth Utilization", f"{opt_p.berth_utilization:.0%}",
                      delta=f"{(opt_p.berth_utilization - fcfs_p.berth_utilization):.0%} vs FCFS")
        with mcol5:
            solver_stat = opt_p.solver_result.status.value if opt_p.solver_result else "FEASIBLE"
            st.metric("Solver Status", f"{solver_stat}", delta=f"{opt_p.runtime_seconds:.3f}s runtime")

        # Gantt — with pre-existing occupied berths shown as grey blocks
        st.markdown("#### 📅 Berth Allocation Gantt (including pre-existing occupancy)")
        fig_gantt = _build_gantt_chart(
            opt_p.assignments,
            vessels_by_id,
            horizon,
            occupied_berths=selected_live_state.occupied_berths,
            port_berth_ids=port_berth_ids,
        )
        st.plotly_chart(fig_gantt, use_container_width=True)

        # Allocation table
        st.markdown("#### 📋 Detailed Berth & Crane Assignment Table")
        plan_view = st.radio(
            "Select Schedule Table View",
            ["Optimized Plan (CP-SAT)", "Baseline Plan (FCFS)"],
            horizontal=True
        )
        active_plan = opt_p if "Optimized" in plan_view else fcfs_p

        # Build enriched table for selected port vessels
        rows = []
        port_vessel_ids = {v.vessel_id for v in port_vessels}
        for a in active_plan.assignments:
            if a.vessel_id not in port_vessel_ids:
                continue
            v = vessels_by_id.get(a.vessel_id)
            # Find the berth object for extra info
            berth_obj = next((b for b in port_berths if b.berth_id == a.berth_id), None)
            crane_obj = next((c for c in port_cranes if c.crane_id == a.crane_id), None)
            rows.append({
                "Vessel ID": a.vessel_id,
                "Vessel Name": v.vessel_name if v else "N/A",
                "Priority": f"P{v.priority}" if v else "-",
                "Arrival (T+h)": f"{v.arrival_time:.1f}h" if v else "-",
                "Berth Assigned": a.berth_id if not a.deferred else "— Queued —",
                "Berth Free At": f"T+{berth_obj.free_at_hours:.1f}h" if (berth_obj and berth_obj.currently_occupied) else "Available",
                "Crane Assigned": a.crane_id if not a.deferred else "—",
                "Crane Busy Until": f"T+{crane_obj.busy_until_hours:.1f}h" if (crane_obj and crane_obj.currently_busy) else "Free",
                "Wait (h)": f"{a.wait_time:.1f}h" if not a.deferred else "Queued",
                "Service Start": f"T+{a.start_time:.1f}h" if not a.deferred else "—",
                "Service End": f"T+{a.end_time:.1f}h" if not a.deferred else "—",
                "Status": "⚠️ DEFERRED" if a.deferred else "✅ SCHEDULED",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No assignments to display for this port.")

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 3: TARGET PORT OPTIMIZER & VOYAGE ECONOMICS
    # ──────────────────────────────────────────────────────────────────────────
    with tab_router:
        st.subheader("🎯 Target Port-Based Congestion Optimization & Routing")
        st.caption(
            "In real-world operations, vessels have predetermined destinations and cannot change routes arbitrarily. "
            "This engine performs a 72-hour operational simulation at the target port (docked vessels, quay crane availability, incoming arrivals), "
            "evaluates full voyage economics (extra distance, bunker fuel burn, port charges, demurrage), "
            "and only recommends diversion when operationally feasible and financially justified."
        )

        # ── Target Port & Vessel Selection ────────────────────────────────────
        tp_col1, tp_col2 = st.columns([1, 1])
        with tp_col1:
            t_port_id = st.selectbox(
                "Predetermined Target Port",
                [p.port_id for p in ports],
                index=[p.port_id for p in ports].index(selected_port_id) if selected_port_id in [p.port_id for p in ports] else 0,
                format_func=lambda pid: f"🎯 {next(p.port_name for p in ports if p.port_id == pid)} ({pid})",
                key="target_opt_port_select",
            )
            eval_target_port = next(p for p in ports if p.port_id == t_port_id)

        with tp_col2:
            # Inbound vessels for target port
            target_candidates = [v for v in vessels if v.preferred_port == t_port_id or v.destination_port == t_port_id]
            if not target_candidates:
                target_candidates = vessels
            eval_vessel_id = st.selectbox(
                "Select Inbound Vessel to Evaluate",
                [v.vessel_id for v in target_candidates],
                format_func=lambda vid: f"🚢 {vid} — {vessels_by_id[vid].vessel_name} (ETA: T+{vessels_by_id[vid].arrival_time:.1f}h, {vessels_by_id[vid].cargo_volume:,.0f} TEU)",
                key="target_opt_vessel_select",
            )
            eval_vessel = vessels_by_id[eval_vessel_id]

        # ── Vessel Specifications Summary ─────────────────────────────────────
        st.markdown(f"""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 18px; margin-bottom: 14px;">
            <div style="font-weight: 700; color: #1E293B; font-size: 1.05em; margin-bottom: 4px;">
                🚢 Evaluated Vessel: {eval_vessel.vessel_id} ({eval_vessel.vessel_name})
            </div>
            <div style="display: flex; gap: 24px; flex-wrap: wrap; font-size: 0.88em; color: #475569;">
                <div><b>Length:</b> {eval_vessel.vessel_length_m:.1f} m</div>
                <div><b>Draft:</b> {eval_vessel.vessel_draft_m:.1f} m</div>
                <div><b>Cargo:</b> {eval_vessel.cargo_volume:,.0f} TEU</div>
                <div><b>Required Cranes:</b> {eval_vessel.required_cranes} STS</div>
                <div><b>Priority:</b> P{eval_vessel.priority}</div>
                <div><b>Service Duration:</b> {eval_vessel.service_duration_h:.1f} h</div>
                <div><b>ETA:</b> T+{eval_vessel.arrival_time:.1f} h</div>
                <div><b>Predetermined Destination:</b> {eval_target_port.port_name}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Configurable Voyage & Financial Parameters ────────────────────────
        with st.expander("⚙️ Configure Maritime Voyage & Economic Parameters (Bunker, OPEX, Demurrage)", expanded=False):
            st.caption("Customize commercial charter rates, bunker fuel consumption, and laytime terms for this voyage:")
            pcol1, pcol2, pcol3, pcol4 = st.columns(4)
            with pcol1:
                in_vessel_opex = st.number_input("Vessel Daily OPEX / Charter ($/day)", min_value=5000, max_value=80000, value=25000, step=1000)
                in_bunker_price = st.number_input("VLSFO Bunker Fuel Price ($/MT)", min_value=300, max_value=1500, value=620, step=20)
            with pcol2:
                in_fuel_sea = st.number_input("Transit Fuel Burn at Sea (MT/day)", min_value=10.0, max_value=120.0, value=35.0, step=2.5)
                in_fuel_idle = st.number_input("Auxiliary Idle Fuel at Anchor (MT/day)", min_value=1.0, max_value=20.0, value=3.5, step=0.5)
            with pcol3:
                in_speed_knots = st.number_input("Cruising Speed (knots)", min_value=8.0, max_value=25.0, value=16.0, step=0.5)
                in_demurrage_rate = st.number_input("Demurrage Penalty Rate ($/day)", min_value=5000, max_value=60000, value=18000, step=1000)
            with pcol4:
                in_free_laytime = st.number_input("Allowed Free Laytime (hours)", min_value=0.0, max_value=48.0, value=12.0, step=2.0)
                in_min_savings = st.number_input("Min Diversion Savings Threshold ($)", min_value=1000, max_value=100000, value=10000, step=2500)

            custom_cost_params = VoyageCostParams(
                vessel_daily_cost_usd=float(in_vessel_opex),
                fuel_consumption_sea_mt_day=float(in_fuel_sea),
                fuel_consumption_idle_mt_day=float(in_fuel_idle),
                bunker_price_vlsfo_usd_mt=float(in_bunker_price),
                vessel_speed_knots=float(in_speed_knots),
                demurrage_rate_day_usd=float(in_demurrage_rate),
                free_laytime_hours=float(in_free_laytime),
            )

        # ── Run Target Port Optimization ──────────────────────────────────────
        opt_res: TargetPortOptimizationResult = run_target_port_optimization(
            vessel=eval_vessel,
            target_port=eval_target_port,
            all_ports=ports,
            all_berths=berths,
            all_cranes=cranes,
            incoming_fleet=vessels,
            cluster_key=selected_cluster_key,
            cost_params=custom_cost_params,
            horizon_hours=horizon,
            min_saving_threshold_usd=float(in_min_savings),
        )

        t_ana = opt_res.target_analysis

        # ── STEP 1: Target Port 72-Hour Operational Simulation ────────────────
        st.markdown(f"#### 1️⃣ Target Port 72-Hour Simulation — {eval_target_port.port_name}")
        t_col1, t_col2, t_col3, t_col4 = st.columns(4)
        with t_col1:
            st.metric(
                "Berth Occupancy at T+0",
                f"{t_ana.occupied_berths_now} / {t_ana.total_berths} occupied",
                delta=f"{t_ana.free_berths_now} berths free now",
            )
        with t_col2:
            st.metric(
                "Quay Crane Availability",
                f"{t_ana.busy_cranes_now} / {t_ana.total_cranes} busy",
                delta=f"{t_ana.total_cranes - t_ana.busy_cranes_now} cranes free now",
            )
        with t_col3:
            st.metric(
                "Simulated Inbound Queue Wait",
                f"{t_ana.expected_wait_hours:.1f} hours",
                delta=f"Service Start: T+{t_ana.service_start_time:.1f}h",
                delta_color="inverse" if t_ana.expected_wait_hours > custom_cost_params.free_laytime_hours else "normal",
            )
        with t_col4:
            st.metric(
                "Total Target Port Call Cost",
                f"${t_ana.cost_breakdown.total_target_cost:,.0f}",
                delta=f"Demurrage: ${t_ana.cost_breakdown.demurrage_cost:,.0f}" if t_ana.cost_breakdown.demurrage_cost > 0 else "No Demurrage",
                delta_color="inverse",
            )

        # Cost Breakdown Card for Target Port
        with st.expander("🧾 View Target Port Itemized Financial Breakdown", expanded=True):
            cb = t_ana.cost_breakdown
            cb_df = pd.DataFrame([
                {"Cost Component": "Vessel Waiting OPEX (Charter)", "Details": f"{cb.wait_hours:.1f}h waiting @ ${custom_cost_params.vessel_daily_cost_usd:,.0f}/day", "Amount (USD)": f"${cb.wait_opex_cost:,.2f}"},
                {"Cost Component": "Auxiliary Bunker Fuel at Anchor", "Details": f"{cb.wait_hours:.1f}h @ {custom_cost_params.fuel_consumption_idle_mt_day} MT/day (${custom_cost_params.bunker_price_vlsfo_usd_mt:.0f}/MT)", "Amount (USD)": f"${cb.wait_idle_fuel_cost:,.2f}"},
                {"Cost Component": "Contractual Demurrage Charges", "Details": f"{max(0.0, cb.wait_hours - custom_cost_params.free_laytime_hours):.1f}h excess wait beyond {custom_cost_params.free_laytime_hours:.0f}h laytime", "Amount (USD)": f"${cb.demurrage_cost:,.2f}"},
                {"Cost Component": "Terminal Handling Tariff", "Details": f"{eval_vessel.cargo_volume:,.0f} TEU @ ${eval_target_port.handling_cost_per_teu:.2f}/TEU", "Amount (USD)": f"${cb.port_handling_cost:,.2f}"},
                {"Cost Component": "STS Crane Operating Charges", "Details": f"{eval_vessel.service_duration_h:.1f}h × {max(1, eval_vessel.required_cranes)} cranes @ ${custom_cost_params.crane_rate_per_hour_usd:.0f}/h", "Amount (USD)": f"${cb.crane_operating_cost:,.2f}"},
                {"Cost Component": "TOTAL ESTIMATED CALL COST", "Details": "Sum of all waiting, fuel, demurrage, and port handling costs", "Amount (USD)": f"${cb.total_target_cost:,.2f}"},
            ])
            st.dataframe(cb_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        # ── STEP 2: Decision Gate & Operational Verdict ───────────────────────
        st.markdown("#### 2️⃣ Operational Decision Gate & Recommendation")
        if opt_res.verdict == RecommendationVerdict.CONSIDER_DIVERSION:
            verdict_badge = "🚨 CONSIDER DIVERSION TO ALTERNATIVE PORT"
            card_bg = "#FEF2F2"
            card_border = "#EF4444"
            headline_color = "#991B1B"
        else:
            verdict_badge = "🟢 PROCEED TO PREDETERMINED TARGET PORT"
            card_bg = "#F0FDF4"
            card_border = "#22C55E"
            headline_color = "#166534"

        st.markdown(f"""
        <div style="background-color: {card_bg}; border: 2px solid {card_border}; border-radius: 10px; padding: 20px 24px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="font-weight: 800; font-size: 1.25em; color: {headline_color};">
                    {verdict_badge}
                </div>
                <div style="background-color: white; border: 1px solid {card_border}; border-radius: 6px; padding: 4px 12px; font-weight: 700; font-size: 0.9em; color: #1E293B;">
                    Confidence: {opt_res.confidence:.0%}
                </div>
            </div>
            <div style="font-size: 1.1em; font-weight: 700; color: #1E293B; margin-bottom: 10px;">
                {opt_res.headline}
            </div>
            <div style="font-size: 0.95em; color: #334155; line-height: 1.6;">
                {opt_res.detailed_justification}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # ── STEP 3: Nearby Alternative Ports Comparative Analysis ─────────────
        st.markdown("#### 3️⃣ Feasible Nearby Alternative Ports — Voyage & Economic Comparison")
        st.caption(
            "Every alternative port is evaluated against vessel physical constraints (draft & length), "
            "additional sailing distance, transit bunker fuel cost, expected port waiting queue, and net bottom-line financial savings."
        )

        if not opt_res.alternatives:
            st.info("No nearby alternative ports identified in this regional cluster.")
        else:
            alt_cols = st.columns(len(opt_res.alternatives))
            for i, alt in enumerate(opt_res.alternatives):
                with alt_cols[i]:
                    if not alt.is_physically_feasible:
                        st.markdown(f"""
                        <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 16px; min-height: 380px;">
                            <h4 style="margin: 0 0 6px 0; color: #64748B;">{alt.candidate_port.port_name}</h4>
                            <div style="background-color: #FEE2E2; color: #991B1B; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 700; display: inline-block; margin-bottom: 10px;">
                                ❌ Incompatible Vessel Size
                            </div>
                            <p style="font-size: 0.9em; color: #64748B; margin: 6px 0;"><b>Distance:</b> {alt.distance_nm:.0f} NM ({alt.distance_km:.0f} km)</p>
                            <hr style="margin: 10px 0;">
                            <p style="font-size: 0.88em; color: #DC2626;"><b>Reason:</b><br>{alt.infeasibility_reason}</p>
                            <p style="font-size: 0.82em; color: #64748B; margin-top: 10px;">
                                Candidate limits: Max length {alt.candidate_port.max_vessel_length_m}m, Max draft {alt.candidate_port.max_vessel_draft_m}m
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        dc = alt.diversion_cost
                        is_rec = alt.is_recommended
                        badge_color = "#166534" if is_rec else "#9A3412"
                        badge_bg = "#DCFCE7" if is_rec else "#FFEDD5"
                        border_color = "#22C55E" if is_rec else "#CBD5E1"
                        net_sign = "+" if dc.net_cost_difference > 0 else "-"
                        net_color = "#166534" if dc.net_cost_difference > 0 else "#DC2626"

                        st.markdown(f"""
                        <div style="background-color: #F8FAFC; border: 2px solid {border_color}; border-radius: 8px; padding: 16px; min-height: 380px;">
                            <h4 style="margin: 0 0 6px 0; color: #1E293B;">{alt.candidate_port.port_name}</h4>
                            <div style="background-color: {badge_bg}; color: {badge_color}; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 700; display: inline-block; margin-bottom: 10px;">
                                {alt.summary_verdict}
                            </div>
                            <div style="font-size: 0.88em; color: #475569; margin-bottom: 4px;">
                                📍 <b>Additional Transit:</b> {alt.distance_nm:.0f} NM ({dc.extra_sailing_hours:.1f}h @ {custom_cost_params.vessel_speed_knots} kts)
                            </div>
                            <div style="font-size: 0.88em; color: #475569; margin-bottom: 4px;">
                                ⛽ <b>Extra Transit Bunker:</b> {dc.extra_sailing_fuel_mt:.1f} MT (${dc.extra_sailing_fuel_cost:,.0f})
                            </div>
                            <div style="font-size: 0.88em; color: #475569; margin-bottom: 4px;">
                                ⏳ <b>Expected Port Wait:</b> {alt.expected_wait_hours:.1f} hours
                            </div>
                            <div style="font-size: 0.88em; color: #475569; margin-bottom: 6px;">
                                💰 <b>Total Diversion Cost:</b> ${dc.total_diversion_cost:,.0f}
                            </div>
                            <div style="background-color: white; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 10px; margin: 10px 0;">
                                <div style="font-size: 0.8em; color: #64748B; text-transform: uppercase;">Net Economic Delta vs Target:</div>
                                <div style="font-size: 1.15em; font-weight: 800; color: {net_color};">
                                    {net_sign}${abs(dc.net_cost_difference):,.0f} {'SAVINGS' if dc.net_cost_difference > 0 else 'PREMIUM'}
                                </div>
                                <div style="font-size: 0.8em; color: #64748B; margin-top: 2px;">
                                    Turnaround Time: {dc.time_difference_hours:+.1f}h vs target
                                </div>
                            </div>
                            <div style="font-size: 0.82em; color: #059669; margin-top: 6px;">
                                {'<br>'.join('• ' + p for p in alt.pros[:2])}
                            </div>
                            <div style="font-size: 0.82em; color: #DC2626; margin-top: 4px;">
                                {'<br>'.join('• ' + c for c in alt.cons[:2])}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # ── Visual Cost Comparison Bar Chart ──────────────────────────────
            st.markdown("#### 📊 Comparative Financial Modeling: Target Port vs Alternatives")
            comp_rows = [{
                "Port": f"🎯 {eval_target_port.port_name} (Target)",
                "Transit Fuel ($)": 0.0,
                "Waiting OPEX ($)": t_ana.cost_breakdown.wait_opex_cost,
                "Demurrage ($)": t_ana.cost_breakdown.demurrage_cost,
                "Port & Crane Tariffs ($)": t_ana.cost_breakdown.port_handling_cost + t_ana.cost_breakdown.crane_operating_cost,
                "Anchor Fuel ($)": t_ana.cost_breakdown.wait_idle_fuel_cost,
            }]

            for alt in opt_res.alternatives:
                if alt.is_physically_feasible and alt.diversion_cost:
                    dc = alt.diversion_cost
                    comp_rows.append({
                        "Port": f"⚓ {alt.candidate_port.port_name}",
                        "Transit Fuel ($)": dc.extra_sailing_fuel_cost,
                        "Waiting OPEX ($)": dc.wait_opex_cost_alt + dc.extra_sailing_opex_cost,
                        "Demurrage ($)": dc.demurrage_cost_alt,
                        "Port & Crane Tariffs ($)": dc.port_handling_cost_alt + dc.diversion_tariff_cost + dc.crane_operating_cost_alt,
                        "Anchor Fuel ($)": dc.wait_idle_fuel_cost_alt,
                    })

            df_cost_comp = pd.DataFrame(comp_rows)
            fig_cost = px.bar(
                df_cost_comp,
                x="Port",
                y=["Transit Fuel ($)", "Waiting OPEX ($)", "Demurrage ($)", "Port & Crane Tariffs ($)", "Anchor Fuel ($)"],
                title="<b>Total Voyage & Port Call Cost Component Comparison (USD)</b>",
                barmode="stack",
                color_discrete_sequence=["#F59E0B", "#EF4444", "#DC2626", "#3B82F6", "#8B5CF6"],
            )
            fig_cost.update_layout(height=340, margin=dict(l=20, r=20, t=40, b=20), legend_title="Cost Component")
            st.plotly_chart(fig_cost, use_container_width=True)

            # Detailed Comparative Data Table
            table_rows = []
            for alt in opt_res.alternatives:
                if alt.is_physically_feasible and alt.diversion_cost:
                    dc = alt.diversion_cost
                    table_rows.append({
                        "Candidate Port": alt.candidate_port.port_name,
                        "Extra Dist (NM)": f"{alt.distance_nm:.0f} NM",
                        "Transit Fuel (MT)": f"{dc.extra_sailing_fuel_mt:.1f} MT",
                        "Extra Fuel Cost": f"${dc.extra_sailing_fuel_cost:,.0f}",
                        "Port Wait (h)": f"{alt.expected_wait_hours:.1f}h",
                        "Demurrage Cost": f"${dc.demurrage_cost_alt:,.0f}",
                        "Total Voyage Cost": f"${dc.total_diversion_cost:,.0f}",
                        "Net vs Target": f"{'+' if dc.net_cost_difference > 0 else ''}${dc.net_cost_difference:,.0f}",
                        "Time Delta": f"{dc.time_difference_hours:+.1f}h",
                        "Status": alt.summary_verdict,
                    })
            if table_rows:
                st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)


    # ──────────────────────────────────────────────────────────────────────────
    # TAB 4: WHAT-IF SIMULATION
    # ──────────────────────────────────────────────────────────────────────────
    with tab_sim:
        st.subheader("Recalculating What-If Simulation Sandbox (PRD 11.9)")
        st.caption("Non-cosmetic simulation: every what-if scenario re-executes the full prediction, CP-SAT optimization, planning, and routing pipeline.")

        scol1, scol2, scol3 = st.columns(3)
        with scol1:
            sim_param_type = st.selectbox(
                "Parameter Modification",
                ["berth_count", "crane_count", "arrival_surge", "service_duration",
                 "crane_outage", "berth_maintenance", "weather_disruption", "port_selection"],
                format_func=lambda p: {
                    "berth_count": "🏗️ Alter Berth Count at Port",
                    "crane_count": "🦾 Alter Crane Count at Port",
                    "arrival_surge": "⚡ Fleet Arrival Surge / Compression",
                    "service_duration": "⏱️ Cargo Handling Duration Multiplier",
                    "crane_outage": "❌ Crane Sudden Outage",
                    "berth_maintenance": "🛠️ Berth Offline for Maintenance",
                    "weather_disruption": "⛈️ Severe Weather Disruption (+50% Service Time)",
                    "port_selection": "🔀 Fleet Divert to Specific Port",
                }.get(p, p),
            )
        with scol2:
            sim_port = st.selectbox("Target Port", [p.port_id for p in ports])
        with scol3:
            selected_crane_out = "C-1"
            selected_berth_maint = "B-1"
            if sim_param_type in ("berth_count", "crane_count"):
                sim_val = float(st.number_input("New Resource Count", min_value=1, max_value=10, value=2))
            elif sim_param_type in ("arrival_surge", "service_duration"):
                sim_val = float(st.slider("Multiplier Factor", min_value=0.5, max_value=3.0, value=1.5, step=0.1))
            elif sim_param_type == "crane_outage":
                sim_port_cranes = [c.crane_id for c in cranes if c.port_id == sim_port]
                selected_crane_out = st.selectbox("Crane to take offline", sim_port_cranes if sim_port_cranes else ["C-1"])
                sim_val = 0.0
            elif sim_param_type == "berth_maintenance":
                sim_port_berths = [b.berth_id for b in berths if b.port_id == sim_port]
                selected_berth_maint = st.selectbox("Berth to take offline", sim_port_berths if sim_port_berths else ["B-1"])
                sim_val = 0.0
            else:
                sim_val = 1.0

        col_sbtn1, col_sbtn2 = st.columns([1, 4])
        with col_sbtn1:
            if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
                param_obj = SimulationParam(
                    param_type=sim_param_type,
                    port_id=sim_port,
                    change_value=sim_val,
                    crane_id=selected_crane_out if sim_param_type == "crane_outage" else None,
                    berth_id=selected_berth_maint if sim_param_type == "berth_maintenance" else None,
                )
                sim_res = run_simulation(scenario, [param_obj], horizon)
                st.session_state["sim"] = sim_res
        with col_sbtn2:
            if st.button("🔄 Reset to Baseline Scenario", use_container_width=False):
                st.session_state["sim"] = None
                st.rerun()

        sim: SimulationResult = st.session_state.get("sim")
        if sim:
            st.markdown("#### Simulation Impact & Delta Comparison")
            sim_col1, sim_col2, sim_col3, sim_col4 = st.columns(4)
            with sim_col1:
                st.metric("Optimized Wait Time", f"{sim.scenario_optimized.avg_wait_hours:.1f}h",
                          delta=f"{sim.kpi_comparison['opt_wait_delta']:+.1f}h vs baseline", delta_color="inverse")
            with sim_col2:
                st.metric("Optimized Delay", f"{sim.scenario_optimized.avg_delay_hours:.1f}h",
                          delta=f"{sim.kpi_comparison['opt_avg_delay_delta']:+.1f}h vs baseline", delta_color="inverse")
            with sim_col3:
                st.metric("Deferred Vessels", f"{sim.scenario_optimized.deferred_count}",
                          delta=f"{sim.kpi_comparison['opt_deferral_delta']:+d} vs baseline", delta_color="inverse")
            with sim_col4:
                st.metric("FCFS Baseline Wait", f"{sim.scenario_fcfs.avg_wait_hours:.1f}h",
                          delta=f"{sim.kpi_comparison['fcfs_wait_delta']:+.1f}h vs baseline", delta_color="inverse")

            st.markdown("#### Simulated Scenario Berth Schedule")
            fig_sim_gantt = _build_gantt_chart(sim.scenario_optimized.assignments, vessels_by_id, horizon)
            st.plotly_chart(fig_sim_gantt, use_container_width=True)

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 5: ALERTS HUB
    # ──────────────────────────────────────────────────────────────────────────
    with tab_alerts:
        st.subheader("Operational Alerts Hub (PRD 11.10)")
        st.caption("All alerts strictly include 5 mandatory fields: Severity, Entity, Trigger, Explanation, and Recommended Action.")

        all_alerts = _generate_all_system_alerts(forecasts, opt_p, st.session_state.get("sim"))

        if not all_alerts:
            st.success("✅ No operational warnings or critical saturation risks detected.")
        else:
            for a in all_alerts:
                sev = a.get("severity", "info").lower()
                css_class = f"alert-{sev}" if sev in ("critical", "warning", "info") else "alert-info"
                icon = "🚨" if sev == "critical" else ("⚠️" if sev == "warning" else "ℹ️")

                st.markdown(f"""
                <div class="alert-box {css_class}">
                    <div style="font-weight: 700; font-size: 1.05em; margin-bottom: 4px;">
                        {icon} [{sev.upper()}] {a['entity']} — {a['trigger']}
                    </div>
                    <div style="margin-bottom: 4px;"><b>Explanation:</b> {a['explanation']}</div>
                    <div><b>Recommended Action:</b> <i>{a['recommended_action']}</i></div>
                </div>
                """, unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 6: EXPORT & METADATA
    # ──────────────────────────────────────────────────────────────────────────
    with tab_export:
        st.subheader("Export Schedule Data & Solver Diagnostics")
        st.caption("Download schedules in CSV / JSON format for operational dispatch.")

        dcol1, dcol2 = st.columns(2)
        with dcol1:
            csv_content = _assignments_to_csv(opt_p.assignments)
            st.download_button(
                "📥 Download Optimized Schedule (CSV)",
                data=csv_content,
                file_name=f"portpilot_schedule_{selected_port_spec.port_name.replace(' ', '_')}_{scenario_name}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dcol2:
            json_content = _assignments_to_json(opt_p.assignments)
            st.download_button(
                "📥 Download Optimized Schedule (JSON)",
                data=json_content,
                file_name=f"portpilot_schedule_{selected_port_spec.port_name.replace(' ', '_')}_{scenario_name}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("#### Solver Diagnostics & Settings")
        if opt_p and opt_p.solver_result:
            st.json({
                "selected_port": selected_port_spec.port_name,
                "port_id": selected_port_id,
                "incoming_vessels": len(port_vessels),
                "port_berths": len(port_berths),
                "port_cranes": len(port_cranes),
                "pre_occupied_berths": len(selected_live_state.occupied_berths),
                "solver_method": opt_p.solver_result.method,
                "solver_status": opt_p.solver_result.status.value,
                "runtime_seconds": opt_p.solver_result.runtime_seconds,
                "time_limit_seconds": opt_p.solver_result.time_limit_seconds,
                "fallback_used": opt_p.solver_result.fallback_used,
                "fallback_reason": opt_p.solver_result.fallback_reason,
                "objective_value": opt_p.solver_result.objective_value,
                "metadata": opt_p.solver_result.solver_metadata,
            })


if __name__ == "__main__":
    main()
