import sys
import unittest

sys.path.insert(0, r"d:\Reliable-Alerting\src")
with open("test_results.log", "w", encoding="utf-8") as f:
    runner = unittest.TextTestRunner(stream=f, verbosity=2)
    tests = unittest.TestLoader().discover("tests")
    runner.run(tests)
