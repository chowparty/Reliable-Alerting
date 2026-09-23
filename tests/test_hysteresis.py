"""Day-4 hysteresis policy checks (hand-derived, no labels in runtime paths)."""
import dataclasses
import inspect
import unittest

from reliable_alerting import policy


class HysteresisInitTest(unittest.TestCase):
    def test_starts_normal(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        self.assertEqual(pol.state, "normal")

    def test_levels_are_validated_numbers(self):
        pol = policy.HysteresisPolicy(low=1, high=2)
        self.assertEqual(pol.low, 1.0)
        self.assertEqual(pol.high, 2.0)

    def test_rejects_equal_and_reversed_levels(self):
        with self.assertRaises(ValueError):
            policy.HysteresisPolicy(low=2.0, high=2.0)
        with self.assertRaises(ValueError):
            policy.HysteresisPolicy(low=3.0, high=2.0)

    def test_rejects_nonfinite_levels(self):
        for low, high in (
            (float("nan"), 2.0),
            (1.0, float("nan")),
            (float("inf"), 2.0),
            (1.0, float("inf")),
            (float("-inf"), 2.0),
            (1.0, float("-inf")),
        ):
            with self.assertRaises(ValueError, msg=repr((low, high))):
                policy.HysteresisPolicy(low=low, high=high)

    def test_rejects_non_numeric_levels(self):
        for low, high in (
            (True, 2.0),
            (1.0, False),
            (None, 2.0),
            (1.0, None),
            ("1.0", 2.0),
            (1.0, "2.0"),
            (object(), 2.0),
        ):
            with self.assertRaises(TypeError, msg=repr((low, high))):
                policy.HysteresisPolicy(low=low, high=high)

    def test_levels_and_state_are_read_only(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
            pol.low = 0.0
        with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
            pol.high = 5.0
        with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
            pol.state = "alert"

    def test_accepts_no_labels(self):
        params = inspect.signature(policy.HysteresisPolicy.__init__).parameters
        self.assertNotIn("labels", params)
        self.assertNotIn("label", params)
        decide_params = inspect.signature(policy.HysteresisPolicy.decide).parameters
        self.assertNotIn("labels", decide_params)
        self.assertNotIn("label", decide_params)


class HysteresisTransitionsTest(unittest.TestCase):
    def test_normal_to_alert_only_above_high(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        self.assertEqual(pol.decide(2.0), "normal")  # equality preserves normal
        self.assertEqual(pol.state, "normal")
        self.assertEqual(pol.decide(2.0001), "alert")
        self.assertEqual(pol.state, "alert")

    def test_band_holds_normal(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        self.assertEqual(pol.decide(1.5), "normal")
        self.assertEqual(pol.decide(1.0001), "normal")
        self.assertEqual(pol.state, "normal")

    def test_band_holds_alert_and_low_equality_preserves(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        pol.decide(2.5)
        self.assertEqual(pol.state, "alert")
        self.assertEqual(pol.decide(1.0), "alert")  # equality preserves alert
        self.assertEqual(pol.decide(1.5), "alert")
        self.assertEqual(pol.decide(1.9999), "alert")

    def test_alert_to_normal_only_below_low(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        pol.decide(3.0)
        self.assertEqual(pol.decide(0.9999), "normal")
        self.assertEqual(pol.state, "normal")

    def test_repeated_on_off_cycles(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        scores = [0.5, 2.5, 0.5, 2.5, 0.5]
        expected = ["normal", "alert", "normal", "alert", "normal"]
        self.assertEqual([pol.decide(s) for s in scores], expected)

    def test_spike_holds_unwanted_tail(self):
        # Hand-derived: spike 2.5 latches alert; tail 1.5 stays alert
        # under hysteresis but would be normal under a fixed 2.0 cut.
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        scores = [0.5, 2.5, 1.5, 1.5, 0.5]
        expected = ["normal", "alert", "alert", "alert", "normal"]
        self.assertEqual([pol.decide(s) for s in scores], expected)

    def test_reset_returns_to_normal(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        pol.decide(5.0)
        self.assertEqual(pol.state, "alert")
        pol.reset()
        self.assertEqual(pol.state, "normal")
        # Band score stays normal after reset (was alert before reset).
        self.assertEqual(pol.decide(1.5), "normal")


class HysteresisRobustnessTest(unittest.TestCase):
    def test_rejects_bad_scores(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError, msg=repr(bad)):
                pol.decide(bad)
        for bad in (None, True, False, "1.0", object()):
            with self.assertRaises(TypeError, msg=repr(bad)):
                pol.decide(bad)

    def test_invalid_score_does_not_mutate_state(self):
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        pol.decide(2.5)
        self.assertEqual(pol.state, "alert")
        with self.assertRaises(ValueError):
            pol.decide(float("nan"))
        self.assertEqual(pol.state, "alert")
        self.assertEqual(pol.decide(1.5), "alert")

        pol2 = policy.HysteresisPolicy(low=1.0, high=2.0)
        with self.assertRaises(TypeError):
            pol2.decide(True)
        self.assertEqual(pol2.state, "normal")

    def test_separate_instances_do_not_leak(self):
        a = policy.HysteresisPolicy(low=1.0, high=2.0)
        b = policy.HysteresisPolicy(low=1.0, high=2.0)
        a.decide(9.0)
        self.assertEqual(a.state, "alert")
        self.assertEqual(b.state, "normal")
        # Repeated runs from fresh instances agree.
        for _ in range(3):
            fresh = policy.HysteresisPolicy(low=1.0, high=2.0)
            self.assertEqual([fresh.decide(s) for s in (0.5, 2.5, 1.5)], ["normal", "alert", "alert"])

    def test_prefix_invariance_to_future_scores(self):
        prefix = [0.5, 2.5, 1.5, 0.9]
        prefix_out = ["normal", "alert", "alert", "normal"]
        pol = policy.HysteresisPolicy(low=1.0, high=2.0)
        got_prefix = [pol.decide(s) for s in prefix]
        self.assertEqual(got_prefix, prefix_out)
        # Appending future scores cannot rewrite already-returned prefix outputs.
        extended = prefix + [2.5, 1.5]
        fresh = policy.HysteresisPolicy(low=1.0, high=2.0)
        got_extended = [fresh.decide(s) for s in extended]
        self.assertEqual(got_extended[: len(prefix)], got_prefix)
        # Mutating the caller's input list afterwards leaves recorded outputs fixed.
        recorded = list(got_extended)
        extended.append(9.0)
        self.assertEqual(recorded, got_extended)


if __name__ == "__main__":
    unittest.main()
