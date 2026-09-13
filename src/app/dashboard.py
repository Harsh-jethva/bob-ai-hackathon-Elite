import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # run from project root
import streamlit as st, pandas as pd
import plotly.express as px, plotly.graph_objects as go
from copy import deepcopy
from src.config.ports import PORTS, DIVERSION_COST_H
from src.config.settings import CRANE_RATE_TEU_PER_H
from src.models.congestion_model import CongestionModel
from src.optimization.planner import build_plan
from src.scenarios.demo import load_scenario

st.set_page_config(page_title="AI Port Manager - 72h Operations Plan", layout="wide")
st.title("🚢 AI Port Manager — Congestion Prediction & 72h Plan")

@st.cache_resource
def model():
    return CongestionModel.load()

@st.cache_data
def run_plan(seed, weather, crane_out, burst):
    now, live, inbound = load_scenario(seed, add_burst=burst)
    ports = deepcopy(PORTS)
    if crane_out:                                        # what-if: 2 cranes unavailable at PORT_A
        ports["PORT_A"]["n_cranes"] = max(2, ports["PORT_A"]["n_cranes"] - 2)
    return build_plan(now, live, inbound, model(), ports, DIVERSION_COST_H,
                      crane_rate=CRANE_RATE_TEU_PER_H * weather)

with st.sidebar:
    st.header("Scenario controls")
    seed = st.slider("Scenario seed", 1, 30, 11)
    weather = st.slider("Weather productivity factor", 0.5, 1.0, 1.0, 0.05)
    crane_out = st.checkbox("⚙️ Simulate 2-crane outage (Port A)")
    burst = st.checkbox("🚨 Inject 11 AM arrival burst")

plan = run_plan(seed, weather, crane_out, burst)
k = plan["kpis"]
s = plan["schedule"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Vessels in 72h plan", k["vessels_planned"])
c2.metric("Avg waiting (optimized)", f"{k['avg_wait_opt_h']} h")
c3.metric("Avg waiting (FCFS baseline)", f"{k['avg_wait_fcfs_h']} h")
c4.metric("Improvement vs FCFS", f"{k['improvement_pct']} %",
          f"-{max(0.0, k['avg_wait_fcfs_h'] - k['avg_wait_opt_h']):.1f} h")
c5.metric("Recommended diversions", k["diversions"])

tab1, tab2, tab3, tab4 = st.tabs(["🔮 Congestion forecast", "📅 72h Plan (Gantt)",
                                  "⚙️ Berth & crane assignments", "🔀 Recommendations"])

with tab1:
    for pid, fc in plan["forecast"].items():
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=fc.bucket_start, y=fc.queue_pred, name="Predicted waiting ships",
            mode="lines+markers",
            marker=dict(color=fc.level.map({"LOW": "green", "MEDIUM": "orange", "HIGH": "red"}),
                        size=10)))
        nb = len(PORTS[pid]["berths"])
        fig.add_hline(y=0.9 * nb, line_dash="dash", line_color="red",
                      annotation_text=f"HIGH threshold ({0.9 * nb:.0f})")
        fig.add_hline(y=0.4 * nb, line_dash="dot", line_color="orange")
        fig.update_layout(title=f"{PORTS[pid]['name']} — predicted queue, next 72h (6h buckets)",
                          yaxis_title="Waiting ships", height=350)
        st.plotly_chart(fig, width="stretch")

with tab2:
    if len(s) == 0:
        st.info("No vessels to schedule in this scenario.")
    else:
        fig = px.timeline(s, x_start="start", x_end="end", y="berth", color="priority",
                          color_continuous_scale="RdYlGn_r",
                          hover_data=["name", "teu", "cranes", "wait_h"],
                          category_orders={"berth": sorted(s.berth.unique())})
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(title="Berth schedule — next 72h (color = priority)", height=450)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(s[["name", "port", "berth", "cranes", "eta", "start", "end", "wait_h", "teu"]])

with tab3:
    if len(s) == 0:
        st.info("No vessels to schedule in this scenario.")
    else:
        util = (s.assign(busy_h=(s.end - s.start).dt.total_seconds() / 3600)
                 .groupby("berth", as_index=False)["busy_h"].sum())
        st.bar_chart(util.set_index("berth")["busy_h"])
        st.caption("Planned busy hours per berth over the 72h window.")
        st.dataframe(s[["vessel_id", "berth", "cranes", "start", "end"]]
                     .assign(cranes=lambda d: d.cranes.map(lambda kk: "🔧 " * int(kk))))

with tab4:
    if len(plan["recs"]):
        for r in plan["recs"].itertuples():
            st.warning(f"🔀 **{r.name}** ({r.teu:,} TEU, ETA {r.eta:%d %b %H:%M}) → "
                       f"divert **{r.from_port} → {r.to_port}** (+{r.extra_steaming_h}h steaming). "
                       f"Reason: {r.reason}")
        st.dataframe(plan["recs"])
    else:
        st.success("✅ No diversions needed — all ports within capacity for the next 72h.")

st.download_button("⬇️ Download full 72h plan (CSV)",
                   s.to_csv(index=False).encode(),
                   "72h_port_plan.csv", "text/csv")