"""
infer_fields.py
---------------
Read a CSV of new hardware entries (with partial fields like name, manufacturer,
category, year, hashrate, power_draw, rarity, description) and infer/extrapolate
the missing HARDWARE_DB fields (id, chipset, clock_mhz, word_bits, cores,
type, process_nm, transistors, tdp_watts) using the existing DB as reference.

Usage:
    python tools/infer_fields.py new_gpus.csv                     # prints to stdout
    python tools/infer_fields.py new_gpus.csv -o filled.csv       # writes CSV
    python tools/infer_fields.py new_gpus.csv --format dict       # prints Python dicts (paste-ready)
"""

import argparse
import csv
import re
import sys
import os
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Reference data loaded once ──────────────────────────────────────────────

_REF = None

def _load_ref():
    """Try loading HARDWARE_DB; return empty list if discord isn't installed."""
    global _REF
    if _REF is not None:
        return _REF
    try:
        from cogs.trash_collector import HARDWARE_DB
        _REF = HARDWARE_DB
    except ImportError:
        # discord not available (CLI-only usage) — rely on KNOWN_SPECS
        _REF = []
    return _REF


# ── Lookup tables built from existing DB ────────────────────────────────────

def _build_year_to_process(db):
    """Map (type, year) -> median process_nm from existing entries."""
    buckets = {}
    for hw in db:
        key = (hw.get("type", "GPU"), hw.get("year"))
        if key[1] and hw.get("process_nm"):
            buckets.setdefault(key, []).append(hw["process_nm"])
    return {k: statistics.median(v) for k, v in buckets.items()}


def _build_year_to_transistors(db):
    """Map (type, year) -> median transistors from existing entries."""
    buckets = {}
    for hw in db:
        key = (hw.get("type", "GPU"), hw.get("year"))
        t = hw.get("transistors", 0)
        if key[1] and t and t > 0:
            buckets.setdefault(key, []).append(t)
    return {k: int(statistics.median(v)) for k, v in buckets.items()}


def _build_year_to_clock(db):
    """Map (type, year) -> median clock_mhz."""
    buckets = {}
    for hw in db:
        key = (hw.get("type", "GPU"), hw.get("year"))
        c = hw.get("clock_mhz", 0)
        if key[1] and c:
            buckets.setdefault(key, []).append(c)
    return {k: round(statistics.median(v), 1) for k, v in buckets.items()}


def _build_year_to_cores(db):
    """Map (type, year) -> median cores."""
    buckets = {}
    for hw in db:
        key = (hw.get("type", "GPU"), hw.get("year"))
        c = hw.get("cores", 0)
        if key[1] and c:
            buckets.setdefault(key, []).append(c)
    return {k: int(statistics.median(v)) for k, v in buckets.items()}


# ── Known GPU specs for common models (saves web lookups) ──────────────────

