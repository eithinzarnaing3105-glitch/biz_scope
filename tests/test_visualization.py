import unittest

import pandas as pd

from bizscope.data import interpret_question
from bizscope.visualization import build_chart, get_field_types, suggest_calculations, suggest_charts


class VisualizationTests(unittest.TestCase):
    def setUp(self):
        self.sales = pd.DataFrame(
            {
                "Order_Date": pd.to_datetime(["2025-01-03", "2025-01-20", "2025-02-02", "2025-02-25"]),
                "Brand": ["A", "A", "B", "B"],
                "Price": [10.0, 30.0, 20.0, 40.0],
                "Quantity": [1, 3, 2, 4],
                "Transaction_ID": ["T1", "T2", "T3", "T4"],
            }
        )

    def test_types_exclude_identifier_fields(self):
        numeric, categories, dates = get_field_types(self.sales)
        self.assertIn("Price", numeric)
        self.assertNotIn("Transaction_ID", numeric)
        self.assertIn("Brand", categories)
        self.assertIn("Order_Date", dates)

    def test_bar_chart_uses_requested_average(self):
        result, meta = build_chart(self.sales, "bar", "Brand", "Price", "Average")
        self.assertEqual(result.iloc[0]["Result"], 30.0)
        self.assertEqual(meta["x"], "Brand")

    def test_row_count_chart_does_not_claim_sales(self):
        result, meta = build_chart(self.sales, "bar", "Brand")
        self.assertEqual(dict(zip(result["Brand"], result["Result"])), {"A": 2, "B": 2})
        self.assertIn("records", meta["note"])

    def test_time_chart_groups_to_month(self):
        result, _ = build_chart(self.sales, "line", "Order_Date", "Quantity", "Sum", date_grain="Month")
        self.assertEqual(result["Result"].tolist(), [4, 6])
        self.assertEqual(len(result), 2)

    def test_histogram_and_scatter(self):
        histogram, _ = build_chart(self.sales, "histogram", "Price", bins=5)
        scatter, _ = build_chart(self.sales, "scatter", "Price", "Quantity")
        self.assertEqual(int(histogram["Records"].sum()), 4)
        self.assertEqual(len(scatter), 4)

    def test_missing_measure_values_are_not_reported_as_zero(self):
        data = pd.DataFrame({"Group": ["A", "A", "B"], "Amount": [None, None, 5.0]})
        result, _ = build_chart(data, "bar", "Group", "Amount", "Sum")
        self.assertEqual(result.to_dict(orient="records"), [{"Group": "B", "Result": 5.0}])

    def test_pie_chart_keeps_small_categories_in_other(self):
        data = pd.DataFrame({"Group": list("ABCDEFGHIJ")})
        result, _ = build_chart(data, "pie", "Group")
        self.assertIn("Other categories", result["Group"].tolist())
        self.assertEqual(int(result["Result"].sum()), 10)

    def test_suggestions_are_based_on_columns(self):
        suggestions = suggest_charts(self.sales)
        self.assertTrue(any(item["type"] == "line" for item in suggestions))
        self.assertTrue(any(item["type"] == "bar" for item in suggestions))

    def test_calculation_examples_use_detected_measure_and_category_fields(self):
        ideas = suggest_calculations(self.sales)
        self.assertTrue(any("average" in idea and "by Brand" in idea for idea in ideas))
        self.assertFalse(any("Transaction_ID" in idea for idea in ideas))
        suggestion = next(idea for idea in ideas if "average" in idea and "by Brand" in idea)
        plan = interpret_question(suggestion, self.sales)
        self.assertEqual(plan["metric"], "Quantity")
        self.assertEqual(plan["dimension"], "Brand")
        self.assertEqual(plan["operation"], "Average")

    def test_no_numeric_fields_means_no_calculation_prompts(self):
        data = pd.DataFrame({"Name": ["A", "B"], "Group": ["North", "South"]})
        self.assertEqual(suggest_calculations(data), [])


if __name__ == "__main__":
    unittest.main()
