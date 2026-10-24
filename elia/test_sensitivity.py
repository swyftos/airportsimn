"""Tests for sensitivity analysis and capacity stress tests."""
import unittest
from pathlib import Path

import pandas as pd

import parking_optimizer as po
import sensitivity

HERE = Path(__file__).parent


class TestSensitivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demand = po.load_demand()
        cls.a = po.load_assumptions()
        cls.a["mc_runs"] = 2000
        cls.tornado_df = sensitivity.run_tornado(cls.demand, cls.a, mc_runs=2000)
        cls.stress_df, cls.thresholds = sensitivity.run_capacity_stress(cls.demand, cls.a, mc_runs=2000)

    def test_base_row_equals_po_run_medium_peak(self):
        """Test that base row peak_p50_base equals po.run() Medium peak with the same mc_runs."""
        _, recs = po.run(self.demand, self.a, variant="standard")
        expected_medium_peak = recs["Medium"]["summary"]["peak_parking_demand_su_p50"]

        for _, row in self.tornado_df.iterrows():
            self.assertEqual(
                row["peak_p50_base"],
                expected_medium_peak,
                f"Parameter {row['parameter']} base peak {row['peak_p50_base']} != {expected_medium_peak}",
            )

    def test_peak_increases_with_demand_scale(self):
        """Test that parking demand peak increases monotonically with demand_scale."""
        scale_rows = self.tornado_df[self.tornado_df["parameter"] == "demand_scale"]
        self.assertEqual(len(scale_rows), 1, "demand_scale row not found in tornado results")
        row = scale_rows.iloc[0]

        self.assertLess(row["peak_p50_low"], row["peak_p50_base"])
        self.assertLess(row["peak_p50_base"], row["peak_p50_high"])
        self.assertLess(row["peak_p90_low"], row["peak_p90_high"])

    def test_capacity_stress_unaccommodated_mean_non_increasing(self):
        """Test that in capacity_stress, no_preparation unaccommodated mean is non-increasing as capacity grows."""
        variants = ["standard", "departure_delay_24h"]
        scenarios = ["Low", "Medium", "High"]

        for var in variants:
            for scen in scenarios:
                sub = self.stress_df[
                    (self.stress_df["variant"] == var) & (self.stress_df["scenario"] == scen)
                ].sort_values(by="ramp_capacity_su")

                means = sub["no_preparation_unaccommodated_mean"].tolist()
                capacities = sub["ramp_capacity_su"].tolist()

                for i in range(len(means) - 1):
                    self.assertGreaterEqual(
                        means[i],
                        means[i + 1],
                        f"Unaccommodated mean increased for {var} {scen} from capacity {capacities[i]} ({means[i]}) to {capacities[i+1]} ({means[i+1]})",
                    )

    def test_every_action_requires_human_approval(self):
        """Test that every action in every row/scenario requires human approval."""
        capacities = [10, 15, 20, 25, 30, 40, 50, 75]
        variants = ["standard", "departure_delay_24h"]
        scenarios = ["Low", "Medium", "High"]

        action_count = 0
        for cap in capacities:
            a = self.a.copy()
            a["ramp_capacity_su"] = float(cap)
            for var in variants:
                _, recs = po.run(self.demand, a, variant=var)
                for scen in scenarios:
                    actions = recs[scen]["actions"]
                    for action in actions:
                        action_count += 1
                        self.assertTrue(
                            action.get("requires_human_approval"),
                            f"Action {action.get('id')} at capacity {cap} {var} {scen} missing requires_human_approval=True",
                        )
                        self.assertTrue(
                            bool(action.get("approver")),
                            f"Action {action.get('id')} at capacity {cap} {var} {scen} missing approver role",
                        )

        self.assertGreater(action_count, 0, "No actions were checked")

    def test_tornado_csv_schema_and_sorting(self):
        """Test tornado CSV columns, sorting by swing_p50 descending, and swing consistency."""
        tornado_path = HERE / "sensitivity_tornado.csv"
        self.assertTrue(tornado_path.exists(), "sensitivity_tornado.csv does not exist")
        df = pd.read_csv(tornado_path)

        expected_columns = [
            "parameter", "low_value", "base_value", "high_value",
            "peak_p50_low", "peak_p50_base", "peak_p50_high",
            "swing_p50", "peak_p90_low", "peak_p90_high", "note",
        ]
        self.assertEqual(list(df.columns), expected_columns)

        swings = df["swing_p50"].tolist()
        self.assertEqual(swings, sorted(swings, reverse=True), "Tornado not sorted by swing_p50 descending")

        for _, row in df.iterrows():
            calc_swing = round(abs(row["peak_p50_high"] - row["peak_p50_low"]), 1)
            self.assertEqual(round(row["swing_p50"], 1), calc_swing)
            self.assertIn("mc_runs=2000", row["note"])

    def test_capacity_stress_csv_schema_and_thresholds(self):
        """Test capacity stress CSV has 48 rows, proper schema, and expected threshold capacities."""
        stress_path = HERE / "capacity_stress.csv"
        self.assertTrue(stress_path.exists(), "capacity_stress.csv does not exist")
        df = pd.read_csv(stress_path)

        self.assertEqual(len(df), 48, f"Expected 48 rows in capacity_stress.csv, got {len(df)}")
        self.assertIn("ramp_capacity_su", df.columns)
        self.assertIn("no_preparation_unaccommodated_mean", df.columns)
        self.assertIn("ai_preparation_unaccommodated_mean", df.columns)

        # Expected thresholds (< 0.5 unaccommodated mean)
        expected_thresholds = {
            ("standard", "Low"): 20,
            ("standard", "Medium"): 20,
            ("standard", "High"): 30,
            ("departure_delay_24h", "Low"): 30,
            ("departure_delay_24h", "Medium"): 30,
            ("departure_delay_24h", "High"): 40,
        }
        for (var, scen), expected_cap in expected_thresholds.items():
            self.assertEqual(
                self.thresholds[(var, scen)],
                expected_cap,
                f"Mismatch for {var} {scen}: expected {expected_cap}, got {self.thresholds[(var, scen)]}",
            )


if __name__ == "__main__":
    unittest.main()
