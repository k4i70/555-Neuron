
#!/usr/bin/env python3

import argparse
import math
import re
from pathlib import Path

NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?"

SUFFIX = {
    "": 1,
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "g": 1e9,
    "t": 1e12
}

TIMING = {
    "thl": "High -> Low delay",
    "tlh": "Low -> High delay",
    "trise": "Rise time (10-90%)",
    "tfall": "Fall time (90-10%)"
}


def spice_num(token):
    token = token.strip().rstrip(",")
    match = re.fullmatch(rf"({NUM})([A-Za-z]*)", token)

    if not match:
        raise ValueError(f"Unsupported SPICE number: {token}")

    number, unit = match.groups()
    unit = unit.lower()

    if unit in ("s", "v"):
        unit = ""

    if unit.endswith(("s", "v")) and unit[:-1] in SUFFIX:
        unit = unit[:-1]

    if unit not in SUFFIX:
        raise ValueError(f"Unsupported SPICE suffix: {token}")

    return (
        float(number.replace("D", "e").replace("d", "e"))
        * SUFFIX[unit]
    )


def statements(path):
    """Combine SPICE continuation lines."""
    result = []

    for line in Path(path).read_text().splitlines():
        s = line.strip()

        if not s or s.startswith("*"):
            continue

        if s.startswith("+"):
            if result:
                result[-1] += " " + s[1:].strip()

        elif (
            s == ")"
            and result
            and result[-1].count("(") > result[-1].count(")")
        ):
            result[-1] += " )"

        else:
            result.append(s)

    return result


def get_pwl_inputs(stmts):
    """Detect ground-referenced PWL voltage sources."""
    inputs = {}

    pattern = (
        r"^(v\S+)\s+(\S+)\s+(\S+)\s+"
        r"PWL\s*\((.*?)\)"
    )

    for s in stmts:
        match = re.match(pattern, s, re.I)

        if not match:
            continue

        source, positive, negative, body = match.groups()

        if negative != "0":
            print(f"WARNING: Skipping differential source {source}")
            continue

        pieces = re.split(r"[\s,]+", body.strip())

        if len(pieces) < 4 or len(pieces) % 2:
            print(f"WARNING: Invalid PWL source {source}")
            continue

        try:
            points = [
                (
                    spice_num(pieces[i]),
                    spice_num(pieces[i + 1])
                )
                for i in range(0, len(pieces), 2)
            ]
        except ValueError as error:
            print(f"WARNING: {error}")
            continue

        if any(
            points[i][0] < points[i - 1][0]
            for i in range(1, len(points))
        ):
            print(f"WARNING: Invalid time ordering: {source}")
            continue

        inputs[positive.upper()] = points

    return inputs


def get_output_samples(stmts):
    """Find output measurements and their sample times."""
    samples = {}

    pattern = (
        r"^\.meas(?:ure)?\s+tran\s+(\S+)\s+"
        r"find\s+v\s*\(\s*([^\s)]+)\s*\)"
        r"\s+at\s*=\s*([^\s]+)"
    )

    for s in stmts:
        match = re.match(pattern, s, re.I)

        if not match:
            continue

        name, pin, time = match.groups()

        try:
            time = spice_num(time)
        except ValueError:
            print(f"WARNING: Unsupported sample time: {time}")
            continue

        samples[name.lower()] = (pin.upper(), time)

    return samples


def read_mt0(path):
    """Parse HSPICE .mt0 measurement data."""
    tokens = []

    for line in Path(path).read_text().splitlines():
        line = line.strip()

        if line and not line.startswith(("$", ".", "*")):
            tokens.extend(line.lower().split())

    try:
        end = tokens.index("alter#")
    except ValueError:
        raise ValueError("Invalid .mt0 measurement header")

    names = tokens[:end + 1]

    if "temper" not in names:
        raise ValueError("Missing temperature field")

    raw = tokens[end + 1:]
    records = []

    for i in range(0, len(raw), len(names)):
        chunk = raw[i:i + len(names)]

        if len(chunk) != len(names):
            break

        try:
            values = [
                float(v.replace("d", "e"))
                for v in chunk
            ]
        except ValueError:
            break

        records.append(dict(zip(names, values)))

    if not records:
        raise ValueError("No measurement data found")

    return records


