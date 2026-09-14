"""Unit tests for congestion forecasting and fractional queue policies (PRD 11.3 & 15.2)."""

import unittest
from src.models.congestion_model import (
    predict_congestion, CongestionLevel, classify_queue_fraction, _format_queue_display
)
from src.data.generator import generate_scenario


class TestCongestionModel(unittest.TestCase):

    def test_classify_levels(self):
        self.assertEqual(classify_queue_fraction(0.1), CongestionLevel.LOW)
        self.assertEqual(classify_queue_fraction(0.4), CongestionLevel.MEDIUM)
        self.assertEqual(classify_queue_fraction(0.7), CongestionLevel.HIGH)
        self.assertEqual(classify_queue_fraction(0.9), CongestionLevel.CRITICAL)

    def test_fractional_queue_policy_display(self):
        # Fractional values must not be presented as literal physical vessel counts
        display_sub_one = _format_queue_display(0.54)
        self.assertIn("less than one vessel expected", display_sub_one)
        self.assertIn("0.54", display_sub_one)

        display_multi = _format_queue_display(2.35)
        self.assertIn("~2.4 vessels expected", display_multi)

    def test_predict_congestion_structure(self):
        scenario = generate_scenario("normal", 20)
        forecasts = predict_congestion(
            scenario["vessels"], scenario["berths"], scenario["cranes"], 72.0
        )
        self.assertTrue(len(forecasts) > 0)
        for f in forecasts:
            self.assertIn(f.congestion_level, list(CongestionLevel))
            self.assertGreaterEqual(f.confidence, 0.0)
            self.assertLessEqual(f.confidence, 1.0)
            self.assertTrue(len(f.contributing_factors) > 0)


if __name__ == "__main__":
    unittest.main()
