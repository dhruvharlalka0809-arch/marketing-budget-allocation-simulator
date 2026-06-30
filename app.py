import pandas as pd
import streamlit as st

from src.budget_model import (
    AllocationWeights,
    build_budget_bridge,
    build_scenario_memo,
    format_money,
    load_channel_data,
    simulate_budget_plan,
)


def format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(lambda value: format_money(float(value)))
    return output


def format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(lambda value: f"{value:.1%}")
    return output


def format_number_columns(df: pd.DataFrame, columns: list[str], suffix: str = "") -> pd.DataFrame:
    output = df.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(lambda value: f"{value:,.1f}{suffix}")
    return output


st.set_page_config(
    page_title="Marketing Budget Allocation Simulator",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)


@st.cache_data
def load_sample_channels() -> pd.DataFrame:
    return load_channel_data("data/channel_assumptions.csv")


st.title("Marketing Budget Allocation Simulator")
st.caption("Model channel mix, diminishing returns, CAC, payback, contribution, and revenue trade-offs before moving spend.")

with st.sidebar:
    st.header("Scenario Controls")
    uploaded_file = st.file_uploader("Upload channel assumptions CSV", type="csv")
    active_channels = pd.read_csv(uploaded_file) if uploaded_file else load_sample_channels()
    stage_filter = st.multiselect("Funnel stage filter", sorted(active_channels["Funnel_Stage"].dropna().unique()))
    scenario_channels = active_channels.copy()
    if stage_filter:
        scenario_channels = scenario_channels.loc[scenario_channels["Funnel_Stage"].isin(stage_filter)]
    st.caption("No stage selected = all channels included.")

    current_budget = float(scenario_channels["Current_Spend"].sum())
    min_budget = int(scenario_channels["Min_Spend"].sum())
    max_budget = int(scenario_channels["Max_Spend"].sum())
    total_budget = st.slider(
        "Total monthly budget",
        min_value=min_budget,
        max_value=max_budget,
        value=min(max(int(current_budget), min_budget), max_budget),
        step=5000,
    )

    st.header("Allocation Weights")
    contribution_weight = st.slider("Contribution ROI", 0.00, 0.50, 0.35, 0.01)
    cac_weight = st.slider("CAC efficiency", 0.00, 0.40, 0.25, 0.01)
    payback_weight = st.slider("Payback speed", 0.00, 0.35, 0.20, 0.01)
    retention_weight = st.slider("Retention quality", 0.00, 0.30, 0.10, 0.01)
    priority_weight = st.slider("Strategic priority", 0.00, 0.30, 0.10, 0.01)

weights = AllocationWeights(
    contribution=contribution_weight,
    cac=cac_weight,
    payback=payback_weight,
    retention=retention_weight,
    strategic_priority=priority_weight,
)

try:
    if scenario_channels.empty:
        st.warning("No channels match the selected stage filter.")
        st.stop()

    combined, summary = simulate_budget_plan(scenario_channels, total_budget, weights)
    bridge = build_budget_bridge(combined)
except Exception as exc:
    st.error(f"Could not simulate budget plan: {exc}")
    st.stop()

current = summary.loc[summary["Plan"] == "Current Mix"].iloc[0]
recommended = summary.loc[summary["Plan"] == "Recommended Mix"].iloc[0]
revenue_delta = float(recommended.Projected_Revenue - current.Projected_Revenue)
contribution_delta = float(recommended.Contribution - current.Contribution)
cac_delta = float(recommended.CAC - current.CAC)
customer_delta = float(recommended.Projected_Customers - current.Projected_Customers)

hero = st.columns(5)
hero[0].metric("Budget", format_money(float(recommended.Spend)), delta=format_money(float(recommended.Spend - current.Spend)))
hero[1].metric("Revenue Impact", format_money(revenue_delta))
hero[2].metric("Contribution Impact", format_money(contribution_delta))
hero[3].metric("Customer Impact", f"{customer_delta:,.0f}")
hero[4].metric("CAC Change", format_money(cac_delta))

