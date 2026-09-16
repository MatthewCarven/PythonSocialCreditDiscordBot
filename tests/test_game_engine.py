"""Tests for the pure game logic in game_engine.py.

game_engine.py and mining_db.py are synced to Python Trash Colllector 2,
so these tests guard two projects at once.
"""
import math
import random
import time

import pytest

import game_engine as ge


# ---------------------------------------------------------------------------
# era_bonus
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year,bonus", [
    (1970, 5.0), (1974, 5.0),
    (1975, 4.0), (1984, 4.0),
    (1985, 3.0), (1994, 3.0),
    (1995, 2.0), (2004, 2.0),
    (2005, 1.5), (2014, 1.5),
    (2015, 1.0), (2024, 1.0),
])
def test_era_bonus_boundaries(year, bonus):
    assert ge.era_bonus(year) == bonus


# ---------------------------------------------------------------------------
# compute_score
# ---------------------------------------------------------------------------
# "XTYPE" is deliberately absent from TYPE_MULTIPLIERS/TYPE_SCORE_BOOST so the
# type multiplier is 1.0 and the arithmetic is easy to follow. Year 2020 makes
# the era bonus 1.0.

def test_compute_score_compute_path():
    hw = {"type": "XTYPE", "year": 2020, "clock_mhz": 100, "word_bits": 32, "cores": 2}
    # clock * (bits/8) * cores = 100 * 4 * 2
    assert ge.compute_score(hw) == 800.0


def test_compute_score_missing_word_bits_assumes_8_bit():
    base = {"type": "XTYPE", "year": 2020, "clock_mhz": 100, "cores": 2}
    explicit = dict(base, word_bits=8)
    assert ge.compute_score(base) == ge.compute_score(explicit)


def test_compute_score_missing_cores_assumes_single_core():
    base = {"type": "XTYPE", "year": 2020, "clock_mhz": 100, "word_bits": 8}
    explicit = dict(base, cores=1)
    assert ge.compute_score(base) == ge.compute_score(explicit)


def test_compute_score_hashrate_path():
    hw = {"type": "XTYPE", "year": 2020, "hashrate_mhs": 1_000_000}  # 1 TH/s
    # sqrt(1 TH/s) * 2000
    assert ge.compute_score(hw) == 2000.0


def test_compute_score_hashrate_path_ignores_compute_fields():
    with_clock = {"type": "XTYPE", "year": 2020, "hashrate_mhs": 1_000_000,
                  "clock_mhz": 999, "cores": 64}
    without = {"type": "XTYPE", "year": 2020, "hashrate_mhs": 1_000_000}
    assert ge.compute_score(with_clock) == ge.compute_score(without)


def test_compute_score_transistor_bonus_capped():
    base = {"type": "XTYPE", "year": 2020, "clock_mhz": 100, "word_bits": 8, "cores": 1}
    at_cap = dict(base, transistors=50_000_000_000)
    beyond = dict(base, transistors=1_000_000_000_000)
    assert ge.compute_score(at_cap) == ge.compute_score(beyond)  # hard cap at 3.5x
    assert ge.compute_score(at_cap) == pytest.approx(100 * 3.5)


def test_compute_score_never_zero():
    assert ge.compute_score({}) > 0


def test_compute_score_all_hardware_rows():
    """Every row in the shipped CSVs must produce a positive finite score.
    This is the regression net for hand-edits to trash.csv / trash2.csv."""
    for hw in ge.HARDWARE_DB:
        score = ge.compute_score(hw)
        assert math.isfinite(score) and score > 0, f"bad score for {hw.get('id')}"


# ---------------------------------------------------------------------------
# Hardware database integrity
# ---------------------------------------------------------------------------

def test_hardware_db_loaded():
    assert len(ge.HARDWARE_DB) >= 1500


def test_hardware_ids_unique():
    # A duplicate id would silently shadow a row in HARDWARE_LOOKUP.
    assert len(ge.HARDWARE_LOOKUP) == len(ge.HARDWARE_DB)


def test_hardware_required_fields():
    for hw in ge.HARDWARE_DB:
        for field in ("id", "name", "type"):
            assert str(hw.get(field, "")).strip(), f"row missing {field}: {hw}"
        assert hw.get("rarity") in ge.RARITY_ORDER, f"{hw['id']}: bad rarity {hw.get('rarity')!r}"


