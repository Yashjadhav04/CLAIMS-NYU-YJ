"""Interactive Part D cost trend monitor.  Run:  PYTHONPATH=src streamlit run app/streamlit_app.py"""
import streamlit as st

from partd import charts

st.set_page_config(page_title="Part D Cost Trend Monitor", layout="wide")


@st.cache_data(show_spinner=False)
def _load():
    d = charts.load_data()
    return d, *charts.compute_kpis(d)


d, kpis, insights = _load()

st.title("Medicare Part D Cost Trend Analysis")
st.caption("Synthetic plan-level PDE data. Benefit parameters are illustrative. Not UnitedHealth Group data.")

with st.sidebar:
    st.header("Segment view")
    by = st.radio("Split PMPM by", ["lis_flag", "plan_type"], format_func=lambda v: {"lis_flag": "Low-income subsidy", "plan_type": "Plan type"}[v])
    measure = st.radio("Measure", ["net_plan_liability", "gross_drug_cost"], format_func=lambda v: "Net plan liability" if v.startswith("net") else "Gross drug cost")

c = st.columns(6)
tiles = [
    ("FY projected net plan", f"${kpis['fy_projection']/1e6:.1f}M", f"budget ${kpis['fy_budget']/1e6:.1f}M"),
    ("FY variance", f"{kpis['fy_variance_pct']:+.1%}", f"{kpis['fy_variance_low']:+.1%} to {kpis['fy_variance_high']:+.1%}"),
    ("YTD net PMPM", f"${kpis['ytd_net_plan_pmpm']:,.0f}", f"budget ${kpis['ytd_budget_pmpm']:,.0f}"),
    ("Gross PMPM YoY", f"{kpis['gross_trend_pct']:+.1%}", "YTD"),
    ("Catastrophic", f"{kpis['cat_now']:.1%}", f"{kpis['cat_prior']:.1%} a year ago"),
    ("Unresolved rejects", f"${kpis['unresolved_dollars']/1e3:,.0f}K", "gross cost"),
]
for col, (a, b, s) in zip(c, tiles):
    col.metric(a, b, s, delta_color="off")

with st.expander("Key observations (auto-generated)", expanded=True):
    for i in insights:
        st.markdown(f"- {i}")

t1, t2, t3, t4 = st.tabs(["Overview", "Trend drivers", "Benefit and members", "Data quality"])
with t1:
    st.plotly_chart(charts.ALL_FIGS["pmpm_vs_budget"](d), width="stretch")
    st.plotly_chart(charts.fig_pmpm_segments(d["pmpm_seg"], by, measure), width="stretch")
    st.plotly_chart(charts.ALL_FIGS["variance"](d), width="stretch")
with t2:
    st.plotly_chart(charts.ALL_FIGS["waterfall_gross"](d), width="stretch")
    st.plotly_chart(charts.ALL_FIGS["waterfall_net"](d), width="stretch")
    st.plotly_chart(charts.ALL_FIGS["movers"](d), width="stretch")
with t3:
    for k in ("who_pays", "cat", "top_drugs", "concentration"):
        st.plotly_chart(charts.ALL_FIGS[k](d), width="stretch")
with t4:
    for k in ("edits", "completion"):
        st.plotly_chart(charts.ALL_FIGS[k](d), width="stretch")
    st.subheader("Forecast backtest")
    st.dataframe(d["backtest"].round(4), hide_index=True)
    st.caption("The backtest contains few observations; method selection and interval width are provisional.")
