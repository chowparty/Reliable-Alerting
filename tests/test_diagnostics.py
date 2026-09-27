import unittest
from reliable_alerting import diagnostics_features

class DiagnosticsTest(unittest.TestCase):
    def test_rolling_median(self):
        f = diagnostics_features.RollingMedianFeature(3)
        self.assertEqual(f.update(1.0), 1.0)
        self.assertEqual(f.update(3.0), 2.0)
        self.assertEqual(f.update(2.0), 2.0)
        self.assertEqual(f.update(5.0), 3.0) 

    def test_rolling_spread(self):
        f = diagnostics_features.RollingSpreadFeature(3)
        self.assertEqual(f.update(2.0), 0.0)
        spread = f.update(4.0)
        self.assertAlmostEqual(spread, 1.41421356, places=5)
        spread = f.update(6.0) # [2, 4, 6] -> mean 4, var 4 => std 2
        self.assertAlmostEqual(spread, 2.0, places=5)
        spread = f.update(6.0) # [4, 6, 6] -> mean 5.333, var = (1.33^2 + 0.67^2 + 0.67^2)/2 = 1.333 -> std=1.1547
        self.assertAlmostEqual(spread, 1.1547005, places=5)

    def test_validation(self):
        with self.assertRaises(ValueError):
            diagnostics_features.RollingSpreadFeature(0)
        with self.assertRaises(ValueError):
            diagnostics_features.RollingMedianFeature(-1)

if __name__ == "__main__":
    unittest.main()
