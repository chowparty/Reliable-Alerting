"""H1 mechanism property test (frozen protocol section 2, H1).

Characterises the EXISTING RollingThresholdPolicy: with
admission_rule="normal_only" the threshold is a one-way ratchet (monotone
non-increasing) over any score sequence, because a score above the current
threshold is an alert and is never admitted into the recomputation buffer, so
the buffer only ever holds scores at or below the threshold and its
nearest-rank quantile cannot exceed the current threshold.

The counter-test shows admission_rule="all" CAN increase the threshold: an
above-threshold score is admitted, so the quantile of the buffer can rise.

These are property tests over many seeded random sequences (random.Random),
sweeping L and q. They pass on the current code (this file characterises it;
no change to policy.py is required for it).
"""
import random
import unittest

from reliable_alerting import policy


def _run_thresholds(scores, initial, length, quantile, admission_rule):
    pol = policy.RollingThresholdPolicy(initial, length, quantile, admission_rule)
    seen = [pol.threshold]
    for s in scores:
        pol.decide(s)
        seen.append(pol.threshold)
    return seen


class NormalOnlyIsMonotoneNonIncreasing(unittest.TestCase):
    def test_never_increases_over_random_sequences(self):
        rng = random.Random(20260929)
        for trial in range(400):
            length = rng.choice([2, 3, 5, 8, 10, 13])
            quantile = rng.choice([0.5, 0.75, 0.9, 0.95, 0.99, 1.0])
            initial = rng.uniform(0.5, 5.0)
            n = rng.randint(1, 60)
            # Scores span both sides of the initial threshold.
            scores = [rng.uniform(0.0, 2.0 * initial + 3.0) for _ in range(n)]
            seen = _run_thresholds(scores, initial, length, quantile, "normal_only")
            for prev, cur in zip(seen, seen[1:]):
                self.assertLessEqual(
                    cur, prev + 1e-12,
                    msg=(f"normal_only threshold increased: {prev} -> {cur} "
                         f"(trial={trial}, L={length}, q={quantile}, "
                         f"init={initial}, scores={scores})"),
                )

    def test_monotone_even_when_all_scores_below(self):
        # A degenerate all-admitted case still cannot increase under normal_only.
        rng = random.Random(7)
        for _ in range(50):
            initial = rng.uniform(1.0, 3.0)
            scores = [rng.uniform(0.0, initial) for _ in range(rng.randint(1, 40))]
            seen = _run_thresholds(scores, initial, 10, 0.95, "normal_only")
            for prev, cur in zip(seen, seen[1:]):
                self.assertLessEqual(cur, prev + 1e-12)


class AllAdmissionCanIncrease(unittest.TestCase):
    def test_all_admission_can_increase_threshold(self):
        # Counter-test: admit-all lets an above-threshold score raise the
        # threshold. Find at least one increase across randomized sequences.
        rng = random.Random(101)
        observed_increase = False
        for _ in range(400):
            length = rng.choice([2, 3, 5, 10])
            quantile = rng.choice([0.5, 0.9, 0.95, 1.0])
            initial = rng.uniform(0.5, 3.0)
            n = rng.randint(2, 40)
            scores = [rng.uniform(0.0, 4.0 * initial + 5.0) for _ in range(n)]
            seen = _run_thresholds(scores, initial, length, quantile, "all")
            if any(cur > prev + 1e-9 for prev, cur in zip(seen, seen[1:])):
                observed_increase = True
                break
        self.assertTrue(
            observed_increase,
            "admission_rule='all' never increased the threshold across trials",
        )

    def test_all_admission_specific_increase(self):
        # Hand case: an above-threshold score is admitted and raises it.
        pol = policy.RollingThresholdPolicy(1.0, 3, 1.0, "all")
        self.assertEqual(pol.decide(5.0), "alert")
        self.assertGreater(pol.threshold, 1.0)


if __name__ == "__main__":
    unittest.main()
