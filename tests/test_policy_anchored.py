"""Tests for AnchoredRecalibrationPolicy (frozen protocol section 4).

The pseudocode in section 4 is binding. These tests pin every branch with
hand-computed small sequences, the state invariants, and determinism. Written
before the implementation (TDD).

Buffer R holds the last L scores of EVERY window (admission does not depend on
any decision). quantile(R) is nearest rank (ceil(q*|R|)-th smallest); median is
the ordinary median. full = (|R| == L); elevated = full and median(R) > theta.
Output state per window is 'alert', 'normal' (hold) or 'defer'.
last_action is in {hold, alert, defer, recalibrate}.
"""
import math
import unittest

from reliable_alerting import policy


class ConstructionAndInvariants(unittest.TestCase):
    def test_defaults(self):
        pol = policy.AnchoredRecalibrationPolicy(theta0=1.0)
        self.assertEqual(pol.threshold, 1.0)
        self.assertEqual(pol.mode, "normal")

    def test_validation(self):
        with self.assertRaises((ValueError, TypeError)):
            policy.AnchoredRecalibrationPolicy(theta0=1.0, block_length=0)
        with self.assertRaises((ValueError, TypeError)):
            policy.AnchoredRecalibrationPolicy(theta0=1.0, quantile=0.0)
        with self.assertRaises((ValueError, TypeError)):
            policy.AnchoredRecalibrationPolicy(theta0=1.0, quantile=1.5)
        with self.assertRaises((ValueError, TypeError)):
            policy.AnchoredRecalibrationPolicy(theta0=1.0, defer_limit=-1)
        # theta0 must be finite and positive-ish (a threshold)
        with self.assertRaises((ValueError, TypeError)):
            policy.AnchoredRecalibrationPolicy(theta0=float("inf"))
        # kappa/rho accept math.inf (ablations); D accepts 0.
        policy.AnchoredRecalibrationPolicy(theta0=1.0, cap=math.inf)
        policy.AnchoredRecalibrationPolicy(theta0=1.0, stability=math.inf)
        policy.AnchoredRecalibrationPolicy(theta0=1.0, defer_limit=0)

    def test_no_recalibration_before_buffer_full(self):
        # With L=10, the first 9 windows cannot recalibrate; threshold stays theta0.
        pol = policy.AnchoredRecalibrationPolicy(theta0=2.0, block_length=10)
        for _ in range(9):
            pol.decide(5.0)  # all above theta0, but buffer not full yet
            self.assertEqual(pol.threshold, 2.0)
            self.assertNotEqual(pol.last_action, "recalibrate")

    def test_theta_bounds_invariant_random(self):
        import random
        rng = random.Random(2026)
        for _ in range(200):
            theta0 = rng.uniform(0.5, 3.0)
            L = rng.choice([2, 3, 5, 10])
            q = rng.choice([0.5, 0.9, 0.95, 1.0])
            kappa = rng.choice([2.0, 4.0, 8.0])
            rho = rng.choice([1.5, 2.0, 4.0])
            D = rng.choice([0, 3, 10])
            pol = policy.AnchoredRecalibrationPolicy(
                theta0=theta0, block_length=L, quantile=q,
                cap=kappa, stability=rho, defer_limit=D)
            for _ in range(rng.randint(1, 80)):
                pol.decide(rng.uniform(0.0, 6.0 * theta0))
                self.assertGreaterEqual(pol.threshold, theta0 - 1e-9)
                self.assertLessEqual(pol.threshold, kappa * theta0 + 1e-9)


