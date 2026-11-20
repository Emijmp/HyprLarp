"""Long-run reporting rejects real growth and keeps its short-smoke limits clear."""

import unittest

from tools.soak import summarize


class SoakReportTests(unittest.TestCase):
  def test_warmup_is_excluded_from_growth_budget(self):
    samples = [{"elapsed": 0, "rssMiB": 1}, {"elapsed": 121, "rssMiB": 200},
      {"elapsed": 140, "rssMiB": 202}, {"elapsed": 160, "rssMiB": 201}]
    report = summarize(samples, 120, 64)
    self.assertTrue(report["memory_checked"])
    self.assertTrue(report["stable"])
    self.assertEqual(report["growth_mib"], 1)

  def test_growing_and_insufficient_measurements_are_distinguished(self):
    self.assertFalse(summarize([], 120, 64)["memory_checked"])
    samples = [{"elapsed": 121, "rssMiB": 200}, {"elapsed": 140, "rssMiB": 250},
      {"elapsed": 160, "rssMiB": 300}]
    report = summarize(samples, 120, 64)
    self.assertFalse(report["stable"])
    self.assertEqual(report["growth_mib"], 100)

  def test_window_medians_tolerate_one_short_peak(self):
    values = [200] * 6 + [700] + [202] * 8
    report = summarize([{"elapsed": 121 + i, "rssMiB": value} for i, value in enumerate(values)], 120, 64)
    self.assertTrue(report["stable"])
    self.assertEqual(report["growth_mib"], 2)
    self.assertEqual(report["peak_rss_mib"], 700)