def test_random_finds_come_from_db():
    finds = ge.random_finds(5)
    assert len(finds) == 5
    for hw in finds:
        assert hw["id"] in ge.HARDWARE_LOOKUP


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("1 th/s", 1_000_000.0),
    ("1 TH/s", 1_000_000.0),
    ("500", 500.0),          # bare float = already MH/s
    ("", 0.0),
    (None, 0.0),
    ("5-10 gh/s", 7_500.0),  # range takes the midpoint
])
def test_parse_hashrate(raw, expected):
    assert ge._parse_hashrate(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("3,300", 3300.0),
    ("10 000", 10000.0),
    ("2.4 billion", 2.4e9),
    ("5 million", 5e6),
    ("5-10", 7.5),
    ("95 W", 95.0),
    ("~7", 7.0),
    ("", 0.0),
])
def test_parse_numeric(raw, expected):
    assert ge._parse_numeric(raw) == expected


# ---------------------------------------------------------------------------
# Rig multipliers
# ---------------------------------------------------------------------------

def _parts(*types, rarity="common"):
    return [{"type": t, "rarity": rarity} for t in types]


def test_diversity_multiplier():
    assert ge.diversity_multiplier(_parts("CPU")) == 1.00
    assert ge.diversity_multiplier(_parts("CPU", "CPU", "CPU")) == 1.00
    assert ge.diversity_multiplier(_parts("CPU", "GPU", "DSP")) == 1.60
    # More unique types than the table has keys -> capped at the top bonus
    assert ge.diversity_multiplier(_parts("A", "B", "C", "D", "E", "F")) == 2.50


@pytest.mark.parametrize("n,mult", [(0, 1.0), (1, 5.0), (2, 7.0), (3, 8.0), (5, 8.75)])
def test_legendary_multiplier(n, mult):
    parts = [{"rarity": "legendary"}] * n + [{"rarity": "common"}] * (5 - n)
    assert ge.legendary_multiplier(parts) == mult


def test_combo_requires_fpga():
    assert ge.combo_multiplier(_parts("CPU", "GPU", "ASIC", "TPU")) == (1.0, "", "")
    assert ge.combo_multiplier(_parts("FPGA")) == (1.0, "", "")


def test_combo_tiers():
    mult, name, _ = ge.combo_multiplier(_parts("FPGA", "CPU"))
    assert (mult, name) == (1.20, "FPGA-CPU Cluster")
    mult, name, _ = ge.combo_multiplier(_parts("FPGA", "CPU", "GPU"))
    assert (mult, name) == (1.75, "Hybrid Hypervisor Stack")
    mult, name, _ = ge.combo_multiplier(_parts("FPGA", "CPU", "GPU", "ASIC", "TPU"))
    assert (mult, name) == (4.0, "C-137 Stack")


def test_combo_types_case_insensitive():
    mult, name, _ = ge.combo_multiplier(_parts("fpga", "cpu"))
    assert (mult, name) == (1.20, "FPGA-CPU Cluster")


# ---------------------------------------------------------------------------
# BTC market
# ---------------------------------------------------------------------------

def test_update_btc_price_no_time_elapsed():
    assert ge.update_btc_price(42.0, time.time()) == 42.0


def test_update_btc_price_reverts_to_given_base():
    """With a 50-credit base (the Discord economy), a week of updates must
    keep the price in a sane band near the base — not rail to the clamp."""
    random.seed(1337)
    week_ago = time.time() - 168 * 3600
    price = ge.update_btc_price(500.0, week_ago, 50.0)
    assert ge.BTC_MIN_PRICE <= price <= ge.BTC_MAX_PRICE
    assert price < 200.0, "price should revert toward the 50-credit base"


def test_update_btc_price_default_base_rails_to_ceiling():
    """Documents the module-default behavior: the standalone's 50k base is
    far above BTC_MAX_PRICE, so the price pins at the ceiling. If this test
    ever fails, the standalone economy constants were rescaled — check that
    the Discord cog still passes its own base."""
    random.seed(1337)
    week_ago = time.time() - 168 * 3600
    assert ge.update_btc_price(50.0, week_ago) == ge.BTC_MAX_PRICE


# ---------------------------------------------------------------------------
# Permits & recycling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,tier", [
    (0, 0), (99_999_999, 0),
    (100_000_000, 1), (999_999_999, 1),
    (1_000_000_000, 2),
    (50_000_000_000, 3),
    (500_000_000_000, 4), (10**15, 4),
])
def test_assess_permit_tier(score, tier):
    info = ge.assess_permit_tier(score)
    assert info["tier"] == tier
    assert info["cprm_rate"] <= 0.25


def test_recycle_yield_scales():
    small = ge.recycle_yield({"rarity": "common", "tdp_watts": 10})
    big = ge.recycle_yield({"rarity": "legendary", "tdp_watts": 300})
    assert big["gold"] > small["gold"]
    assert big["copper"] > small["copper"]
    assert big["aluminium"] > small["aluminium"]
    assert small["pcb"] == big["pcb"] == 20.0
    for v in {**small, **big}.values():
        assert v > 0
