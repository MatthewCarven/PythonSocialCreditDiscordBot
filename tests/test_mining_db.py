"""Tests for MiningDB against a throwaway SQLite file."""
import time

import pytest

from mining_db import MiningDB

U, G = 1, 2  # test user / guild


@pytest.fixture()
def mdb(tmp_path):
    return MiningDB(str(tmp_path / "mining.db"))


def _stock_inventory(mdb, n=3):
    for i in range(n):
        mdb.add_hardware(U, G, f"hw_{i}")
    return [row[0] for row in mdb.get_inventory(U, G)]


# ---------------------------------------------------------------------------
# Atomic bulk sale — the dupe-exploit guard
# ---------------------------------------------------------------------------

def test_sell_hardware_bulk_happy_path(mdb):
    ids = _stock_inventory(mdb, 3)
    sold = mdb.sell_hardware_bulk(ids, U, G, 0.5)
    assert sold == 3
    assert mdb.get_btc_balance(U, G) == pytest.approx(0.5)
    assert mdb.get_inventory(U, G) == []


def test_sell_hardware_bulk_replay_pays_nothing(mdb):
    """Selling the same ids twice must not mint BTC the second time."""
    ids = _stock_inventory(mdb, 3)
    assert mdb.sell_hardware_bulk(ids, U, G, 0.5) == 3
    assert mdb.sell_hardware_bulk(ids, U, G, 0.5) is None
    assert mdb.get_btc_balance(U, G) == pytest.approx(0.5)


def test_sell_hardware_bulk_aborts_on_partial_match(mdb):
    """If any quoted part vanished, the whole sale must roll back."""
    ids = _stock_inventory(mdb, 3)
    mdb.remove_hardware_bulk(ids[:1], U, G)  # one part disappears pre-confirm
    assert mdb.sell_hardware_bulk(ids, U, G, 0.5) is None
    assert mdb.get_btc_balance(U, G) == 0.0
    assert len(mdb.get_inventory(U, G)) == 2, "surviving parts must not be deleted"


def test_sell_hardware_bulk_empty_list(mdb):
    assert mdb.sell_hardware_bulk([], U, G, 1.0) is None
    assert mdb.get_btc_balance(U, G) == 0.0


def test_sell_hardware_bulk_other_users_parts_abort(mdb):
    ids = _stock_inventory(mdb, 2)
    assert mdb.sell_hardware_bulk(ids, U + 1, G, 9.9) is None, "wrong owner"
    assert mdb.get_btc_balance(U + 1, G) == 0.0
    assert len(mdb.get_inventory(U, G)) == 2


# ---------------------------------------------------------------------------
# BTC wallet
# ---------------------------------------------------------------------------

def test_add_btc_upserts(mdb):
    mdb.add_btc(U, G, 1.0)
    mdb.add_btc(U, G, 0.25)
    assert mdb.get_btc_balance(U, G) == pytest.approx(1.25)


def test_remove_btc_sufficient(mdb):
    mdb.add_btc(U, G, 1.0)
    assert mdb.remove_btc(U, G, 0.4) is True
    assert mdb.get_btc_balance(U, G) == pytest.approx(0.6)


def test_remove_btc_overdraw_refused(mdb):
    mdb.add_btc(U, G, 0.3)
    assert mdb.remove_btc(U, G, 0.5) is False
    assert mdb.get_btc_balance(U, G) == pytest.approx(0.3)


def test_remove_btc_no_wallet(mdb):
    assert mdb.remove_btc(U, G, 0.1) is False


# ---------------------------------------------------------------------------
# Rig lifecycle
# ---------------------------------------------------------------------------

def test_create_and_scrap_rig_round_trip(mdb):
    inv_ids = _stock_inventory(mdb, 3)
    rig_id = mdb.create_rig(U, G, "Test Rig", inv_ids)
    assert mdb.get_inventory(U, G) == [], "building consumes the parts"

    hw_ids = mdb.scrap_rig(rig_id, U, G)
    assert sorted(hw_ids) == ["hw_0", "hw_1", "hw_2"]
    assert len(mdb.get_inventory(U, G)) == 3, "scrapping returns the parts"
    assert mdb.get_rigs(U, G) == []


def test_scrap_rig_wrong_owner(mdb):
    inv_ids = _stock_inventory(mdb, 3)
    rig_id = mdb.create_rig(U, G, "Test Rig", inv_ids)
    assert mdb.scrap_rig(rig_id, U + 1, G) is None
    assert len(mdb.get_rigs(U, G)) == 1


def test_scrap_rig_twice(mdb):
    inv_ids = _stock_inventory(mdb, 3)
    rig_id = mdb.create_rig(U, G, "Test Rig", inv_ids)
    assert mdb.scrap_rig(rig_id, U, G) is not None
    assert mdb.scrap_rig(rig_id, U, G) is None, "second scrap must no-op"
    assert len(mdb.get_inventory(U, G)) == 3, "parts must not duplicate"


# ---------------------------------------------------------------------------
# Cooldowns & market price storage
# ---------------------------------------------------------------------------

def test_cooldowns_persist_per_command(mdb):
    assert mdb.get_cooldown(U, G, "scavenge") == 0.0
    mdb.set_cooldown(U, G, "scavenge")
    assert abs(mdb.get_cooldown(U, G, "scavenge") - time.time()) < 2
    assert mdb.get_cooldown(U, G, "mine") == 0.0


def test_btc_price_seed_and_update(mdb):
    price, _ = mdb.get_btc_price(G)
    assert price == 50.0, "unseeded market starts at the 50-credit base"
    mdb.set_btc_price(G, 61.5)
    price, _ = mdb.get_btc_price(G)
    assert price == 61.5
