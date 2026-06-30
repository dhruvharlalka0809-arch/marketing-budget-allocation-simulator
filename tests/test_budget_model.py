import unittest

import pandas as pd

from src.budget_model import (
    AllocationWeights,
    allocate_budget,
    build_budget_bridge,
    build_opportunity_scores,
    build_plan_summary,
    build_scenario_memo,
    load_channel_data,
    normalize_weights,
    project_plan,
    simulate_budget_plan,
)


class BudgetModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.channels = load_channel_data("data/channel_assumptions.csv")
        cls.total_budget = float(cls.channels["Current_Spend"].sum())
        cls.combined, cls.summary = simulate_budget_plan(cls.channels, cls.total_budget)

    def test_budget_is_preserved(self):
        recommended = self.summary.loc[self.summary["Plan"] == "Recommended Mix"].iloc[0]
        self.assertAlmostEqual(float(recommended.Spend), self.total_budget)

    def test_recommended_spend_respects_bounds(self):
        recommended = self.combined.loc[self.combined["Plan"] == "Recommended Mix"].set_index("Channel")
        source = self.channels.set_index("Channel")
        self.assertTrue((recommended["Spend"] >= source["Min_Spend"]).all())
        self.assertTrue((recommended["Spend"] <= source["Max_Spend"]).all())

    def test_projection_outputs_are_non_negative(self):
        for column in ["Projected_Customers", "Projected_Revenue", "Gross_Profit", "CAC", "ROAS"]:
            self.assertTrue((self.combined[column] >= 0).all())

    def test_opportunity_scores_are_positive(self):
        current = project_plan(self.channels, self.channels["Current_Spend"], "Current Mix")
        scores = build_opportunity_scores(current)
        self.assertTrue((scores > 0).all())

    def test_weight_normalization_is_explicit(self):
        weights = normalize_weights(AllocationWeights(contribution=3, cac=2, payback=1, retention=1, strategic_priority=1))
        total = weights.contribution + weights.cac + weights.payback + weights.retention + weights.strategic_priority
        self.assertAlmostEqual(total, 1.0)

    def test_bridge_has_delta_columns(self):
        bridge = build_budget_bridge(self.combined)
        for column in ["Spend_Change", "Revenue_Change", "Contribution_Change", "Customer_Change"]:
            self.assertIn(column, bridge.columns)

    def test_summary_reconciles_to_plan_rows(self):
        summary = build_plan_summary(self.combined)
        for plan in summary["Plan"]:
            plan_rows = self.combined.loc[self.combined["Plan"] == plan]
            summary_row = summary.loc[summary["Plan"] == plan].iloc[0]
            self.assertAlmostEqual(float(summary_row.Spend), float(plan_rows["Spend"].sum()))

    def test_allocator_clamps_to_total_possible_budget(self):
        current = project_plan(self.channels, self.channels["Current_Spend"], "Current Mix")
        scores = build_opportunity_scores(current)
        allocation = allocate_budget(self.channels, 999_999_999, scores)
        self.assertAlmostEqual(float(allocation.sum()), float(self.channels["Max_Spend"].sum()))

    def test_memo_mentions_diminishing_returns(self):
        bridge = build_budget_bridge(self.combined)
        memo = build_scenario_memo(self.summary, bridge)
        self.assertIn("diminishing returns", memo)
        self.assertIn("Marketing Budget Allocation Memo", memo)

    def test_missing_columns_raise_clear_error(self):
        with self.assertRaises(ValueError):
            simulate_budget_plan(pd.DataFrame({"Channel": ["Search"]}), 10000)


if __name__ == "__main__":
    unittest.main()