st.divider()

overview_tab, allocation_tab, economics_tab, memo_tab, data_tab = st.tabs(
    ["Scenario Overview", "Allocation Plan", "Channel Economics", "Memo", "Data"]
)

with overview_tab:
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Current vs Recommended Mix")
        st.bar_chart(summary.set_index("Plan")[["Projected_Revenue", "Contribution"]], width="stretch")
    with right:
        st.subheader("Portfolio Efficiency")
        efficiency = summary[["Plan", "CAC", "ROAS", "Contribution_ROI"]].copy()
        efficiency = format_money_columns(efficiency, ["CAC"])
        efficiency = format_number_columns(efficiency, ["ROAS"], "x")
        efficiency = format_percent_columns(efficiency, ["Contribution_ROI"])
        st.dataframe(efficiency, width="stretch", hide_index=True)

    st.subheader("Revenue and Contribution Change by Channel")
    st.bar_chart(bridge.set_index("Channel")[["Revenue_Change", "Contribution_Change"]], width="stretch")

with allocation_tab:
    st.subheader("Recommended Budget Moves")
    allocation = bridge[
        [
            "Channel",
            "Spend_Current_Mix",
            "Spend_Recommended_Mix",
            "Spend_Change",
            "Revenue_Change",
            "Contribution_Change",
            "Customer_Change",
        ]
    ].copy()
    allocation = format_money_columns(
        allocation,
        ["Spend_Current_Mix", "Spend_Recommended_Mix", "Spend_Change", "Revenue_Change", "Contribution_Change"],
    )
    allocation = format_number_columns(allocation, ["Customer_Change"])
    st.dataframe(allocation, width="stretch", hide_index=True)
    st.bar_chart(bridge.set_index("Channel")[["Spend_Current_Mix", "Spend_Recommended_Mix"]], width="stretch")

with economics_tab:
    st.subheader("Recommended Channel Economics")
    recommended_detail = combined.loc[combined["Plan"] == "Recommended Mix"][
        [
            "Channel",
            "Funnel_Stage",
            "Spend",
            "Projected_Customers",
            "Projected_Revenue",
            "Contribution",
            "CAC",
            "ROAS",
            "Contribution_ROI",
            "LTV_CAC",
            "Payback_Months",
            "Action",
        ]
    ].copy()
    recommended_detail = format_money_columns(recommended_detail, ["Spend", "Projected_Revenue", "Contribution", "CAC"])
    recommended_detail = format_number_columns(recommended_detail, ["Projected_Customers"])
    recommended_detail = format_number_columns(recommended_detail, ["ROAS", "LTV_CAC"], "x")
    recommended_detail = format_number_columns(recommended_detail, ["Payback_Months"], " mo")
    recommended_detail = format_percent_columns(recommended_detail, ["Contribution_ROI"])
    st.dataframe(recommended_detail, width="stretch", hide_index=True)

with memo_tab:
    st.subheader("Budget Allocation Memo")
    memo = build_scenario_memo(summary, bridge)
    st.markdown(memo)
    st.download_button("Download memo", memo, "marketing_budget_allocation_memo.md", "text/markdown")

with data_tab:
    st.subheader("Source Channel Assumptions")
    st.dataframe(scenario_channels, width="stretch", hide_index=True)
    st.subheader("Methodology")
    st.write("Projected customers use a diminishing-return response curve: customers scale with spend raised to each channel's elasticity.")
    st.write("Allocation scores combine contribution ROI, CAC efficiency, payback speed, retention quality, and strategic priority, then apply a risk penalty.")
    st.write("Recommended spend is constrained by each channel's minimum and maximum spend limits.")
    st.write("The simulator supports planning and trade-off discussion. It does not replace incrementality testing, attribution analysis, or media-mix modeling.")
