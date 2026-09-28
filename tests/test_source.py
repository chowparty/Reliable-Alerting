"""Source-only synthetic integration checks for Aman review.

Exercises the real loading / splitting / scoring components with
hand-computed values. No labels flow through runtime paths.
"""
import dataclasses
import inspect
import math
import tempfile
from pathlib import Path
import unittest

from reliable_alerting import loading, scoring, splitting


class LoadValuesTest(unittest.TestCase):
    def test_csv_rejects_missing_current_instead_of_filling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stream.csv"
            path.write_text("datetime;Current\n0;1.5\n1;\n")
            with self.assertRaisesRegex(ValueError, "missing Current.*row 2"):
                loading.load_csv_stream(str(path), "Current")

    def test_converts_ints_to_float_tuple(self):
        self.assertEqual(loading.load_values([0, 2]), (0.0, 2.0))

    def test_accepts_generator(self):
        self.assertEqual(loading.load_values(iter([1, 2.5])), (1.0, 2.5))

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            loading.load_values([])

    def test_rejects_bool_element(self):
        for bad in ([True], [False], [1, True]):
            with self.assertRaises((TypeError, ValueError), msg=repr(bad)):
                loading.load_values(bad)

    def test_rejects_none_and_nonnumeric(self):
        for bad in ([None], [None, 1], (["a"],), ([object()],), (["1"],)):
            with self.assertRaises((TypeError, ValueError), msg=repr(bad)):
                loading.load_values(bad[0] if len(bad) == 1 and isinstance(bad[0], list) else bad)

    def test_rejects_nan_inf(self):
        for bad in ([float("nan")], [float("inf")], [float("-inf")], [0, float("nan")]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                loading.load_values(bad)

    def test_rejects_overflow_conversion(self):
        with self.assertRaises(ValueError):
            loading.load_values([10**400])

    def test_rejects_non_iterable(self):
        with self.assertRaises(TypeError):
            loading.load_values(None)


class SyntheticValuesTest(unittest.TestCase):
    def test_repeats_pattern(self):
        self.assertEqual(
            loading.synthetic_values(6, [1, 2], []), (1.0, 2.0, 1.0, 2.0, 1.0, 2.0)
        )

    def test_offset_half_open_range(self):
        got = loading.synthetic_values(
            6, [0, 0], [{"start": 2, "stop": 4, "offset": 5}]
        )
        self.assertEqual(got, (0.0, 0.0, 5.0, 5.0, 0.0, 0.0))

    def test_stop_is_exclusive(self):
        got = loading.synthetic_values(
            4, [1], [{"start": 0, "stop": 1, "offset": 10}]
        )
        self.assertEqual(got, (11.0, 1.0, 1.0, 1.0))

    def test_rejects_bad_length(self):
        for bad in (0, -3, True, 2.5, "4", None):
            with self.assertRaises((TypeError, ValueError), msg=repr(bad)):
                loading.synthetic_values(bad, [1], [])

    def test_rejects_empty_pattern(self):
        with self.assertRaises(ValueError):
            loading.synthetic_values(4, [], [])

    def test_rejects_bad_pattern_entry(self):
        for bad in ([True], [float("nan")], [float("inf")], ["x"], [None]):
            with self.assertRaises((TypeError, ValueError), msg=repr(bad)):
                loading.synthetic_values(3, bad, [])

    def test_rejects_out_of_bounds_offset(self):
        with self.assertRaises(ValueError):
            loading.synthetic_values(4, [1], [{"start": -1, "stop": 2, "offset": 1}])
        with self.assertRaises(ValueError):
            loading.synthetic_values(4, [1], [{"start": 1, "stop": 5, "offset": 1}])
        with self.assertRaises(ValueError):
            loading.synthetic_values(4, [1], [{"start": 3, "stop": 2, "offset": 1}])

    def test_rejects_bad_offset_entry(self):
        with self.assertRaises((TypeError, ValueError)):
            loading.synthetic_values(4, [1], [{"start": True, "stop": 2, "offset": 1}])
        with self.assertRaises((TypeError, ValueError)):
            loading.synthetic_values(4, [1], [{"start": 0, "stop": 2, "offset": float("nan")}])
        with self.assertRaises((TypeError, ValueError)):
            loading.synthetic_values(4, [1], [{"start": 0, "stop": 2, "offset": True}])
        with self.assertRaises(ValueError):
            loading.synthetic_values(4, [1], [{"start": 0, "stop": 2}])

    def test_rejects_nonfinite_result(self):
        with self.assertRaises(ValueError):
            loading.synthetic_values(1, [1e308], [{"start": 0, "stop": 1, "offset": 1e308}])
        with self.assertRaises(ValueError):
            loading.synthetic_values(
                1,
                [0],
                [
                    {"start": 0, "stop": 1, "offset": 1e308},
                    {"start": 0, "stop": 1, "offset": 1e308},
                ],
            )

    def test_rejects_bad_offset_keys(self):
        with self.assertRaises(ValueError):
            loading.synthetic_values(4, [1], [{"start": 0, "stop": 2}])
        with self.assertRaises(ValueError):
            loading.synthetic_values(4, [1], [{"start": 0, "stop": 2, "offset": 1, "extra": 0}])

    def test_accepts_no_labels(self):
        params = inspect.signature(loading.synthetic_values).parameters
        self.assertNotIn("labels", params)
        self.assertNotIn("label", params)


class MakeWindowsTest(unittest.TestCase):
    def test_non_aligned_split_skips_tail(self):
        values = tuple(float(i) for i in range(14))
        windows = splitting.make_windows(values, 5, 14, 4, 3, "seg")
        self.assertEqual(len(windows), 2)
        self.assertEqual((windows[0].start_index, windows[0].end_index), (5, 8))
        self.assertEqual((windows[1].start_index, windows[1].end_index), (8, 11))
        self.assertEqual(windows[0].window_id, "seg:5:8")
        self.assertEqual(windows[1].window_id, "seg:8:11")
        self.assertEqual(windows[0].values, (5.0, 6.0, 7.0, 8.0))
        self.assertEqual(windows[1].values, (8.0, 9.0, 10.0, 11.0))

    def test_window_dataclass_shape_and_frozen(self):
        w = splitting.Window(window_id="s:0:1", start_index=0, end_index=1, values=(1.0, 2.0))
        self.assertEqual(dataclasses.fields(splitting.Window)[0].name, "window_id")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            w.start_index = 9

    def test_rejects_bad_segments(self):
        values = tuple(float(i) for i in range(10))
        with self.assertRaises(ValueError):
            splitting.make_windows((), 0, 0, 2, 1, "seg")
        with self.assertRaises(ValueError):
            splitting.make_windows(values, 4, 4, 2, 1, "seg")
        with self.assertRaises(ValueError):
            splitting.make_windows(values, 6, 4, 2, 1, "seg")
        with self.assertRaises(ValueError):
            splitting.make_windows(values, -1, 4, 2, 1, "seg")
        with self.assertRaises(ValueError):
            splitting.make_windows(values, 0, 11, 2, 1, "seg")

    def test_rejects_bad_length_stride(self):
        values = tuple(float(i) for i in range(10))
        for bad in (0, -1, True, 2.5, "3"):
            with self.assertRaises((TypeError, ValueError), msg=repr(bad)):
                splitting.make_windows(values, 0, 8, bad, 1, "seg")
            with self.assertRaises((TypeError, ValueError), msg=repr(bad)):
                splitting.make_windows(values, 0, 8, 2, bad, "seg")

    def test_rejects_segment_shorter_than_length(self):
        values = tuple(float(i) for i in range(10))
        with self.assertRaises(ValueError):
            splitting.make_windows(values, 2, 4, 4, 1, "seg")

    def test_rejects_bad_segment_name(self):
        values = tuple(float(i) for i in range(10))
        with self.assertRaises((TypeError, ValueError)):
            splitting.make_windows(values, 0, 4, 2, 1, "")

    def test_rejects_nonfinite_or_nonnumeric_elements(self):
        with self.assertRaises(ValueError):
            splitting.make_windows([0.0, float("nan"), 2.0, 3.0], 0, 4, 2, 1, "seg")
        with self.assertRaises((TypeError, ValueError)):
            splitting.make_windows([0.0, True, 2.0, 3.0], 0, 4, 2, 1, "seg")
        with self.assertRaises((TypeError, ValueError)):
            splitting.make_windows([0.0, None, 2.0, 3.0], 0, 4, 2, 1, "seg")


class MeanDistanceScorerTest(unittest.TestCase):
    def test_fit_hand_values(self):
        scorer = scoring.MeanDistanceScorer.fit([0, 2])
        self.assertAlmostEqual(scorer.mean, 1.0)
        self.assertAlmostEqual(scorer.std, 1.0)

    def test_score_hand_values(self):
        eps = 1e-6
        scorer = scoring.MeanDistanceScorer.fit([0, 2], epsilon=eps)
        self.assertAlmostEqual(scorer.score([3, 3]), 2.0 / (1.0 + eps))

    def test_constant_source(self):
        eps = 1e-6
        scorer = scoring.MeanDistanceScorer.fit([5, 5, 5], epsilon=eps)
        self.assertAlmostEqual(scorer.std, 0.0)
        self.assertAlmostEqual(scorer.score([5, 5]), 0.0)
        self.assertAlmostEqual(scorer.score([7, 7]), 2.0 / eps)

    def test_rejects_bad_fit(self):
        with self.assertRaises(ValueError):
            scoring.MeanDistanceScorer.fit([1])
        with self.assertRaises(ValueError):
            scoring.MeanDistanceScorer.fit([])
        with self.assertRaises((TypeError, ValueError)):
            scoring.MeanDistanceScorer.fit([0, True])
        with self.assertRaises(ValueError):
            scoring.MeanDistanceScorer.fit([0, float("nan")])
        for bad_eps in (0, -1e-6, float("nan"), float("inf"), True):
            with self.assertRaises((TypeError, ValueError), msg=repr(bad_eps)):
                scoring.MeanDistanceScorer.fit([0, 2], epsilon=bad_eps)

    def test_rejects_bad_score_input(self):
        scorer = scoring.MeanDistanceScorer.fit([0, 2])
        with self.assertRaises(ValueError):
            scorer.score([])
        with self.assertRaises(ValueError):
            scorer.score([1, float("nan")])
        with self.assertRaises(ValueError):
            scorer.score([1, float("inf")])

    def test_rejects_nonfinite_output(self):
        scorer = scoring.MeanDistanceScorer.fit([0, 0], epsilon=1e-6)
        with self.assertRaises(ValueError):
            scorer.score([1e308, 1e308])

    def test_scorer_frozen_and_no_labels(self):
        scorer = scoring.MeanDistanceScorer.fit([0, 2])
        with self.assertRaises(dataclasses.FrozenInstanceError):
            scorer.mean = 0.0
        self.assertNotIn("label", inspect.signature(scorer.score).parameters)
        self.assertNotIn("labels", inspect.signature(scoring.MeanDistanceScorer.fit).parameters)

    def test_direct_construction_validated(self):
        with self.assertRaises(ValueError):
            scoring.MeanDistanceScorer(mean=0.0, std=-1.0, epsilon=1e-6)
        with self.assertRaises(ValueError):
            scoring.MeanDistanceScorer(mean=0.0, std=float("nan"), epsilon=1e-6)
        with self.assertRaises((TypeError, ValueError)):
            scoring.MeanDistanceScorer(mean=True, std=1.0, epsilon=1e-6)
        with self.assertRaises(ValueError):
            scoring.MeanDistanceScorer(mean=0.0, std=1.0, epsilon=0.0)
        with self.assertRaises(ValueError):
            scoring.MeanDistanceScorer(mean=0.0, std=1e308, epsilon=1e308)

    def test_future_mutation_leaves_earlier_scores_unchanged(self):
        raw = list(float(i) for i in range(12))
        values = loading.load_values(raw)
        windows = splitting.make_windows(values, 0, 12, 4, 4, "seg")
        scorer = scoring.MeanDistanceScorer.fit(values[:4])
        before = [scorer.score(w.values) for w in windows]
        raw[10] = 999.0
        mutated = loading.load_values(raw)
        self.assertNotEqual(mutated[10], values[10])
        rebuilt = splitting.make_windows(mutated, 0, 12, 4, 4, "seg")
        self.assertEqual(
            [w.values for w in rebuilt[:2]], [w.values for w in windows[:2]]
        )
        self.assertEqual([scorer.score(w.values) for w in rebuilt[:2]], before[:2])
        self.assertNotEqual(scorer.score(rebuilt[2].values), before[2])
        self.assertIsInstance(windows[0].values, tuple)


if __name__ == "__main__":
    unittest.main()
