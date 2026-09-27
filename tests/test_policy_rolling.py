import unittest
from reliable_alerting import policy

class RollingThresholdPolicyTest(unittest.TestCase):
    def test_initialization(self):
        pol = policy.RollingThresholdPolicy(10.0, 5, 0.5, "normal_only")
        self.assertEqual(pol.threshold, 10.0)

    def test_validation(self):
        with self.assertRaises(ValueError):
            policy.RollingThresholdPolicy(10.0, -1, 0.5)
        with self.assertRaises(ValueError):
            policy.RollingThresholdPolicy(10.0, 5, 1.5)
        with self.assertRaises(ValueError):
            policy.RollingThresholdPolicy(10.0, 5, 0.5, "invalid_rule")

    def test_normal_only_admission(self):
        pol = policy.RollingThresholdPolicy(10.0, 5, 0.5, "normal_only")
        # 11.0 is an alert (since > 10.0)
        self.assertEqual(pol.decide(11.0), "alert")
        # Threshold should be unchanged because it wasn't admitted
        self.assertEqual(pol.threshold, 10.0)

        # 9.0 is normal, should be admitted
        self.assertEqual(pol.decide(9.0), "normal")
        # Now threshold recomputes: history is [9.0], 50th percentile of 1 element is 9.0
        self.assertEqual(pol.threshold, 9.0)

    def test_all_admission(self):
        pol = policy.RollingThresholdPolicy(10.0, 3, 1.0, "all") # max quantile
        # Admits alert score
        self.assertEqual(pol.decide(15.0), "alert")
        self.assertEqual(pol.threshold, 15.0)

    def test_rolling_window(self):
        pol = policy.RollingThresholdPolicy(10.0, 3, 1.0, "normal_only")
        # 9.0 is normal -> threshold = 9.0
        pol.decide(9.0)
        self.assertEqual(pol.threshold, 9.0)
        # 8.0 is normal -> threshold = max(9.0, 8.0) = 9.0
        pol.decide(8.0)
        self.assertEqual(pol.threshold, 9.0)
        # 8.5 is normal -> threshold = max(9.0, 8.0, 8.5) = 9.0
        pol.decide(8.5)
        self.assertEqual(pol.threshold, 9.0)
        
        # Now history is [9.0, 8.0, 8.5].
        # 11.0 is alert (not admitted)
        self.assertEqual(pol.decide(11.0), "alert")
        self.assertEqual(pol.threshold, 9.0)
        
        # 7.0 is normal. Replaces 9.0. History is [8.0, 8.5, 7.0]. Max is 8.5!
        self.assertEqual(pol.decide(7.0), "normal")
        self.assertEqual(pol.threshold, 8.5)
        
        # 6.0 is normal. Replaces 8.0. History is [8.5, 7.0, 6.0]. Max is 8.5!
        self.assertEqual(pol.decide(6.0), "normal")
        self.assertEqual(pol.threshold, 8.5)
        
        # 5.0 is normal. Replaces 8.5. History is [7.0, 6.0, 5.0]. Max is 7.0!
        self.assertEqual(pol.decide(5.0), "normal")
        self.assertEqual(pol.threshold, 7.0)

if __name__ == "__main__":
    unittest.main()
