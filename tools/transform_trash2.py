"""
One-shot script: transform trash2.csv to match trash.csv schema.

Adds/renames columns so the loader can treat both files identically:
  - Generates 'id' from name (slugified)
  - Renames 'category' -> 'type'
  - Parses 'power_draw' ("30 W", "20 MW", "900 kW") -> 'tdp_watts' (float)
  - Parses 'hashrate' ("5.0 PH/s", "0.003 MH/s") -> 'hashrate_mhs' (float, in MH/s)
  - Adds empty/default columns: chipset, clock_mhz, word_bits, cores, process_nm
  - Keeps: name, manufacturer, year, description, rarity, transistors
"""
import csv, os, re, unicodedata


def slugify(name: str) -> str:
    """Convert a hardware name to a snake_case id."""
    # Normalize unicode, strip non-ASCII
    s = unicodedata.normalize("NFKD", name)
    s = re.sub(r"[^\x20-\x7e]", "", s)  # strip non-ASCII
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)   # replace non-alnum with _
    s = s.strip("_")
    return s[:80]  # cap length


def parse_power_draw(val: str) -> float:
    """Convert '30 W', '20 MW', '900 kW' -> watts as float."""
    if not val or not val.strip():
        return 0.0
    val = re.sub(r"[^\d.a-zA-Z ]", "", val).strip()  # strip special chars
    m = re.match(r"([\d.]+)\s*(MW|kW|W)", val, re.IGNORECASE)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "MW":
        return num * 1_000_000
    elif unit == "KW":
        return num * 1_000
    return num


def parse_hashrate_to_mhs(val: str) -> float:
    """Convert '5.0 PH/s', '0.003 MH/s', '234.0 TH/s', '20.0 GH/s' -> MH/s."""
    if not val or not val.strip():
        return 0.0
    m = re.match(r"([\d.]+)\s*(PH/s|TH/s|GH/s|MH/s|KH/s|H/s)", val.strip(), re.IGNORECASE)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2).upper()
    multipliers = {
        "PH/S": 1e9,       # 1 PH = 1e9 MH
        "TH/S": 1e6,       # 1 TH = 1e6 MH
        "GH/S": 1e3,       # 1 GH = 1e3 MH
        "MH/S": 1.0,
        "KH/S": 1e-3,
        "H/S":  1e-6,
    }
    return num * multipliers.get(unit, 1.0)


# Target schema (same column order as trash.csv)
OUT_FIELDS = [
    "id", "name", "chipset", "manufacturer", "year",
    "clock_mhz", "word_bits", "cores", "type", "process_nm",
    "transistors", "description", "rarity", "tdp_watts", "hashrate_mhs",
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    in_path = os.path.normpath(os.path.join(here, "..", "trash2.csv"))
    out_path = in_path  # overwrite in place

    # Read
    with open(in_path, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))

    # Track duplicate IDs
    seen_ids = {}
    out_rows = []

    for row in rows:
        raw_id = "t2_" + slugify(row.get("name", "unknown"))
        # Deduplicate IDs
        if raw_id in seen_ids:
            seen_ids[raw_id] += 1
            raw_id = f"{raw_id}_{seen_ids[raw_id]}"
        else:
            seen_ids[raw_id] = 1

        # Handle both original format (power_draw/hashrate/category) and
        # already-transformed format (tdp_watts/hashrate_mhs/type)
        tdp_raw = row.get("power_draw", "") or row.get("tdp_watts", "0")
        hr_raw = row.get("hashrate", "") or row.get("hashrate_mhs", "0")
        # parse_power_draw handles "30 W" strings; plain numbers pass through
        tdp = parse_power_draw(tdp_raw) if not tdp_raw.replace(".", "").replace("-", "").isdigit() else float(tdp_raw or 0)
        hashrate = parse_hashrate_to_mhs(hr_raw) if not hr_raw.replace(".", "").replace("-", "").replace("e+", "").replace("e", "").isdigit() else float(hr_raw or 0)
        hw_type = row.get("category") or row.get("type") or "CPU"

        out = {
            "id": raw_id,
            "name": row.get("name", ""),
            "chipset": row.get("chipset", ""),
            "manufacturer": row.get("manufacturer", ""),
            "year": row.get("year", ""),
            "clock_mhz": row.get("clock_mhz", ""),
            "word_bits": row.get("word_bits", ""),
            "cores": row.get("cores", ""),
            "type": hw_type,
            "process_nm": row.get("process_nm", ""),
            "transistors": row.get("transistors", "0"),
            "description": row.get("description", ""),
            "rarity": row.get("rarity", "common"),
            "tdp_watts": tdp,
            "hashrate_mhs": hashrate,
        }
        out_rows.append(out)

    # Write
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    print(f"Transformed {len(out_rows)} rows.")
    print(f"Columns: {', '.join(OUT_FIELDS)}")

    # Quick sanity check
    sample_types = {}
    for r in out_rows:
        t = r["type"]
        sample_types[t] = sample_types.get(t, 0) + 1
    print(f"Type distribution: {sample_types}")


if __name__ == "__main__":
    main()