def interpolate(points, t):
    """Calculate PWL input voltage at time t."""
    if t <= points[0][0]:
        return points[0][1]

    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t <= t1:
            if t1 == t0:
                return v1

            fraction = (t - t0) / (t1 - t0)
            return v0 + fraction * (v1 - v0)

    return points[-1][1]


def logic(voltage, vdd):
    """Convert voltage into binary logic."""
    if voltage is None or not math.isfinite(voltage):
        return "?"

    if abs(voltage) >= 1e20:
        return "?"

    if voltage <= 0.2 * vdd:
        return "0"

    if voltage >= 0.8 * vdd:
        return "1"

    return "X"


def report(data, inputs, measurements, vdd, filename):
    print("\n" + "=" * 70)
    print("             HSPICE SIMULATION REPORT")
    print("=" * 70)

    print(f"File: {filename}")
    print(f"VDD: {vdd:g} V")

    if "temper" in data:
        print(f"Temperature: {data['temper']:g} C")

    print("\nTIMING RESULTS")
    print("-" * 70)

    found = False

    for key, label in TIMING.items():
        if key not in data:
            continue

        found = True
        value = data[key]

        if math.isfinite(value) and abs(value) < 1e20:
            print(f"{label:<32} {value * 1e12:.4f} ps")
        else:
            print(f"{label:<32} UNAVAILABLE")

    for key, value in data.items():
        if key.startswith(("td_", "delay_", "t_")):
            found = True

            if math.isfinite(value) and abs(value) < 1e20:
                print(f"{key:<32} {value * 1e12:.4f} ps")

    if not found:
        print("No timing measurements found")

    input_names = sorted(inputs)
    output_names = sorted(
        set(pin for pin, _ in measurements.values())
    )

    if not input_names or not output_names:
        print("\nUnable to construct truth table.")
        return

    rows = {}

    for name, (pin, time) in measurements.items():
        input_bits = tuple(
            logic(interpolate(inputs[p], time), vdd)
            for p in input_names
        )

        voltage = data.get(name)
        output_bit = logic(voltage, vdd)

        rows.setdefault(input_bits, {})
        rows[input_bits].setdefault(pin, [])
        rows[input_bits][pin].append(output_bit)

    print("\nMEASURED TRUTH TABLE")
    print("-" * 70)

    input_widths = [
        max(len(p), 3) for p in input_names
    ]

    output_widths = [
        max(len(p), 3) for p in output_names
    ]

    def fmt(values, widths):
        return "  ".join(
            str(value).center(width)
            for value, width in zip(values, widths)
        )

    left_header = fmt(input_names, input_widths)
    right_header = fmt(output_names, output_widths)

    print(f"{left_header}  |  {right_header}")

    print(
        "-" * (len(left_header) + 2)
        + "-+-"
        + "-" * (len(right_header) + 2)
    )

    conflicts = False

    for input_bits in sorted(rows):
        output_bits = []

        for pin in output_names:
            states = set(rows[input_bits].get(pin, []))

            if len(states) == 1:
                output_bits.append(next(iter(states)))
            elif len(states) > 1:
                output_bits.append("!")
                conflicts = True
            else:
                output_bits.append("--")

        print(
            f"{fmt(input_bits, input_widths)}  |  "
            f"{fmt(output_bits, output_widths)}"
        )

    print(
        f"\nUnique input combinations: "
        f"{len(rows)} / {2 ** len(input_names)} possible"
    )

    if conflicts:
        print("WARNING: ! means conflicting output measurements")

    if any(name not in data for name in measurements):
        print("WARNING: Some output measurements are missing")

    print("X = ambiguous voltage; ? = missing/failed measurement")
    print("Only the explicitly sampled times are evaluated.")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze HSPICE timing and truth table"
    )

    parser.add_argument("sp", help="SPICE testbench")
    parser.add_argument("mt0", help="HSPICE measurement file")

    parser.add_argument(
        "--vdd",
        type=float,
        default=0.9,
        help="Supply voltage (default 0.9 V)"
    )

    args = parser.parse_args()

    if args.vdd <= 0:
        parser.error("VDD must be positive")

    try:
        stmts = statements(args.sp)
        inputs = get_pwl_inputs(stmts)
        measurements = get_output_samples(stmts)
        records = read_mt0(args.mt0)

    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")

    for data in records:
        report(
            data,
            inputs,
            measurements,
            args.vdd,
            Path(args.mt0).name
        )


if __name__ == "__main__":
    main()
