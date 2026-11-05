# PLC Encoder Input Lab

Read signed shaft speed from simulated snapshots of an unsigned quadrature counter. Learn why a PLC should report an unknown speed after a reset, a reported fault, or a sampling gap that makes rollover ambiguous.

Full WIFA Robotics lesson: https://wifarobotics.com/learn/plc-encoder-input/

## Start from zero

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/). In PowerShell, run `py -3 --version`; on Linux or macOS run `python3 --version`. Download and extract the repository ZIP, then open a terminal in the folder containing `encoder.py`. Use `py -3` in place of `python3` on Windows if needed. There are no dependencies to install.

```sh
python3 encoder.py examples/wrap.json
python3 encoder.py examples/quality.json
python3 encoder.py examples/gap.json
python3 -m unittest discover -s tests -v
```

The first trace starts at register value 65,530, moves forward to 34, then reverses. It ends with a stationary window:

```text
time_ms,status,delta,rpm
0,baseline,,
20,valid,40,30.000
40,valid,-40,-30.000
60,valid,0,0.000
```

In the quality trace, 10 ms is a reset, 30 ms reports +15 RPM, 50 ms reports a fault, 70 ms is a baseline and 90 ms reports −15 RPM. In the gap trace, 1000 ms is ambiguous, 1020 ms reports +75 RPM, 1040 ms fails the speed bound, and 1060 ms reports zero net motion. Empty fields mean unknown; zero is a valid result.

## Data and changes to try

Each sample is `[time_ms, unsigned_count, status]`. Use strictly increasing integer timestamps, a count between zero and `2^bits - 1`, and status `ok`, `reset`, or `fault`. The configuration contains `bits` (16 or 32), `cycles_per_rev` (electrical cycles), `decode` (1, 2 or 4), and `max_rpm` (an assumed upper bound on absolute shaft speed). `reset` denotes a trustworthy post-reset register; map resets with untrusted data to `fault`.

Copy `examples/wrap.json` before editing it. Keep the trace fixed but change `decode` from 4 to 1. The +30 RPM result becomes +120 RPM because the software now assumes one fourth as many counts per revolution. That is a configuration mismatch, not a faster shaft. Next change only the second timestamp to 25 ms and predict the forward speed, +24 RPM, before running.

## Troubleshooting

* If Python cannot find `encoder.py`, use the directory containing it rather than its parent.
* A command that exits with code 2 found unreadable or malformed input. Check timestamp order and count range.
* A `gap_too_long` interval needs a shorter acquisition gap, a wider counter, or a physically justified bound. Do not reduce the bound just to remove the warning.
* Reversed sign can reflect a channel order or direction convention mismatch. Check the module documentation and a known direction reference.

This project uses synthetic data and no PLC, drive or motor. It assumes a wrapping unsigned register, a coherent timestamp and register value per sample, and trustworthy status indications. It does not detect every hardware fault, missed edge, or reversal within a window. Do not use this simulator for a safety function. SVG artwork and its WebP exports are in `diagrams/`.

Primary references: [Beckhoff incremental encoder basics](https://infosys.beckhoff.com/content/1033/el5101/10710739595.html), [Beckhoff EL5101 specifications](https://infosys.beckhoff.com/content/1033/el5101/9857366155.html), and [Python unittest](https://docs.python.org/3.12/library/unittest.html).
