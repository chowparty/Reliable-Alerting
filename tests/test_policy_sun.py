"""Tests for SunConfidenceSequencePolicy (frozen protocol section 5).

Re-implementation of Sun et al. (ICML 2024) Algorithm 1 with confidence set
eq. (1). Semantics (binding):

  u_n(alpha) = 0.85 * sqrt((log log(e*n) + 0.8*log(1612/alpha)) / n)
  Qhat(p; y_1..n) = (y_(floor(p*n)) + y_(ceil(p*n))) / 2, 1-indexed order stats,
                    with y_(0) := y_(1)
  C = [ Qhat(max(p-2u,0)), Qhat(min(p+2u,1)) ]
  history = calibration scores UNION replay scores seen so far (admit-all)
  p = 0.95, alpha = 0.05
  decision: S > max(C) -> alert ; S in C -> defer ; else normal

Written before implementation (TDD).
"""
import math
import unittest

from reliable_alerting import policy


def _expected_un(n, alpha=0.05):
    return 0.85 * math.sqrt((math.log(math.log(math.e * n)) + 0.8 * math.log(1612.0 / alpha)) / n)


def _qhat(sorted_vals, p):
    # 1-indexed order stats with y_(0) := y_(1)
    n = len(sorted_vals)
    def order(k):
        if k <= 0:
            k = 1
        if k > n:
            k = n
        return sorted_vals[k - 1]
    lo = math.floor(p * n)
    hi = math.ceil(p * n)
    return (order(lo) + order(hi)) / 2.0


class UnFormula(unittest.TestCase):
    def test_un_spot_values(self):
        pol = policy.SunConfidenceSequencePolicy(p=0.95, alpha=0.05)
        for n in (1, 2, 5, 10, 174, 1000):
            self.assertAlmostEqual(pol.u_n(n), _expected_un(n, 0.05), places=12)


class QhatSemantics(unittest.TestCase):
    def test_qhat_small_lists(self):
        pol = policy.SunConfidenceSequencePolicy()
        vals = [1.0, 2.0, 3.0, 4.0]
        # p=0.5, n=4: floor=2, ceil=2 -> (2+2)/2 = 2.0 (order stats: 1,2,3,4)
        self.assertAlmostEqual(pol.q_hat(vals, 0.5), 2.0)
        # p=0.95, n=4: floor(3.8)=3, ceil=4 -> (3+4)/2 = 3.5
        self.assertAlmostEqual(pol.q_hat(vals, 0.95), 3.5)
        # p very small -> floor 0 -> y_(0):=y_(1) ; ceil 1 -> y_(1) => y1
        self.assertAlmostEqual(pol.q_hat(vals, 0.0), 1.0)

    def test_qhat_matches_reference(self):
        pol = policy.SunConfidenceSequencePolicy()
        vals = [5.0, 1.0, 3.0, 2.0, 4.0]
        s = sorted(vals)
        for p in (0.0, 0.2, 0.5, 0.9, 0.95, 1.0):
            self.assertAlmostEqual(pol.q_hat(vals, p), _qhat(s, p))


class ConfidenceSetAndDecision(unittest.TestCase):
    def test_history_includes_calibration_then_replay(self):
        cal = [0.1, 0.2, 0.3, 0.4]
        pol = policy.SunConfidenceSequencePolicy(calibration_scores=cal)
        # Before any replay, history is the calibration scores.
        self.assertEqual(sorted(pol.history), sorted(cal))
        pol.decide(0.5)
        # After one replay score, history includes it (admit-all).
        self.assertEqual(sorted(pol.history), sorted(cal + [0.5]))
        pol.decide(9.0)
        self.assertEqual(sorted(pol.history), sorted(cal + [0.5, 9.0]))

    def test_decision_mapping(self):
        # Derive the expected label from the eq. (1) reference for each score,
        # rather than assuming one: when the current score becomes the new max
        # and the upper bound clips to Qhat(1.0)=that score, the result is a
        # boundary 'defer', which is correct behaviour.
        cal = [float(i) for i in range(1, 21)]  # 1..20
        for s in (1000.0, -1000.0, 10.0, 19.0, 21.0):
            pol = policy.SunConfidenceSequencePolicy(
                calibration_scores=cal, p=0.95, alpha=0.05)
            hist = sorted(cal + [s])
            n = len(hist)
            u = _expected_un(n, 0.05)
            c_lo = _qhat(hist, max(0.95 - 2 * u, 0.0))
            c_hi = _qhat(hist, min(0.95 + 2 * u, 1.0))
            expected = "alert" if s > c_hi else ("defer" if s >= c_lo else "normal")
            self.assertEqual(pol.decide(s), expected, msg=f"score={s}")

    def test_confidence_bounds_computed_from_eq1(self):
        cal = [float(i) for i in range(1, 51)]  # 1..50
        pol = policy.SunConfidenceSequencePolicy(calibration_scores=cal, p=0.95, alpha=0.05)
        s = 25.0
        # Reproduce eq. (1) independently for the first replay decision.
        hist = sorted(cal + [s])
        n = len(hist)
        u = _expected_un(n, 0.05)
        lo_p = max(0.95 - 2 * u, 0.0)
        hi_p = min(0.95 + 2 * u, 1.0)
        c_lo = _qhat(hist, lo_p)
        c_hi = _qhat(hist, hi_p)
        decision = pol.decide(s)
        if s > c_hi:
            self.assertEqual(decision, "alert")
        elif s >= c_lo:
            self.assertEqual(decision, "defer")
        else:
            self.assertEqual(decision, "normal")

    def test_history_includes_current_score_before_decision(self):
        # Protocol: history = calibration scores UNION replay scores so far,
        # and the current score is part of "so far".
        cal = [1.0, 2.0, 3.0]
        pol = policy.SunConfidenceSequencePolicy(calibration_scores=cal)
        pol.decide(4.0)
        self.assertIn(4.0, pol.history)


class Docstring(unittest.TestCase):
    def test_docstring_names_reimplementation(self):
        doc = policy.SunConfidenceSequencePolicy.__doc__ or ""
        self.assertIn("Sun et al.", doc)
        self.assertIn("ICML 2024", doc)
        self.assertIn("Algorithm 1", doc)
        self.assertIn("eq. (1)", doc)
        self.assertIn("not the authors", doc)


if __name__ == "__main__":
    unittest.main()
