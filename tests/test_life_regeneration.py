"""Deterministic wall-clock tests for the offline +1 life / 15 min rule."""
from pathlib import Path
import tempfile
import sqlite3
import unittest
from echo_game.storage import Storage


class FakeClock:
    def __init__(self,now=1_700_000_000.0):
        self.now=now
    def __call__(self):return self.now
    def advance(self,seconds):self.now+=seconds


class FreeLifeRegenerationTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/'echo.sqlite3'
        self.clock=FakeClock()
        self.store=Storage(self.path,clock=self.clock)

    def test_one_life_per_fifteen_minutes_exact_boundary(self):
        self.store.record_defeat()
        self.assertEqual(self.store.wallet()['lives'],2)
        self.clock.advance(899)
        self.assertEqual(self.store.wallet()['lives'],2)
        self.assertEqual(self.store.recovery_status()['next_life_in'],1)
        self.clock.advance(1)
        self.assertEqual(self.store.wallet()['lives'],3)
        self.assertIsNone(self.store.recovery_status()['next_life_in'])

    def test_when_zero_every_fifteen_minutes_awards_one_to_three(self):
        for _ in range(3):self.store.record_defeat()
        self.assertFalse(self.store.can_play())
        for expected in (1,2,3):
            self.clock.advance(900)
            self.assertEqual(self.store.wallet()['lives'],expected)
            self.assertTrue(self.store.can_play())
        self.clock.advance(6000)
        self.assertEqual(self.store.wallet()['lives'],3)

    def test_regeneration_does_not_reset_with_another_defeat(self):
        self.store.record_defeat()  # from 3 to 2, timer begins
        self.clock.advance(400)
        self.store.record_defeat()  # from 2 to 1, same timer continues
        self.clock.advance(500)
        self.assertEqual(self.store.wallet()['lives'],2)
        self.assertEqual(self.store.recovery_status()['next_life_in'],900)

    def test_multiple_periods_offline_are_settled_once_after_restart(self):
        for _ in range(3):self.store.record_defeat()
        self.clock.advance(1807)
        restored=Storage(self.path,clock=self.clock)
        self.assertEqual(restored.wallet()['lives'],2)
        self.assertEqual(restored.recovery_status()['next_life_in'],893)
        self.assertEqual(restored.wallet()['lives'],2)
        self.clock.advance(893)
        self.assertEqual(restored.wallet()['lives'],3)
        self.assertEqual(self.store.wallet()['lives'],3)

    def test_lives_and_timer_survive_clear_story_save(self):
        self.store.save({'level':2})
        for _ in range(3):self.store.record_defeat()
        self.clock.advance(540)
        self.store.clear()
        self.assertIsNone(self.store.load())
        self.assertFalse(self.store.can_play())
        self.assertEqual(self.store.recovery_status()['next_life_in'],360)
        self.clock.advance(360)
        self.assertEqual(self.store.wallet()['lives'],1)

    def test_purchased_lives_are_not_lost_and_free_timer_pauses(self):
        for _ in range(3):self.store.record_defeat()
        self.clock.advance(450)
        self.store.purchase_demo('lives_3')
        self.assertEqual(self.store.wallet()['lives'],3)
        self.clock.advance(4000)
        self.assertEqual(self.store.wallet()['lives'],3)
        self.store.purchase_demo('lives_3')
        self.assertEqual(self.store.wallet()['lives'],6)
        self.clock.advance(8000)
        self.assertEqual(self.store.wallet()['lives'],6)
        self.store.record_defeat() # 5
        self.store.record_defeat() # 4
        self.store.record_defeat() # 3
        self.assertIsNone(self.store.recovery_status()['next_life_in'])
        self.store.record_defeat() # 2 -> starts new free clock
        self.assertEqual(self.store.recovery_status()['next_life_in'],900)

    def test_premium_has_infinite_lives_without_cooldown(self):
        for _ in range(3):self.store.record_defeat()
        self.store.purchase_demo('premium_pass')
        self.clock.advance(9000)
        self.assertTrue(self.store.wallet()['unlimited'])
        self.assertIsNone(self.store.recovery_status()['next_life_in'])
        for _ in range(10):self.store.record_defeat()
        self.assertTrue(self.store.can_play())
        self.assertEqual(self.store.wallet()['lives'],0)

    def test_backward_clock_jump_safe_restarts_timer(self):
        self.store.record_defeat()
        self.clock.now-=3600
        self.assertEqual(self.store.wallet()['lives'],2)
        self.assertEqual(self.store.recovery_status()['next_life_in'],900)
        self.clock.advance(900)
        self.assertEqual(self.store.wallet()['lives'],3)

    def test_old_wallet_schema_migrates_without_overwriting_wallet(self):
        old_db=self.path.parent/'old.sqlite3'
        with sqlite3.connect(old_db) as db:
            db.execute('CREATE TABLE wallet(id INTEGER PRIMARY KEY, lives INTEGER, unlimited INTEGER, defeats INTEGER)')
            db.execute('INSERT INTO wallet VALUES (1,1,0,2)')
            db.execute('CREATE TABLE saves(id INTEGER PRIMARY KEY, snapshot TEXT, updated REAL)')
            db.execute('INSERT INTO saves VALUES (1,?,0)',('{"level":2}',))
        migrated=Storage(old_db,clock=self.clock)
        self.assertEqual(migrated.wallet()['lives'],1)
        self.assertEqual(migrated.load()['level'],2)
        self.assertEqual(migrated.recovery_status()['next_life_in'],900)
        self.clock.advance(900)
        self.assertEqual(migrated.wallet()['lives'],2)


if __name__=='__main__':unittest.main()
