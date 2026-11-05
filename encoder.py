"""Interpret synthetic samples of an unsigned PLC encoder register."""
from dataclasses import dataclass
import argparse
import json
from pathlib import Path

STATUSES = {"ok", "reset", "fault"}


def integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


@dataclass(frozen=True)
class Setup:
    bits: int
    cycles_per_rev: int
    decode: int
    max_rpm: int

    def __post_init__(self):
        if type(self.bits) is not int or self.bits not in (16, 32):
            raise ValueError("bits must be 16 or 32")
        integer(self.cycles_per_rev, "cycles_per_rev", 1, 1_000_000)
        if type(self.decode) is not int or self.decode not in (1, 2, 4):
            raise ValueError("decode must be 1, 2 or 4")
        integer(self.max_rpm, "max_rpm", 1, 1_000_000)

    @property
    def modulus(self):
        return 1 << self.bits

    @property
    def counts_per_rev(self):
        return self.cycles_per_rev * self.decode


def read_trace(payload):
    if not isinstance(payload, dict) or set(payload) != {"setup", "samples"}:
        raise ValueError("input needs setup and samples")
    config = payload["setup"]
    if not isinstance(config, dict) or set(config) != {"bits", "cycles_per_rev", "decode", "max_rpm"}:
        raise ValueError("setup needs bits, cycles_per_rev, decode and max_rpm")
    setup = Setup(**config)
    samples = payload["samples"]
    if not isinstance(samples, list) or not samples:
        raise ValueError("samples must be a nonempty array")
    last_time = -1
    anchor = None
    output = []
    for row in samples:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("each sample must be [time_ms, unsigned_count, status]")
        time_ms, count, status = row
        integer(time_ms, "time_ms", 0, 10**12)
        integer(count, "unsigned_count", 0, setup.modulus - 1)
        if time_ms <= last_time:
            raise ValueError("sample times must strictly increase")
        if not isinstance(status, str) or status not in STATUSES:
            raise ValueError("status must be ok, reset or fault")
        last_time = time_ms
        result = {"time_ms": time_ms, "delta": None, "rpm": None}
        if status == "fault":
            reason = "fault"
            anchor = None
        elif status == "reset":
            reason = "reset"
            anchor = (time_ms, count)
        elif anchor is None:
            reason = "baseline"
            anchor = (time_ms, count)
        else:
            before_ms, before_count = anchor
            elapsed_ms = time_ms - before_ms
            half = setup.modulus // 2
            # Ceiling allows up to one count for endpoint quantization.
            numerator = setup.max_rpm * setup.counts_per_rev * elapsed_ms
            limit = (numerator + 59_999) // 60_000
            residue = (count - before_count) % setup.modulus
            delta = residue if residue < half else residue - setup.modulus
            if limit >= half:
                reason = "gap_too_long"
            elif residue == half or abs(delta) > limit:
                reason = "outside_speed_bound"
            else:
                reason = "valid"
                result["delta"] = delta
                result["rpm"] = delta * 60_000 / (setup.counts_per_rev * elapsed_ms)
            anchor = (time_ms, count)
        result["status"] = reason
        output.append(result)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    try:
        result = read_trace(json.loads(args.trace.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print("time_ms,status,delta,rpm")
    for row in result:
        delta = "" if row["delta"] is None else str(row["delta"])
        rpm = "" if row["rpm"] is None else f'{row["rpm"]:.3f}'
        print(f'{row["time_ms"]},{row["status"]},{delta},{rpm}')


if __name__ == "__main__":
    main()
