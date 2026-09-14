"""PortPilot AI — Streamlit Dashboard.

Explainable Port Congestion Forecasting & Rolling 72-Hour Planning System.
Launch: python -m streamlit run src/app/dashboard.py
"""

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
from src.config.ports import DEFAULT_PORTS
from src.data.live.live_manager import get_live_data_manager


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


def _build_gantt_chart(assignments, vessels_by_id, horizon_hours=72.0):
    scheduled = [a for a in assignments if not a.deferred and a.end_time > a.start_time]
    if not scheduled:
        fig = go.Figure()
        fig.add_annotation(text="No scheduled vessels within the horizon window", showarrow=False, font=dict(size=14))
        fig.update_layout(height=280)
        return fig

    # Anchor to reference time for timeline
    base_time = datetime(2026, 9, 15, 0, 0)
    data = []
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
        category_orders={"Priority": ["Priority 1", "Priority 2", "Priority 3"]},
        color_discrete_map={
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
        height=340,
        legend_title="Vessel Priority",
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    return fig


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

    # Sidebar Data Stream Mode Selector
    st.sidebar.header("📡 Data Stream Mode")
    mode_selection = st.sidebar.radio(
        "Ingestion Source",
        ["🟢 Live Operational Stream (Real-Time Ingestion)", "🟡 Synthetic Demo Scenarios"],
        index=0,
    )
    is_live_mode = "Live" in mode_selection

    # Dynamic Banner
    if is_live_mode:
        st.markdown(f'<div class="live-badge">🟢 {settings.live_data_banner}</div>', unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ {settings.demo_data_banner}")

    # Sidebar Controls
    st.sidebar.header("🌍 Port Region & Hubs")
    from src.config.ports import PORT_CLUSTERS
    selected_cluster_key = st.sidebar.selectbox(
        "Port Region Cluster",
        list(PORT_CLUSTERS.keys()),
        format_func=lambda k: PORT_CLUSTERS[k]["cluster_name"],
        index=0,
    )

    st.sidebar.header("🕹️ Planning Horizon Controls")
    horizon = st.sidebar.slider("Planning Horizon (Hours)", 12, 168, settings.planning_horizon_hours, step=6)
    num_vessels = st.sidebar.slider("Monitored Vessel Fleet Size", 5, 50, settings.default_num_vessels, step=1)

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

        # Sidebar Live Health Badges
        with st.sidebar.expander("🌐 Live Streams Health", expanded=True):
            st.caption(f"**Last Synchronized:** `{last_sync}`")
            health = scenario.get("health", {})
            for k, v in health.items():
                st.write(f"• **{k.replace('_', ' ').title()}:** `{v}`")

    else:
        scenario_name = st.sidebar.selectbox(
            "Operational Scenario",
            [
                "normal",
                "high_arrival",
                "crane_outage",
                "berth_maintenance",
                "weather_disruption",
                "congestion",
            ],
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

    vessels_by_id = {v.vessel_id: v for v in vessels}

    # Data Validation Checks
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

    # Live Weather Cards Widget (if in live mode)
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

    # Top Overview KPIs
    forecasts = predict_congestion(vessels, berths, cranes, horizon)
    avg_berth_util = sum(f.berth_utilization for f in forecasts) / max(len(forecasts), 1)
    high_cong_count = sum(1 for f in forecasts if f.congestion_level in (CongestionLevel.HIGH, CongestionLevel.CRITICAL))

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

    st.markdown("---")

    # Main Tabs
    tab_forecast, tab_plans, tab_router, tab_sim, tab_alerts, tab_export = st.tabs([
        "📊 1. Congestion Forecasts",
        "⚡ 2. 72-Hour Optimization Plans",
        "🗺️ 3. Alternative Port Recommender",
        "🧪 4. What-If Simulation Engine",
        "🚨 5. Operational Alerts Hub",
        "💾 6. Schedule Export & Metadata",
    ])

    # ---------------- TAB 1: CONGESTION FORECASTS ----------------
    with tab_forecast:
        st.subheader("Port Congestion Forecast (72-Hour Projection)")
        st.caption("Transparent baseline congestion modeling following PRD 11.3 fractional queue policies.")

        port_cols = st.columns(len(forecasts))
        for idx, f in enumerate(forecasts):
            port_obj = next((p for p in ports if p.port_id == f.port_id), None)
            port_name = port_obj.port_name if port_obj else f.port_id

            with port_cols[idx]:
                level_color = {
                    CongestionLevel.LOW: "🟢 #10B981",
                    CongestionLevel.MEDIUM: "🟡 #F59E0B",
                    CongestionLevel.HIGH: "🟠 #F97316",
                    CongestionLevel.CRITICAL: "🔴 #EF4444",
                }.get(f.congestion_level, "⚪")

                st.markdown(f"""
                <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
                    <h4 style="margin: 0 0 8px 0; color: #1E293B;">{port_name} <span style="font-size: 0.8em; color: #64748B;">({f.port_id})</span></h4>
                    <p style="margin: 4px 0; font-size: 1.1em; font-weight: 600;">Status: {level_color.split()[0]} {f.congestion_level.value}</p>
                    <p style="margin: 4px 0; color: #475569;"><b>Queue Fraction:</b> {f.predicted_queue_length:.2f}</p>
                    <p style="margin: 4px 0; font-size: 0.85em; color: #64748B;"><i>{_format_queue_display(f.predicted_queue_length)}</i></p>
                    <p style="margin: 4px 0; color: #475569;"><b>Expected Wait:</b> {'Qualified / Minimal (< 0.5h)' if f.congestion_level == CongestionLevel.LOW else f'{f.expected_wait_hours:.1f}h'}</p>
                    <p style="margin: 4px 0; color: #475569;"><b>Berth Utilization:</b> {f.berth_utilization:.0%}</p>
                    <p style="margin: 4px 0; color: #475569;"><b>Confidence:</b> {f.confidence:.0%}</p>
                    <hr style="margin: 8px 0;">
                    <p style="margin: 0; font-size: 0.82em; color: #475569;"><b>Drivers:</b> {', '.join(f.contributing_factors)}</p>
                </div>
                """, unsafe_allow_html=True)

        # Plotly Congestion Bar Chart
        df_cong = pd.DataFrame([
            {
                "Port": f"{next((p.port_name for p in ports if p.port_id == f.port_id), f.port_id)} ({f.port_id})",
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
            title="<b>Port Resource Utilization & Saturation</b>",
            color_discrete_sequence=["#3B82F6", "#8B5CF6"],
        )
        fig_cong.update_layout(height=290, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_cong, use_container_width=True)

    # ---------------- TAB 2: PLANS (FCFS vs OPTIMIZED) ----------------
    with tab_plans:
        st.subheader("72-Hour Berth & Crane Allocation: FCFS vs CP-SAT Optimization")
        st.caption("Fair, consistent evaluation population comparing standard FCFS queueing against OR-Tools CP-SAT constraint-optimized allocation.")

        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            if st.button("▶️ Run FCFS Baseline", use_container_width=True):
                st.session_state["fcfs"] = generate_fcfs(vessels, berths, cranes, horizon)
        with col_btn2:
            if st.button("🚀 Solve with OR-Tools CP-SAT", type="primary", use_container_width=True):
                st.session_state["optimized"] = generate_optimized(vessels, berths, cranes, horizon)
        with col_btn3:
            if st.button("🔄 Generate & Compare Both Plans", use_container_width=True):
                st.session_state["fcfs"] = generate_fcfs(vessels, berths, cranes, horizon)
                st.session_state["optimized"] = generate_optimized(vessels, berths, cranes, horizon)

        # Ensure plans generated for first run
        if "fcfs" not in st.session_state:
            st.session_state["fcfs"] = generate_fcfs(vessels, berths, cranes, horizon)
        if "optimized" not in st.session_state:
            st.session_state["optimized"] = generate_optimized(vessels, berths, cranes, horizon)

        fcfs_p: PlanResult = st.session_state.get("fcfs")
        opt_p: PlanResult = st.session_state.get("optimized")

        # Side-by-side KPI comparison cards
        st.markdown("#### Plan Performance Metrics")
        mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
        with mcol1:
            wait_diff = round(opt_p.avg_wait_hours - fcfs_p.avg_wait_hours, 1)
            st.metric(
                "Average Wait Time",
                f"{opt_p.avg_wait_hours:.1f} h",
                delta=f"{wait_diff} h vs FCFS ({fcfs_p.avg_wait_hours:.1f}h)",
                delta_color="inverse"
            )
        with mcol2:
            delay_diff = round(opt_p.avg_delay_hours - fcfs_p.avg_delay_hours, 1)
            st.metric(
                "Average Delay",
                f"{opt_p.avg_delay_hours:.1f} h",
                delta=f"{delay_diff} h vs FCFS",
                delta_color="inverse"
            )
        with mcol3:
            def_diff = opt_p.deferred_count - fcfs_p.deferred_count
            st.metric(
                "Deferred Vessels",
                f"{opt_p.deferred_count} / {len(vessels)}",
                delta=f"{def_diff} vs FCFS ({fcfs_p.deferred_count})",
                delta_color="inverse"
            )
        with mcol4:
            st.metric(
                "Berth Utilization",
                f"{opt_p.berth_utilization:.0%}",
                delta=f"{(opt_p.berth_utilization - fcfs_p.berth_utilization):.0%} vs FCFS"
            )
        with mcol5:
            solver_stat = opt_p.solver_result.status.value if opt_p.solver_result else "FEASIBLE"
            st.metric("Solver Status", f"{solver_stat}", delta=f"{opt_p.runtime_seconds:.3f}s runtime")

        # Schedule Timeline Gantt Chart
        st.markdown("#### Optimized Berth Allocation Schedule")
        fig_gantt = _build_gantt_chart(opt_p.assignments, vessels_by_id, horizon)
        st.plotly_chart(fig_gantt, use_container_width=True)

        # Plan View Selector
        plan_view = st.radio("Select Schedule Table View", ["Optimized Plan (CP-SAT)", "Baseline Plan (FCFS)"], horizontal=True)
        active_plan = opt_p if "Optimized" in plan_view else fcfs_p
        df_schedule = _format_schedule_dataframe(active_plan.assignments, vessels_by_id)
        st.dataframe(df_schedule, use_container_width=True, hide_index=True)

    # ---------------- TAB 3: ALTERNATIVE PORT RECOMMENDER ----------------
    with tab_router:
        st.subheader("Alternative Port Recommendation Engine (PRD 11.8)")
        st.caption("Multi-criteria weighted scoring engine evaluating expected delays, vessel physical feasibility, diversion cost, and reliability.")

        sel_vessel_id = st.selectbox(
            "Select Vessel to Evaluate for Potential Diversion",
            [v.vessel_id for v in vessels],
            format_func=lambda vid: f"{vid} — {vessels_by_id[vid].vessel_name} (Length: {vessels_by_id[vid].vessel_length_m}m, Draft: {vessels_by_id[vid].vessel_draft_m}m, Preferred: {vessels_by_id[vid].preferred_port})",
        )
        selected_vessel = vessels_by_id[sel_vessel_id]

        recs = recommend_alternative_ports(selected_vessel, ports, forecasts, top_n=3)

        if not recs:
            st.info("ℹ️ No alternative ports available or vessel specifications exceed candidate berth limits.")
        else:
            rcols = st.columns(len(recs))
            for i, r in enumerate(recs):
                with rcols[i]:
                    st.markdown(f"""
                    <div style="background-color: #F8FAFC; border: 2px solid #3B82F6; border-radius: 8px; padding: 16px;">
                        <h4 style="margin: 0 0 8px 0; color: #1E293B;">Rank #{i+1}: {r.recommended_port_name}</h4>
                        <p style="margin: 4px 0; font-size: 1.25em; font-weight: 700; color: #2563EB;">Score: {r.score:.3f} / 1.000</p>
                        <p style="margin: 4px 0; color: #475569;"><b>Confidence:</b> {r.confidence:.0%}</p>
                        <p style="margin: 4px 0; font-size: 0.9em; color: #475569;"><b>Rationale:</b> {r.rationale}</p>
                        <hr style="margin: 8px 0;">
                        <p style="margin: 4px 0; color: #059669; font-size: 0.85em;"><b>✅ Advantages:</b><br>{'<br>'.join('• ' + a for a in r.advantages)}</p>
                        <p style="margin: 4px 0; color: #DC2626; font-size: 0.85em;"><b>⚠️ Disadvantages:</b><br>{'<br>'.join('• ' + d for d in r.disadvantages) if r.disadvantages else '• None noted'}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # Component breakdown chart
            st.markdown("#### Recommendation Scoring Components Breakdown")
            df_comp = pd.DataFrame([
                {
                    "Port": r.recommended_port_name,
                    "Expected Delay Score": r.components["expected_delay"],
                    "Feasibility Score": r.components["feasibility"],
                    "Diversion Cost Score": r.components["diversion_cost"],
                    "Congestion Risk Score": r.components["congestion_risk"],
                    "Reliability Score": r.components["reliability"],
                }
                for r in recs
            ])
            fig_rad = px.bar(
                df_comp,
                x="Port",
                y=["Expected Delay Score", "Feasibility Score", "Diversion Cost Score", "Congestion Risk Score", "Reliability Score"],
                barmode="group",
                title="<b>Scoring Components Comparison</b>",
            )
            fig_rad.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_rad, use_container_width=True)

    # ---------------- TAB 4: WHAT-IF SIMULATION ----------------
    with tab_sim:
        st.subheader("Recalculating What-If Simulation Sandbox (PRD 11.9)")
        st.caption("Non-cosmetic simulation: every what-if scenario re-executes the full prediction, CP-SAT optimization, planning, and routing pipeline.")

        scol1, scol2, scol3 = st.columns(3)
        with scol1:
            sim_param_type = st.selectbox(
                "Parameter Modification",
                [
                    "berth_count",
                    "crane_count",
                    "arrival_surge",
                    "service_duration",
                    "crane_outage",
                    "berth_maintenance",
                    "weather_disruption",
                    "port_selection",
                ],
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
            if sim_param_type in ("berth_count", "crane_count"):
                sim_val = float(st.number_input("New Resource Count", min_value=1, max_value=10, value=2))
            elif sim_param_type in ("arrival_surge", "service_duration"):
                sim_val = float(st.slider("Multiplier Factor", min_value=0.5, max_value=3.0, value=1.5, step=0.1))
            elif sim_param_type == "crane_outage":
                port_cranes = [c.crane_id for c in cranes if c.port_id == sim_port]
                selected_crane_out = st.selectbox("Crane to take offline", port_cranes if port_cranes else ["C-1"])
                sim_val = 0.0
            elif sim_param_type == "berth_maintenance":
                port_berths = [b.berth_id for b in berths if b.port_id == sim_port]
                selected_berth_maint = st.selectbox("Berth to take offline", port_berths if port_berths else ["B-1"])
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
                st.metric(
                    "Optimized Wait Time",
                    f"{sim.scenario_optimized.avg_wait_hours:.1f}h",
                    delta=f"{sim.kpi_comparison['opt_wait_delta']:+.1f}h vs baseline",
                    delta_color="inverse"
                )
            with sim_col2:
                st.metric(
                    "Optimized Delay",
                    f"{sim.scenario_optimized.avg_delay_hours:.1f}h",
                    delta=f"{sim.kpi_comparison['opt_avg_delay_delta']:+.1f}h vs baseline",
                    delta_color="inverse"
                )
            with sim_col3:
                st.metric(
                    "Deferred Vessels",
                    f"{sim.scenario_optimized.deferred_count}",
                    delta=f"{sim.kpi_comparison['opt_deferral_delta']:+d} vs baseline",
                    delta_color="inverse"
                )
            with sim_col4:
                st.metric(
                    "FCFS Baseline Wait",
                    f"{sim.scenario_fcfs.avg_wait_hours:.1f}h",
                    delta=f"{sim.kpi_comparison['fcfs_wait_delta']:+.1f}h vs baseline",
                    delta_color="inverse"
                )

            # Timeline for simulation
            st.markdown("#### Simulated Scenario Berth Schedule")
            fig_sim_gantt = _build_gantt_chart(sim.scenario_optimized.assignments, vessels_by_id, horizon)
            st.plotly_chart(fig_sim_gantt, use_container_width=True)

    # ---------------- TAB 5: ALERTS HUB ----------------
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

    # ---------------- TAB 6: EXPORT & METADATA ----------------
    with tab_export:
        st.subheader("Export Schedule Data & Solver Diagnostics")
        st.caption("Download schedules in CSV / JSON format for operational dispatch.")

        dcol1, dcol2 = st.columns(2)
        with dcol1:
            csv_content = _assignments_to_csv(opt_p.assignments)
            st.download_button(
                "📥 Download Optimized Schedule (CSV)",
                data=csv_content,
                file_name=f"portpilot_schedule_{scenario_name}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dcol2:
            json_content = _assignments_to_json(opt_p.assignments)
            st.download_button(
                "📥 Download Optimized Schedule (JSON)",
                data=json_content,
                file_name=f"portpilot_schedule_{scenario_name}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("#### Solver Diagnostics & Settings")
        if opt_p and opt_p.solver_result:
            st.json({
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
