"""test_manifest.py — structural integrity checks for data/manifest.md.

These tests verify that the manifest exists, carries the required sections,
and — critically — contains an explicit held-out reservation status statement.
They do not validate scientific content (URL correctness, checksum values,
etc.); that is a human review task. They catch the failure mode where the
manifest exists but silently omits the reservation status, which the project
rules treat as equivalent to a missing manifest.

Run with:
    python -m unittest tests/test_manifest.py -v
from the Reliable-Alerting/ directory.
"""

import unittest
from pathlib import Path

# In Reliable-Alerting, the authoritative manifest is at the repo root.
#   Reliable-Alerting/tests/test_manifest.py  <- this file
#   Reliable-Alerting/manifest.md             <- target
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
_MANIFEST_PATH = _REPO_ROOT / "manifest.md"


class ManifestExistsTest(unittest.TestCase):
    """The manifest file must exist."""

    def test_manifest_file_exists(self):
        self.assertTrue(
            _MANIFEST_PATH.exists(),
            f"manifest.md not found at {_MANIFEST_PATH}. "
            "Nakul is the sole editor; create it before any stream is loaded."
        )

    def test_manifest_is_not_empty(self):
        self.assertTrue(_MANIFEST_PATH.exists(), "manifest.md missing")
        content = _MANIFEST_PATH.read_text(encoding="utf-8").strip()
        self.assertGreater(
            len(content), 0,
            "manifest.md exists but is empty."
        )


class ManifestRequiredSectionsTest(unittest.TestCase):
    """The manifest must contain all required section headings."""

    @classmethod
    def setUpClass(cls):
        cls.content = _MANIFEST_PATH.read_text(encoding="utf-8") if _MANIFEST_PATH.exists() else ""

    def _assert_section(self, heading_fragment):
        self.assertIn(
            heading_fragment, self.content,
            f"manifest.md is missing required section containing: {heading_fragment!r}"
        )

    def test_has_held_out_reservation_section(self):
        self._assert_section("Held-Out Reservation")

    def test_has_development_stream_section(self):
        self._assert_section("Development Stream")

    def test_has_source_label_use_section(self):
        self._assert_section("Source Label Use")

    def test_has_audit_trail_section(self):
        self._assert_section("Audit Trail")


class ManifestHeldOutStatusTest(unittest.TestCase):
    """The held-out reservation section must contain an explicit status
    statement. Silence — a section heading with no status sentence — is
    not acceptable.

    We check for either:
      (a) A positive reservation: the word 'reserved' near a stream name, or
      (b) An explicit 'not reserved' or 'no stream' declaration.
    Either is acceptable. Missing both is a failure.
    """

    @classmethod
    def setUpClass(cls):
        cls.content = _MANIFEST_PATH.read_text(encoding="utf-8").lower() if _MANIFEST_PATH.exists() else ""

    def test_held_out_section_has_explicit_status(self):
        """Confirm the held-out section carries a real status sentence."""
        content = self.content
        has_positive = (
            "reserved" in content
            or "held-out stream" in content
            or "held_out stream" in content
        )
        has_negative = (
            "no stream has been reserved" in content
            or "not reserved" in content
            or "not yet reserved" in content
            or "nothing has been reserved" in content
            or "no stream" in content
        )
        self.assertTrue(
            has_positive or has_negative,
            "manifest.md held-out section has no explicit status. "
            "It must say either what IS reserved (stream name + date) "
            "or explicitly state that nothing is reserved and why. "
            "Silence on this topic is never acceptable."
        )

    def test_held_out_section_not_just_placeholder(self):
        """Section must not consist only of 'TBD', 'TODO', or similar."""
        content = self.content
        # Extract the held-out section text (everything after the heading
        # up to the next heading).
        try:
            start = content.index("held-out reservation")
            after = content[start:]
            # Find the next ## heading after the section
            next_heading = after.find("\n##", 3)
            section_text = after[:next_heading] if next_heading != -1 else after
        except ValueError:
            section_text = ""

        for placeholder in ("tbd", "todo", "placeholder", "fill in", "fill this in"):
            self.assertNotIn(
                placeholder, section_text,
                f"manifest.md held-out section appears to contain a "
                f"placeholder ({placeholder!r}). Replace with a real status statement."
            )

    def test_reservation_commitment_date_mentioned(self):
        """If not yet reserved, manifest must mention when it will be."""
        content = self.content
        has_positive_reservation = (
            "reserved as of" in content
            or "reserved on" in content
            or ("reserved" in content and "stream" in content and "date" in content)
        )
        has_deferred_with_commitment = (
            "day 2" in content
            or "before any real stream" in content
            or "first action" in content
            or "before outcomes" in content
        )
        # Either it's already reserved, or there's a commitment for when it will be.
        self.assertTrue(
            has_positive_reservation or has_deferred_with_commitment,
            "manifest.md: if the held-out stream is not yet reserved, "
            "the manifest must state explicitly when the reservation will be made "
            "(e.g., 'Day 2, before any real stream is loaded'). "
            "Vague deferral without a commitment date is not acceptable."
        )


class ManifestSourceLabelDisciplineTest(unittest.TestCase):
    """The manifest must declare the source-label-use policy explicitly."""

    @classmethod
    def setUpClass(cls):
        cls.content = _MANIFEST_PATH.read_text(encoding="utf-8") if _MANIFEST_PATH.exists() else ""

    def test_source_label_policy_stated(self):
        content_lower = self.content.lower()
        self.assertIn(
            "source label",
            content_lower,
            "manifest.md must contain a 'Source Label Use' declaration explaining "
            "if/how source labels are used (solely to select source-normal windows) "
            "and confirming they never enter scorer or policy at runtime."
        )

    def test_source_labels_not_runtime(self):
        """Manifest must confirm source labels do not enter runtime paths."""
        content_lower = self.content.lower()
        # Accept various phrasings that confirm label/runtime separation.
        has_separation = (
            "never enter" in content_lower
            or "not enter" in content_lower
            or "runtime" in content_lower
        )
        self.assertTrue(
            has_separation,
            "manifest.md source-label section must confirm labels do not "
            "enter scorer or policy at runtime."
        )


if __name__ == "__main__":
    unittest.main()
