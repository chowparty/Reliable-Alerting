import unittest
from reliable_alerting import policy

class KConsecutivePolicyTest(unittest.TestCase):
    def test_k_consecutive(self):
        pol = policy.KConsecutivePolicy(10.0, 3)
        self.assertEqual(pol.decide(11.0), "normal") # run=1
        self.assertEqual(pol.decide(11.0), "normal") # run=2
        self.assertEqual(pol.decide(11.0), "alert")  # run=3 (alerts on 3rd)
        self.assertEqual(pol.decide(11.0), "alert")  # run=4
        self.assertEqual(pol.decide(9.0), "normal")  # run=0 (reset)
        self.assertEqual(pol.decide(11.0), "normal") # run=1

    def test_validation(self):
        with self.assertRaises(ValueError):
            policy.KConsecutivePolicy(10.0, 0)
        with self.assertRaises(ValueError):
            policy.KConsecutivePolicy(10.0, -1)

class MOfNPolicyTest(unittest.TestCase):
    def test_m_of_n(self):
        pol = policy.MOfNPolicy(10.0, 2, 3) # 2 of 3
        # [True] -> sum = 1
        self.assertEqual(pol.decide(11.0), "normal")
        # [True, False] -> sum = 1
        self.assertEqual(pol.decide(9.0), "normal")
        # [True, False, True] -> sum = 2 -> alert
        self.assertEqual(pol.decide(11.0), "alert")
        # [False, True, False] -> sum = 1 -> normal
        self.assertEqual(pol.decide(9.0), "normal")
        # [True, False, True] -> sum = 2 -> alert
        self.assertEqual(pol.decide(11.0), "alert")
        # [False, True, True] -> sum = 2 -> alert
        self.assertEqual(pol.decide(11.0), "alert")
        # [True, True, True] -> sum = 3 -> alert
        self.assertEqual(pol.decide(11.0), "alert")
        # [True, True, False] -> sum = 2 -> alert
        self.assertEqual(pol.decide(9.0), "alert")
        # [True, False, False] -> sum = 1 -> normal
        self.assertEqual(pol.decide(9.0), "normal")

    def test_validation(self):
        with self.assertRaises(ValueError):
            policy.MOfNPolicy(10.0, 0, 3)
        with self.assertRaises(ValueError):
            policy.MOfNPolicy(10.0, 4, 3)

if __name__ == "__main__":
    unittest.main()