class RecalibrateUpOnStableElevation(unittest.TestCase):
    def test_stable_elevation_recalibrates_up(self):
        # L=4, q=1.0 (quantile = max of buffer), kappa=4, rho=2, D=10, theta0=1.
        # Feed four scores at 2.0: buffer=[2,2,2,2], median=2>theta(1) => elevated,
        # stable (max 2 <= rho*median = 4), cand = quantile = 2 <= kappa*theta0=4.
        # => recalibrate up to max(theta0, cand) = 2.0; mode normal.
        pol = policy.AnchoredRecalibrationPolicy(
            theta0=1.0, block_length=4, quantile=1.0, cap=4.0, stability=2.0,
            defer_limit=10)
        states = [pol.decide(2.0) for _ in range(4)]
        # First three windows: buffer not full (1..3), stays at theta0=1, 2>1 => alert.
        self.assertEqual(states[:3], ["alert", "alert", "alert"])
        # Fourth: buffer full, elevated, stable, recalibrate up to 2.0.
        self.assertEqual(pol.last_action, "recalibrate")
        self.assertAlmostEqual(pol.threshold, 2.0)
        self.assertEqual(pol.mode, "normal")
        # s=2.0 > new theta 2.0? strict greater -> False => 'normal'.
        self.assertEqual(states[3], "normal")


class UnstableElevationDefersThenAlertCapable(unittest.TestCase):
    def test_unstable_elevation_defers_up_to_D_then_escalates(self):
        # L=2, q=1.0, theta0=1, kappa=4, rho=2, D=3.
        # Alternate 1.0 and 5.0 so the block is always [1,5] or [5,1]:
        # median = 3 > theta => elevated; max 5 > rho*median (2*3=6)? no, 5<=6 stable.
        # Make it unstable: use [1, 5] with rho=1 -> stability = max<=rho*median.
        # Simpler: theta0=1, block [2, 10]: median 6>1 elevated; max 10 > 2*6=12? no.
        # Force unstable with big spread: block [1, 100], median 50.5, max 100 > 2*50.5=101? no.
        # Unstable requires max > rho*median. Use [1, 9], median 5, rho=1.5 => 1.5*5=7.5, max 9>7.5 unstable.
        pol = policy.AnchoredRecalibrationPolicy(
            theta0=1.0, block_length=2, quantile=1.0, cap=4.0, stability=1.5,
            defer_limit=3)
        # Warm buffer to full with one window (not full at 1).
        pol.decide(1.0)   # buffer [1], not full
        # Now feed windows keeping block = [1, 9] pattern => median 5 > theta.
        # window: score 9 -> buffer [1,9] median 5 elevated; max 9 > 1.5*5=7.5 unstable
        # guard fails, c<D so defer, mode suspect.
        s1 = pol.decide(9.0)
        self.assertEqual(s1, "defer")
        self.assertEqual(pol.last_action, "defer")
        self.assertEqual(pol.mode, "suspect")
        # keep it elevated + unstable: buffer becomes [9,1]? feed 1 -> [9,1] median5 max9 unstable
        s2 = pol.decide(1.0)
        # buffer [9,1] median 5 > theta 1 elevated, unstable, c=1<3 defer
        self.assertEqual(s2, "defer")
        s3 = pol.decide(9.0)  # [1,9] c=2<3 defer
        self.assertEqual(s3, "defer")
        s4 = pol.decide(1.0)  # [9,1] c=3, c<D(3)? no -> escalate; mode escalated
        self.assertEqual(pol.mode, "escalated")
        # In escalation the decision is alert if s>theta else hold.
        self.assertIn(s4, ("alert", "normal"))


class DeferLimitZeroEscalatesImmediately(unittest.TestCase):
    def test_D_zero_escalates_at_once(self):
        # D=0: on unstable/guarded elevation, no defer; escalate immediately.
        pol = policy.AnchoredRecalibrationPolicy(
            theta0=1.0, block_length=2, quantile=1.0, cap=4.0, stability=1.5,
            defer_limit=0)
        pol.decide(1.0)          # buffer [1] not full
        s = pol.decide(9.0)      # [1,9] elevated, unstable, c<D(0)? no -> escalate
        self.assertEqual(pol.mode, "escalated")
        self.assertNotEqual(s, "defer")


