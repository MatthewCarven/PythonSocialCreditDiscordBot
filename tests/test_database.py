"""Tests for CreditDB against a throwaway SQLite file."""
import time

import pytest

from database import CreditDB

U, G = 1, 2


@pytest.fixture()
def db(tmp_path):
    return CreditDB(str(tmp_path / "social_credit.db"))


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------

def test_credit_defaults_to_zero(db):
    assert db.get_credit(U, G) == 0.0


def test_update_credit_upserts_and_accumulates(db):
    db.update_credit(U, G, 5.0)
    db.update_credit(U, G, -1.5)
    assert db.get_credit(U, G) == pytest.approx(3.5)


def test_credit_is_per_guild(db):
    db.update_credit(U, G, 5.0)
    assert db.get_credit(U, G + 1) == 0.0


def test_reset_score(db):
    db.update_credit(U, G, 42.0)
    db.reset_score(U, G)
    assert db.get_credit(U, G) == 0.0


def test_leaderboard_orders_and_splits(db):
    for uid, score in [(1, 10.0), (2, 50.0), (3, -5.0), (4, 0.5)]:
        db.update_credit(uid, G, score)
    top, bottom = db.get_leaderboard(G)
    assert [u for u, _ in top][:2] == [2, 1], "descending by score"
    assert [u for u, _ in bottom] == [3], "only negative scores in the bottom list"


# ---------------------------------------------------------------------------
# Slush fund
# ---------------------------------------------------------------------------

def test_slush_fund_accumulates(db):
    assert db.get_slush_fund(G) == 0.0
    db.add_to_slush_fund(G, 2.0)
    db.add_to_slush_fund(G, 3.0)
    assert db.get_slush_fund(G) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Banned / praised words
# ---------------------------------------------------------------------------

def test_banned_words_round_trip(db):
    db.add_banned_word(G, "Bourgeoisie", -2.0)
    assert db.get_banned_words(G) == [("bourgeoisie", -2.0)], "stored lowercased"
    assert db.remove_banned_word(G, "BOURGEOISIE") is True
    assert db.get_banned_words(G) == []
    assert db.remove_banned_word(G, "bourgeoisie") is False, "already gone"


def test_praised_words_round_trip(db):
    db.add_praised_word(G, "Glorious", 1.5)
    assert db.get_praised_words(G) == [("glorious", 1.5)]
    assert db.remove_praised_word(G, "glorious") is True


# ---------------------------------------------------------------------------
# Guild settings
# ---------------------------------------------------------------------------

def test_output_channel_round_trip(db):
    assert db.get_output_channel(G) is None
    db.set_output_channel(G, 12345)
    assert db.get_output_channel(G) == 12345


def test_output_channel_does_not_clobber_slush_fund(db):
    db.add_to_slush_fund(G, 7.0)
    db.set_output_channel(G, 12345)
    assert db.get_slush_fund(G) == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# Lottery
# ---------------------------------------------------------------------------

def test_lottery_tickets(db):
    db.add_lottery_tickets(G, U, 3)
    db.add_lottery_tickets(G, U + 1, 1)
    assert db.count_lottery_tickets(G) == 4
    assert db.get_user_ticket_count(G, U) == 3
    assert sorted(db.get_all_lottery_entries(G)) == [U, U, U, U + 1]
    db.clear_lottery_tickets(G)
    assert db.count_lottery_tickets(G) == 0


# ---------------------------------------------------------------------------
# Persistent command cooldowns
# ---------------------------------------------------------------------------

def test_command_cooldowns(db):
    assert db.get_cooldown(U, G, "work") == 0.0
    db.set_cooldown(U, G, "work")
    assert abs(db.get_cooldown(U, G, "work") - time.time()) < 2
    assert db.get_cooldown(U, G, "heist") == 0.0, "per-command isolation"
    assert db.get_cooldown(U + 1, G, "work") == 0.0, "per-user isolation"


def test_command_cooldowns_survive_reconnect(db, tmp_path):
    db.set_cooldown(U, G, "work")
    db2 = CreditDB(str(tmp_path / "social_credit.db"))
    assert db2.get_cooldown(U, G, "work") > 0
