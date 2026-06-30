from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


REQUIRED_COLUMNS = {
    "Channel",
    "Funnel_Stage",
    "Current_Spend",
    "Min_Spend",
    "Max_Spend",
    "Base_Customers",
    "ARPU",
    "Gross_Margin",
    "Elasticity",
    "Retention_Rate",
    "Strategic_Priority",
    "Risk_Adjustment",
}


@dataclass(frozen=True)
class AllocationWeights:
    contribution: float = 0.35
    cac: float = 0.25
    payback: float = 0.20
    retention: float = 0.10
    strategic_priority: float = 0.10


def load_channel_data(path: str) -> pd.DataFrame:
    return normalize_channel_data(pd.read_csv(path))


def normalize_channel_data(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    output = df.copy()
    numeric_columns = REQUIRED_COLUMNS.difference({"Channel", "Funnel_Stage"})
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output = output.dropna(subset=["Channel", "Current_Spend", "Base_Customers", "ARPU"])
    output["Min_Spend"] = output["Min_Spend"].clip(lower=0.0)
    output["Max_Spend"] = output[["Max_Spend", "Min_Spend"]].max(axis=1)
    output["Current_Spend"] = output["Current_Spend"].clip(lower=output["Min_Spend"], upper=output["Max_Spend"])
    output["Gross_Margin"] = output["Gross_Margin"].clip(lower=0.0, upper=1.0)
    output["Elasticity"] = output["Elasticity"].clip(lower=0.05, upper=1.0)
    output["Retention_Rate"] = output["Retention_Rate"].clip(lower=0.0, upper=0.99)
    output["Strategic_Priority"] = output["Strategic_Priority"].clip(lower=1.0, upper=10.0)
    output["Risk_Adjustment"] = output["Risk_Adjustment"].clip(lower=0.0, upper=0.60)
    return output.reset_index(drop=True)


def simulate_budget_plan(
    df: pd.DataFrame,
    total_budget: float,
    weights: AllocationWeights = AllocationWeights(),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    channels = normalize_channel_data(df)
    current_plan = project_plan(channels, channels["Current_Spend"], "Current Mix")
    opportunity_scores = build_opportunity_scores(current_plan, weights)
    recommended_spend = allocate_budget(channels, float(total_budget), opportunity_scores)
    recommended_plan = project_plan(channels, recommended_spend, "Recommended Mix")
    combined = pd.concat([current_plan, recommended_plan], ignore_index=True)
    summary = build_plan_summary(combined)
    return combined, summary


def project_plan(channels: pd.DataFrame, spend: pd.Series, plan_name: str) -> pd.DataFrame:
    output = channels.copy()
    output["Plan"] = plan_name
    output["Spend"] = spend.astype(float).clip(lower=output["Min_Spend"], upper=output["Max_Spend"])
    spend_ratio = safe_divide(output["Spend"], output["Current_Spend"])
    output["Projected_Customers"] = output["Base_Customers"] * spend_ratio.pow(output["Elasticity"])
    output["Projected_Customers"] = output["Projected_Customers"] * (1 - output["Risk_Adjustment"])
    output["Projected_Revenue"] = output["Projected_Customers"] * output["ARPU"]
    output["Gross_Profit"] = output["Projected_Revenue"] * output["Gross_Margin"]
    output["Contribution"] = output["Gross_Profit"] - output["Spend"]
    output["CAC"] = safe_divide(output["Spend"], output["Projected_Customers"])
    output["ROAS"] = safe_divide(output["Projected_Revenue"], output["Spend"])
    output["Contribution_ROI"] = safe_divide(output["Contribution"], output["Spend"])
    output["Monthly_GP_Per_Customer"] = safe_divide(output["Gross_Profit"], output["Projected_Customers"])
    output["Expected_Lifetime_Months"] = 1 / (1 - output["Retention_Rate"])
    output["LTV"] = output["Monthly_GP_Per_Customer"] * output["Expected_Lifetime_Months"]
    output["LTV_CAC"] = safe_divide(output["LTV"], output["CAC"])
    output["Payback_Months"] = safe_divide(output["CAC"], output["Monthly_GP_Per_Customer"])
    output["Spend_Change"] = output["Spend"] - output["Current_Spend"]
    output["Action"] = output.apply(classify_action, axis=1)
    return output


def build_opportunity_scores(plan: pd.DataFrame, weights: AllocationWeights = AllocationWeights()) -> pd.Series:
    total_weight = (
        weights.contribution
        + weights.cac
        + weights.payback
        + weights.retention
        + weights.strategic_priority
    ) or 1.0
    normalized = AllocationWeights(
        contribution=weights.contribution / total_weight,
        cac=weights.cac / total_weight,
        payback=weights.payback / total_weight,
        retention=weights.retention / total_weight,
        strategic_priority=weights.strategic_priority / total_weight,
    )
    scores = (
        score_positive(plan["Contribution_ROI"], -0.25, 1.25) * normalized.contribution
        + score_negative(plan["CAC"], 200.0, 1800.0) * normalized.cac
        + score_negative(plan["Payback_Months"], 1.0, 12.0) * normalized.payback
        + score_positive(plan["Retention_Rate"], 0.55, 0.92) * normalized.retention
        + score_positive(plan["Strategic_Priority"], 1.0, 10.0) * normalized.strategic_priority
    )
    risk_penalty = 1 - plan["Risk_Adjustment"].clip(lower=0, upper=0.60)
    return (scores * risk_penalty).clip(lower=1.0)


def allocate_budget(channels: pd.DataFrame, total_budget: float, opportunity_scores: pd.Series) -> pd.Series:
    total_budget = max(float(total_budget), float(channels["Min_Spend"].sum()))
    total_budget = min(total_budget, float(channels["Max_Spend"].sum()))
    remaining_budget = total_budget
    allocation = pd.Series(0.0, index=channels.index)
    flexible = pd.Series(True, index=channels.index)
    min_spend = channels["Min_Spend"].astype(float)
    max_spend = channels["Max_Spend"].astype(float)
    scores = opportunity_scores.astype(float).clip(lower=1.0)

    for _ in range(len(channels) + 1):
        active_scores = scores.where(flexible, 0.0)
        if float(active_scores.sum()) == 0:
            break
        proposed = remaining_budget * active_scores / active_scores.sum()
        low = proposed < min_spend
        high = proposed > max_spend
        newly_fixed = flexible & (low | high)
        if not bool(newly_fixed.any()):
            allocation = allocation.where(~flexible, proposed)
            break
        allocation = allocation.where(~newly_fixed, proposed.clip(lower=min_spend, upper=max_spend))
        remaining_budget = total_budget - float(allocation.where(~flexible | newly_fixed, 0.0).sum())
        flexible = flexible & ~newly_fixed

    if bool(flexible.any()) and float(allocation[flexible].sum()) == 0:
        active_scores = scores.where(flexible, 0.0)
        allocation = allocation.where(~flexible, remaining_budget * active_scores / active_scores.sum())

    return allocation.clip(lower=min_spend, upper=max_spend)


def build_plan_summary(combined: pd.DataFrame) -> pd.DataFrame:
    summary = combined.groupby("Plan", as_index=False).agg(
        Spend=("Spend", "sum"),
        Projected_Customers=("Projected_Customers", "sum"),
        Projected_Revenue=("Projected_Revenue", "sum"),
        Gross_Profit=("Gross_Profit", "sum"),
        Contribution=("Contribution", "sum"),
    )
    summary["CAC"] = safe_divide(summary["Spend"], summary["Projected_Customers"])
    summary["ROAS"] = safe_divide(summary["Projected_Revenue"], summary["Spend"])
    summary["Contribution_ROI"] = safe_divide(summary["Contribution"], summary["Spend"])
    return summary


def build_budget_bridge(combined: pd.DataFrame) -> pd.DataFrame:
    pivot = combined.pivot_table(
        index="Channel",
        columns="Plan",
        values=["Spend", "Projected_Customers", "Projected_Revenue", "Contribution", "CAC"],
        aggfunc="sum",
    )
    pivot.columns = [f"{metric}_{plan}".replace(" ", "_") for metric, plan in pivot.columns]
    output = pivot.reset_index()
    output["Spend_Change"] = output["Spend_Recommended_Mix"] - output["Spend_Current_Mix"]
    output["Revenue_Change"] = output["Projected_Revenue_Recommended_Mix"] - output["Projected_Revenue_Current_Mix"]
    output["Contribution_Change"] = output["Contribution_Recommended_Mix"] - output["Contribution_Current_Mix"]
    output["Customer_Change"] = output["Projected_Customers_Recommended_Mix"] - output["Projected_Customers_Current_Mix"]
    return output.sort_values("Contribution_Change", ascending=False).reset_index(drop=True)


def build_scenario_memo(combined: pd.DataFrame, summary: pd.DataFrame) -> str:
    current = summary.loc[summary["Plan"] == "Current Mix"].iloc[0]
    recommended = summary.loc[summary["Plan"] == "Recommended Mix"].iloc[0]
    bridge = build_budget_bridge(combined)
    top_increase = bridge.sort_values("Spend_Change", ascending=False).iloc[0]
    top_reduce = bridge.sort_values("Spend_Change", ascending=True).iloc[0]
    revenue_uplift = float(recommended.Projected_Revenue - current.Projected_Revenue)
    contribution_uplift = float(recommended.Contribution - current.Contribution)
    customer_uplift = float(recommended.Projected_Customers - current.Projected_Customers)

    return f"""### Marketing Budget Allocation Memo

**Planning readout:** The recommended mix reallocates {format_money(float(recommended.Spend))} of spend and is projected to generate {format_money(float(recommended.Projected_Revenue))} of revenue, {format_money(float(recommended.Contribution))} of contribution, and {float(recommended.Projected_Customers):,.0f} customers.

**Impact vs current mix:** Revenue changes by {format_money(revenue_uplift)}, contribution changes by {format_money(contribution_uplift)}, and customers change by {customer_uplift:,.0f}.

**Scale up:** {top_increase.Channel} receives the largest budget increase because its modeled economics show stronger contribution, CAC efficiency, payback, retention, or strategic priority.

**Reduce:** {top_reduce.Channel} receives the largest reduction because the next dollar is less attractive after risk, saturation, and payback are considered.

**Decision note:** The simulator assumes diminishing returns by channel. It is useful for budget planning and trade-off analysis, not as a replacement for incrementality testing or media-mix modeling.
"""


def classify_action(row: pd.Series) -> str:
    threshold = max(float(row["Current_Spend"]) * 0.05, 1.0)
    change = float(row["Spend_Change"])
    if change > threshold:
        return "Increase"
    if change < -threshold:
        return "Reduce"
    return "Hold"


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator / denominator.replace(0, pd.NA)
    return result.fillna(0.0).replace([float("inf"), float("-inf")], 0.0)


def score_positive(series: pd.Series, floor: float, ceiling: float) -> pd.Series:
    return ((series - floor) / (ceiling - floor) * 100).clip(lower=0, upper=100)


def score_negative(series: pd.Series, floor: float, ceiling: float) -> pd.Series:
    return (100 - ((series - floor) / (ceiling - floor) * 100)).clip(lower=0, upper=100)


def format_money(value: float) -> str:
    return f"${value:,.0f}"
