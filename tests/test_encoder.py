import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from encoder import read_trace


ROOT = Path(__file__).resolve().parents[1]


def example(name):
    return json.loads((ROOT / "examples" / f"{name}.json").read_text())


class EncoderTests(unittest.TestCase):
    def test_full_turn_against_shaft_motion_in_32_bit_register(self):
        # A 250 ms quarter turn of a 1024-cycle encoder has 1024 edges at x4.
        # Start 32 counts before overflow; the independently specified register lands on 992.
        trace = {"setup": {"bits": 32, "cycles_per_rev": 1024, "decode": 4, "max_rpm": 120},
                 "samples": [[0, 4294967264, "ok"], [250, 992, "ok"], [500, 4294967264, "ok"]]}
        rows = read_trace(trace)
        self.assertEqual([(r["delta"], r["rpm"]) for r in rows[1:]], [(1024, 60.0), (-1024, -60.0)])

    def test_identical_rotation_at_x1_x2_x4(self):
        for factor, edges in [(1, 250), (2, 500), (4, 1000)]:
            with self.subTest(decode=factor):
                trace = example("wrap")
                trace["setup"]["decode"] = factor
                trace["samples"] = [[0, 200, "ok"], [500, 200 + edges, "ok"]]
                self.assertEqual(read_trace(trace)[1]["rpm"], 30.0)

    def test_true_wrap_both_directions_and_zero(self):
        rows = read_trace(example("wrap"))
        self.assertEqual([r["delta"] for r in rows], [None, 40, -40, 0])
        self.assertEqual([r["rpm"] for r in rows], [None, 30.0, -30.0, 0.0])

    def test_fault_breaks_interval_and_reset_sets_anchor(self):
        rows = read_trace(example("quality"))
        self.assertEqual([r["status"] for r in rows], ["baseline", "reset", "valid", "fault", "baseline", "valid"])
        self.assertEqual([r["rpm"] for r in rows], [None, None, 15.0, None, None, -15.0])

    def test_plausibility_and_gap_are_distinct(self):
        rows = read_trace(example("gap"))
        self.assertEqual([r["status"] for r in rows],
                         ["baseline", "gap_too_long", "valid", "outside_speed_bound", "valid"])
        self.assertEqual([r["rpm"] for r in rows], [None, None, 75.0, None, 0.0])

    def test_gap_threshold_includes_equality(self):
        # 819.2 ms is the physical half-range; 819 ms is safe but 820 ms is not.
        for interval, expected in [(819, "valid"), (820, "gap_too_long")]:
            trace = example("wrap")
            trace["samples"] = [[0, 12, "ok"], [interval, 12, "ok"]]
            self.assertEqual(read_trace(trace)[1]["status"], expected)
        trace["setup"].update(cycles_per_rev=8192, decode=4, max_rpm=60)
        trace["samples"] = [[0, 12, "ok"], [1000, 12, "ok"]]
        self.assertEqual(read_trace(trace)[1]["status"], "gap_too_long")

    def test_half_range_tie_and_rounding_allowance(self):
        trace = example("wrap")
        trace["samples"] = [[0, 0, "ok"], [20, 32768, "ok"]]
        self.assertEqual(read_trace(trace)[1]["status"], "outside_speed_bound")
        trace["setup"]["max_rpm"] = 1
        trace["samples"] = [[0, 0, "ok"], [1, 1, "ok"], [2, 3, "ok"]]
        self.assertEqual([r["status"] for r in read_trace(trace)], ["baseline", "valid", "outside_speed_bound"])

    def test_invalid_fields_fail_instead_of_producing_a_speed(self):
        baseline = example("wrap")
        for name, value in [("time", 0), ("count", 65536), ("status", []), ("bool", True)]:
            with self.subTest(field=name):
                trace = copy.deepcopy(baseline)
                trace["samples"][1][{"time": 0, "count": 1, "status": 2, "bool": 1}[name]] = value
                with self.assertRaises(ValueError):
                    read_trace(trace)

    def test_cli_csv_and_missing_file(self):
        cmd = [sys.executable, "encoder.py"]
        result = subprocess.run([*cmd, "examples/wrap.json"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["time_ms,status,delta,rpm", "0,baseline,,",
                         "20,valid,40,30.000", "40,valid,-40,-30.000", "60,valid,0,0.000"])
        missing = subprocess.run([*cmd, "examples/missing.json"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(missing.stdout, "")
        self.assertIn("error:", missing.stderr)


if __name__ == "__main__":
    unittest.main()
