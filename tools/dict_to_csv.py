"""
dict_to_csv.py
--------------
Flatten a possibly-nested list-of-dicts (like HARDWARE_DB) into a CSV.

Usage:
    python tools/dict_to_csv.py                       # defaults: reads HARDWARE_DB, writes hardware_db.csv
    python tools/dict_to_csv.py -o my_output.csv      # custom output path
"""

import argparse
import csv
import sys
import os

# allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def flatten(obj, parent_key="", sep="_"):
    """Recursively flatten a dict.  Nested keys become parent_child."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(flatten(v, new_key, sep))
            elif isinstance(v, list):
                # store lists as semicolon-joined strings
                items[new_key] = ";".join(str(i) for i in v)
            else:
                items[new_key] = v
    return items


def dicts_to_csv(records, output_path):
    """Write a list of (possibly nested) dicts to *output_path* as CSV."""
    flat = [flatten(r) for r in records]

    # union of all keys, preserving first-seen order
    fieldnames = []
    seen = set()
    for row in flat:
        for k in row:
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat)

    print(f"Wrote {len(flat)} rows x {len(fieldnames)} columns -> {output_path}")


def _extract_hardware_db():
    """Extract HARDWARE_DB from trash_collector.py without importing discord."""
    import ast, re

    src_path = os.path.join(os.path.dirname(__file__), "..", "cogs", "trash_collector.py")
    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Find the HARDWARE_DB = [ ... ] assignment via regex then parse the list literal
    match = re.search(r"^HARDWARE_DB\s*=\s*\[", source, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find HARDWARE_DB in trash_collector.py")

    # Walk forward from the match to find the balanced closing bracket
    start = match.start()
    depth = 0
    end = start
    for i in range(match.end() - 1, len(source)):
        if source[i] == "[":
            depth += 1
        elif source[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    literal = source[start + len("HARDWARE_DB"):end].strip()
    if literal.startswith("="):
        literal = literal[1:].strip()

    return ast.literal_eval(literal)


def main():
    parser = argparse.ArgumentParser(description="Export HARDWARE_DB to CSV")
    parser.add_argument("-o", "--output", default="hardware_db.csv",
                        help="Output CSV path (default: hardware_db.csv)")
    args = parser.parse_args()

    HARDWARE_DB = _extract_hardware_db()
    dicts_to_csv(HARDWARE_DB, args.output)


if __name__ == "__main__":
    main()