KNOWN_SPECS = {
    # name -> (clock_mhz, cores, process_nm, transistors)
    "GeForce GTX 1080":        (1733.0, 2560, 16, 7_200_000_000),
    "GeForce RTX 3080":        (1710.0, 8704, 8,  28_300_000_000),
    "GeForce RTX 3090":        (1695.0, 10496, 8, 28_300_000_000),
    "Radeon RX 580":           (1257.0, 2304, 14, 5_700_000_000),
    "Radeon RX 5700 XT":       (1905.0, 2560, 7,  10_300_000_000),
    "GeForce GTX 1060 6GB":    (1708.0, 1280, 16, 4_400_000_000),
    "GeForce GTX 1070":        (1683.0, 1920, 16, 7_200_000_000),
    "GeForce GTX 1660 Super":  (1785.0, 1408, 12, 6_600_000_000),
    "Radeon RX Vega 64":       (1546.0, 4096, 14, 12_500_000_000),
    "GeForce RTX 2060":        (1680.0, 1920, 12, 10_800_000_000),
    "GeForce RTX 3070":        (1725.0, 5888, 8,  17_400_000_000),
    "GeForce RTX 3060 Ti":     (1665.0, 4864, 8,  17_400_000_000),
    "Radeon RX 470":           (1206.0, 2048, 14, 5_700_000_000),
    "GeForce GTX 970":         (1178.0, 1664, 28, 5_200_000_000),
    "GeForce GTX 780 Ti":      (876.0,  2880, 28, 7_100_000_000),
    "Radeon R9 290X":          (1000.0, 2816, 28, 6_200_000_000),
    "GeForce GTX 460":         (675.0,  336,  40, 1_950_000_000),
    "Radeon HD 7970":          (925.0,  2048, 28, 4_312_000_000),
    "GeForce 8800 GTX":        (575.0,  128,  90, 681_000_000),
    "GeForce 4 Ti 4600":       (300.0,  4,    150, 63_000_000),
    "Radeon 9700 Pro":         (325.0,  8,    150, 110_000_000),
    "Voodoo2 12MB":            (90.0,   1,    350, 3_000_000),
    "Matrox G400":             (150.0,  1,    250, 12_000_000),
    "Intel Arc A770":          (2100.0, 4096, 6,   21_700_000_000),
    "GeForce RTX 4090":        (2520.0, 16384, 5,  76_300_000_000),
    "Radeon RX 7900 XTX":      (2499.0, 6144, 5,  57_700_000_000),
    "GeForce RTX 2080 Ti":     (1545.0, 4352, 12, 18_600_000_000),
    "Titan V":                 (1455.0, 5120, 12, 21_100_000_000),
    "GeForce GTX 750 Ti":      (1085.0, 640,  28, 1_870_000_000),
    "Radeon HD 5850":          (725.0,  1440, 40, 2_154_000_000),
}

# ── Chipset string generator ───────────────────────────────────────────────

def _make_chipset(name, clock_mhz):
    """Generate a chipset tag like 'GTX1080-1733MHz' from the card name."""
    # strip common prefixes
    short = name
    for prefix in ("GeForce ", "Radeon ", "Intel ", "Nvidia ", "AMD ", "NVIDIA "):
        short = short.replace(prefix, "")
    short = re.sub(r"[^A-Za-z0-9]", "", short)
    return f"{short}-{int(clock_mhz)}MHz"


# ── ID generator ───────────────────────────────────────────────────────────

def _make_id(name, manufacturer):
    """Generate a snake_case id like 'nvidia_gtx_1080'."""
    mfr = manufacturer.lower().split()[0]
    # normalize common names
    mfr_map = {"nvidia": "nvidia", "amd": "amd", "ati": "ati", "3dfx": "3dfx",
               "intel": "intel", "matrox": "matrox"}
    mfr = mfr_map.get(mfr, mfr)

    short = name
    for prefix in ("GeForce ", "Radeon ", "Intel ", "Nvidia ", "AMD ", "NVIDIA "):
        short = short.replace(prefix, "")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", short).strip("_").lower()
    return f"{mfr}_{slug}"


# ── Category -> type mapping ──────────────────────────────────────────────

CATEGORY_TO_TYPE = {
    "gpu": "GPU", "cpu": "CPU", "apu": "APU", "fpga": "FPGA",
    "asic": "ASIC", "npu": "NPU", "tpu": "TPU", "dsp": "DSP",
    "mcu": "MCU", "soc": "SOC", "fpu": "FPU", "coprocessor": "COPROCESSOR",
    "custom": "CUSTOM",
}


# ── Parse hashrate string ─────────────────────────────────────────────────

