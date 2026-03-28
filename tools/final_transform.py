"""
One-shot: read original trash3..csv, add transistors + transform columns,
write final trash2.csv matching trash.csv schema.

Input:  name,manufacturer,category,year,hashrate,power_draw,rarity,description
Output: id,name,chipset,manufacturer,year,clock_mhz,word_bits,cores,type,
        process_nm,transistors,description,rarity,tdp_watts,hashrate_mhs
"""
import csv, os, re, unicodedata, sys

# ── Import transistor lookup from add_transistors.py ─────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_transistors import TRANSISTORS, _normalize

# Pre-compute sorted keys (longest first) with normalized forms
_SORTED_KEYS = sorted(TRANSISTORS.keys(), key=len, reverse=True)
_NORM_KEYS = [(_normalize(k), k) for k in _SORTED_KEYS]


def find_transistors(name: str) -> int:
    name_norm = _normalize(name)
    for norm_key, orig_key in _NORM_KEYS:
        if norm_key in name_norm:
            return TRANSISTORS[orig_key]
    return 0


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = re.sub(r"[^\x20-\x7e]", "", s)
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:80]


def parse_power_draw(val: str) -> float:
    """'30 W' -> 30.0, '20 MW' -> 20000000.0, '900 kW' -> 900000.0"""
    if not val or not val.strip():
        return 0.0
    val = re.sub(r"[^\d.a-zA-Z ]", "", val).strip()
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


def parse_hashrate(val: str) -> float:
    """'5.0 PH/s' -> MH/s float"""
    if not val or not val.strip():
        return 0.0
    m = re.match(r"([\d.]+)\s*(PH/s|TH/s|GH/s|MH/s|KH/s|H/s)",
                 val.strip(), re.IGNORECASE)
    if not m:
        return 0.0
    num = float(m.group(1))
    mult = {"PH/S": 1e9, "TH/S": 1e6, "GH/S": 1e3,
            "MH/S": 1.0, "KH/S": 1e-3, "H/S": 1e-6}
    return num * mult.get(m.group(2).upper(), 1.0)


OUT_FIELDS = [
    "id", "name", "chipset", "manufacturer", "year",
    "clock_mhz", "word_bits", "cores", "type", "process_nm",
    "transistors", "description", "rarity", "tdp_watts", "hashrate_mhs",
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.normpath(os.path.join(here, "..", "trash3..csv"))
    dst = os.path.normpath(os.path.join(here, "..", "trash2.csv"))

    with open(src, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))

    seen_ids = {}
    out_rows = []
    unmatched_trans = []

    for row in rows:
        name = row.get("name", "unknown")

        # ID with t2_ prefix to avoid collisions with trash.csv
        raw_id = "t2_" + slugify(name)
        if raw_id in seen_ids:
            seen_ids[raw_id] += 1
            raw_id = f"{raw_id}_{seen_ids[raw_id]}"
        else:
            seen_ids[raw_id] = 1

        hw_type = row.get("category", "CPU").strip()
        tdp = parse_power_draw(row.get("power_draw", ""))
        hashrate = parse_hashrate(row.get("hashrate", ""))
        transistors = find_transistors(name)

        if transistors == 0 and hw_type not in ("DATACENTER", "ARRAY"):
            unmatched_trans.append(f"  [{hw_type}] {name}")

        out = {
            "id": raw_id,
            "name": name,
            "chipset": "",
            "manufacturer": row.get("manufacturer", ""),
            "year": row.get("year", ""),
            "clock_mhz": "",
            "word_bits": "",
            "cores": "",
            "type": hw_type,
            "process_nm": "",
            "transistors": transistors,
            "description": row.get("description", ""),
            "rarity": row.get("rarity", "common"),
            "tdp_watts": tdp,
            "hashrate_mhs": hashrate,
        }
        out_rows.append(out)

    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    # Stats
    types = {}
    for r in out_rows:
        types[r["type"]] = types.get(r["type"], 0) + 1

    print(f"Wrote {len(out_rows)} rows to {dst}")
    print(f"Type distribution: {types}")
    print(f"Unmatched transistors: {len(unmatched_trans)}")
    if unmatched_trans:
        for u in unmatched_trans[:10]:
            print(u.encode("ascii", "replace").decode("ascii"))

    # Spot checks
    for r in out_rows:
        if "RTX 4090" in r["name"]:
            print(f"\nSpot: {r['name']} | type={r['type']} tdp={r['tdp_watts']} hr={r['hashrate_mhs']} trans={r['transistors']}")
            break
    for r in out_rows:
        if "Antminer S21 Pro" in r["name"]:
            print(f"Spot: {r['name']} | type={r['type']} tdp={r['tdp_watts']} hr={r['hashrate_mhs']} trans={r['transistors']}")
            break
    for r in out_rows:
        if "West Texas Wind" in r["name"]:
            print(f"Spot: {r['name']} | type={r['type']} tdp={r['tdp_watts']} hr={r['hashrate_mhs']} trans={r['transistors']}")
            break


if __name__ == "__main__":
    main()
