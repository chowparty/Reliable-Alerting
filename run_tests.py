"""Run the unittest suite and write a verbose log to test_results.log.

Works from any checkout location: paths are resolved relative to this file.
The log is git-ignored. For a quick console run use
``python -m unittest discover -s tests -q`` instead.
"""

import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root / "src"))

with open(repo_root / "test_results.log", "w", encoding="utf-8") as log:
    runner = unittest.TextTestRunner(stream=log, verbosity=2)
    # Same discovery as `python -m unittest discover -s tests`.
    suite = unittest.TestLoader().discover(str(repo_root / "tests"))
    result = runner.run(suite)

sys.exit(0 if result.wasSuccessful() else 1)