def _parse_hashrate(s):
    """Parse '28.5 MH/s' -> float MH/s (kept for reference, not stored in DB)."""
    if not s:
        return 0.0
    m = re.match(r"([\d.]+)\s*(MH/s|GH/s|KH/s|H/s)", str(s), re.IGNORECASE)
    if not m:
        return float(re.sub(r"[^\d.]", "", str(s)) or 0)
    val = float(m.group(1))
    unit = m.group(2).upper()
    multipliers = {"H/S": 1e-6, "KH/S": 1e-3, "MH/S": 1.0, "GH/S": 1000.0}
    return val * multipliers.get(unit, 1.0)


# ── Parse power string ────────────────────────────────────────────────────

def _parse_watts(s):
    """Parse '180 W' -> 180.0"""
    if not s:
        return 0.0
    m = re.match(r"([\d.]+)", str(s))
    return float(m.group(1)) if m else 0.0


# ── Main inference ─────────────────────────────────────────────────────────

def infer_entry(row, yr_proc, yr_trans, yr_clock, yr_cores):
    """Take a partial row dict and return a full HARDWARE_DB-style dict."""
    name = row.get("name", "").strip()
    manufacturer = row.get("manufacturer", "").strip()
    category = row.get("category", "GPU").strip()
    year = int(row.get("year", 0))
    rarity = row.get("rarity", "common").strip()
    description = row.get("description", "").strip()
    tdp = _parse_watts(row.get("power_draw") or row.get("tdp_watts") or "0")

    hw_type = CATEGORY_TO_TYPE.get(category.lower(), category.upper())

    # look up known specs or fall back to year-median extrapolation
    known = KNOWN_SPECS.get(name)
    if known:
        clock_mhz, cores, process_nm, transistors = known
    else:
        key = (hw_type, year)
        clock_mhz = yr_clock.get(key, 1000.0)
        cores = yr_cores.get(key, 1)
        process_nm = yr_proc.get(key, 28)
        transistors = yr_trans.get(key, 0)

    entry = {
        "id": _make_id(name, manufacturer),
        "name": name,
        "chipset": _make_chipset(name, clock_mhz),
        "manufacturer": manufacturer,
        "year": year,
        "clock_mhz": clock_mhz,
        "word_bits": 32,
        "cores": cores,
        "type": hw_type,
        "process_nm": process_nm,
        "transistors": transistors,
        "description": description,
        "rarity": rarity,
        "tdp_watts": tdp,
    }
    return entry


def read_new_csv(path):
    """Read a CSV with at least name, manufacturer, year columns."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def format_as_python(entries):
    """Return a paste-ready Python string of the list of dicts."""
    lines = []
    for e in entries:
        lines.append("    {")
        for k, v in e.items():
            if isinstance(v, str):
                # escape any quotes in strings
                v_esc = v.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'        "{k}": "{v_esc}",')
            elif isinstance(v, float):
                lines.append(f'        "{k}": {v},')
            else:
                lines.append(f'        "{k}": {v},')
        lines.append("    },")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Infer missing HARDWARE_DB fields from a partial CSV")
    parser.add_argument("input", help="Input CSV with partial fields")
    parser.add_argument("-o", "--output", default=None,
                        help="Output CSV path (default: stdout)")
    parser.add_argument("--format", choices=["csv", "dict"], default="csv",
                        help="Output format: csv (default) or dict (Python paste-ready)")
    args = parser.parse_args()

    db = _load_ref()
    yr_proc = _build_year_to_process(db)
    yr_trans = _build_year_to_transistors(db)
    yr_clock = _build_year_to_clock(db)
    yr_cores = _build_year_to_cores(db)

    rows = read_new_csv(args.input)
    entries = [infer_entry(r, yr_proc, yr_trans, yr_clock, yr_cores) for r in rows]

    if args.format == "dict":
        output = format_as_python(entries)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Wrote {len(entries)} entries -> {args.output}")
        else:
            print(output)
    else:
        fieldnames = list(entries[0].keys()) if entries else []
        if args.output:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(entries)
            print(f"Wrote {len(entries)} rows -> {args.output}")
        else:
            import io
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(entries)
            print(buf.getvalue())


if __name__ == "__main__":
    main()