class BeyondCapDefersThenEscalates(unittest.TestCase):
    def test_beyond_cap_elevation_defers_then_escalates(self):
        # Stable but beyond cap: cand > kappa*theta0 so recalibration is refused,
        # then defer up to D, then escalate.
        # theta0=1, kappa=2 (cap=2), rho=4 (very tolerant so stable), L=2, q=1.0, D=2.
        # block [5,5]: median 5>1 elevated; max 5 <= 4*5 stable; cand=5 > 2*1=2 beyond cap.
        pol = policy.AnchoredRecalibrationPolicy(
            theta0=1.0, block_length=2, quantile=1.0, cap=2.0, stability=4.0,
            defer_limit=2)
        pol.decide(5.0)          # [5] not full
        s1 = pol.decide(5.0)     # [5,5] elevated stable but cand 5>cap 2 => defer c=1
        self.assertEqual(s1, "defer")
        s2 = pol.decide(5.0)     # [5,5] c=1<2 defer c=2
        self.assertEqual(s2, "defer")
        s3 = pol.decide(5.0)     # c=2<2? no -> escalate
        self.assertEqual(pol.mode, "escalated")
        self.assertIn(s3, ("alert", "normal"))


class ReturnTowardAnchorWhenElevationEnds(unittest.TestCase):
    def test_returns_toward_theta0_after_elevation(self):
        # First recalibrate up (stable elevation), then feed low scores so the
        # block median drops below theta; the return branch lowers theta toward
        # theta0 (max(theta0, quantile(R))).
        pol = policy.AnchoredRecalibrationPolicy(
            theta0=1.0, block_length=2, quantile=1.0, cap=4.0, stability=2.0,
            defer_limit=10)
        pol.decide(3.0)          # [3] not full
        pol.decide(3.0)          # [3,3] elevated stable cand3<=4 => recalibrate up to 3
        self.assertAlmostEqual(pol.threshold, 3.0)
        # Now low scores: block [3,0.5] median 1.75 > theta 3? no, not elevated.
        pol.decide(0.5)          # [3,0.5] not elevated; full & theta>theta0 & quantile(R)=3<theta3? no
        pol.decide(0.5)          # [0.5,0.5] not elevated; quantile 0.5 < theta 3 => return to max(1,0.5)=1
        self.assertAlmostEqual(pol.threshold, 1.0)

    def test_escalated_returns_to_normal_when_elevation_over(self):
        pol = policy.AnchoredRecalibrationPolicy(
            theta0=1.0, block_length=2, quantile=1.0, cap=2.0, stability=4.0,
            defer_limit=0)
        pol.decide(5.0)
        pol.decide(5.0)          # escalate (beyond cap, D=0)
        self.assertEqual(pol.mode, "escalated")
        pol.decide(0.0)          # [5,0] median 2.5>1 still elevated -> stays escalated
        pol.decide(0.0)          # [0,0] median 0 not elevated -> mode returns to normal
        self.assertEqual(pol.mode, "normal")


class Determinism(unittest.TestCase):
    def test_same_sequence_same_result(self):
        import random
        rng = random.Random(55)
        scores = [rng.uniform(0, 5) for _ in range(50)]
        def run():
            pol = policy.AnchoredRecalibrationPolicy(
                theta0=1.2, block_length=10, quantile=0.95, cap=4.0,
                stability=2.0, defer_limit=10)
            return [(pol.decide(s), pol.threshold, pol.mode, pol.last_action)
                    for s in scores]
        self.assertEqual(run(), run())


class MedianAndQuantileSemantics(unittest.TestCase):
    def test_even_median_is_mean_of_two_middle(self):
        # buffer [1,2,3,4]: median = (2+3)/2 = 2.5. Use theta just below to elevate.
        pol = policy.AnchoredRecalibrationPolicy(
            theta0=2.0, block_length=4, quantile=1.0, cap=100.0, stability=100.0,
            defer_limit=10)
        for s in (1.0, 2.0, 3.0, 4.0):
            pol.decide(s)
        # buffer [1,2,3,4] median 2.5 > theta 2 elevated; stable; cand=4 recalibrate up to 4.
        self.assertAlmostEqual(pol.threshold, 4.0)
        self.assertEqual(pol.last_action, "recalibrate")


if __name__ == "__main__":
    unittest.main()
