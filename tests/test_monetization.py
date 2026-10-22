"""Monetization regression tests (standalone and GUI controller without SDL)."""
import tempfile, unittest, types, sys, importlib.util
from pathlib import Path
from collections import defaultdict
from unittest.mock import patch
from echo_game.storage import Storage

BASE=Path(__file__).resolve().parents[1]

class WalletTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'echo.sqlite3'
        self.store=Storage(self.path)

    def test_initial_three_attempts_and_persisted_defeats(self):
        self.assertEqual(self.store.wallet(),{'lives':3,'unlimited':False,'defeats':0})
        for expected in (2,1,0):
            self.assertEqual(self.store.record_defeat()['lives'],expected)
            self.assertEqual(Storage(self.path).wallet()['lives'],expected)
        self.assertFalse(self.store.can_play())
        self.assertEqual(self.store.record_defeat()['lives'],0)

    def test_demo_purchase_restores_three_attempts_with_receipt(self):
        for _ in range(3):self.store.record_defeat()
        self.assertFalse(self.store.can_play())
        receipt=self.store.purchase_demo('lives_3')
        self.assertTrue(receipt['receipt'].startswith('ECHO-DEMO-'))
        self.assertEqual(receipt['price_kzt'],490)
        self.assertEqual(Storage(self.path).wallet()['lives'],3)
        self.assertTrue(self.store.can_play())
        self.assertEqual(len(self.store.demo_purchases()),1)
        self.store.record_defeat()
        self.assertEqual(self.store.wallet()['lives'],2)

    def test_premium_pass_unlocks_challenge_and_infinite_lives(self):
        for _ in range(3):self.store.record_defeat()
        self.store.purchase_demo('premium_pass')
        self.assertTrue(self.store.wallet()['unlimited'])
        self.assertTrue(self.store.has_unlock('premium_challenge'))
        for _ in range(11):self.store.record_defeat()
        self.assertTrue(self.store.can_play())
        self.assertTrue(Storage(self.path).wallet()['unlimited'])
        self.assertEqual(len(self.store.demo_purchases()),1)

    def test_progress_reset_does_not_refill_wallet(self):
        self.store.save({'level':2})
        for _ in range(3):self.store.record_defeat()
        self.store.clear()
        self.assertIsNone(self.store.load())
        self.assertEqual(self.store.wallet()['lives'],0)
        self.assertFalse(Storage(self.path).can_play())

    def test_invalid_product_no_credit_and_no_records(self):
        with self.assertRaises(ValueError):self.store.purchase_demo('free_restore')
        self.assertEqual(self.store.wallet()['lives'],3)
        self.assertFalse(self.store.demo_purchases())

    def test_old_database_migrates_without_losing_saves_or_premium(self):
        import sqlite3
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM wallet')
            db.execute("INSERT INTO unlocks(name,value) VALUES('premium_challenge',1)")
            db.execute("INSERT INTO saves(id,snapshot,updated) VALUES(1,?,0)",('{"level": 2}',))
        migrated=Storage(self.path)
        self.assertEqual(migrated.wallet()['lives'],3)
        self.assertEqual(migrated.load(),{'level':2})
        self.assertTrue(migrated.has_unlock('premium_challenge'))
        self.assertFalse(migrated.wallet()['unlimited'])

class GameControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame=types.ModuleType('pygame')
        keys=['K_d','K_RIGHT','K_a','K_LEFT','K_s','K_DOWN','K_w','K_UP','K_LSHIFT','K_RSHIFT']
        for i,key in enumerate(keys):setattr(pygame,key,i)
        pygame.key=types.SimpleNamespace(get_pressed=lambda:defaultdict(bool))
        pygame.error=RuntimeError
        spec=importlib.util.spec_from_file_location('echo_game._economy_game',BASE/'echo_game'/'game.py')
        game=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'pygame':pygame}):spec.loader.exec_module(game)
        cls.Game=game.Game

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store=Storage(Path(self.folder.name)/'game.sqlite3')
        self.game=self.Game.__new__(self.Game)
        g=self.game
        g.storage=self.store;g.world=None;g.mode='menu';g.total_score=0
        g.sound_log_counter=0;g.last_alert_level=0;g.last_combat_audio_id=0
        g.camera_warning_ids=set();g.previous_drone_states={};g.turret_armed=False
        g.loss_accounted=False;g.payment_product=None;g.payment_origin='store';g.payment_receipt=None
        g.sound=lambda *args,**kw:None
        g.read_voice=lambda:None
        g.audio_events=lambda:None
        g.audio=types.SimpleNamespace(update=lambda *args,**kw:None)

    def defeat_once(self):
        g=self.game
        self.assertEqual(g.mode,'play')
        g.world.step=lambda *args,**kwargs:setattr(g.world,'status','lost')
        g.world.is_portal_tile=lambda *args:True
        g.tick(.02)
        self.assertEqual(g.mode,'result')
        # Another frame/result page cannot consume another life.
        g.tick(.02)

    def test_three_real_game_losses_then_lockout_and_payment(self):
        g=self.game
        self.assertIsNone(g.start())
        for idx in range(3):
            self.defeat_once()
            self.assertEqual(self.store.wallet()['lives'],2-idx)
            if idx<2:g.result_next()
        self.assertFalse(self.store.can_play())
        g.result_next()
        self.assertEqual(g.mode,'locked')
        self.assertFalse(g.start())
        self.assertEqual(g.mode,'locked')
        self.assertEqual(self.store.wallet()['lives'],0)
        g.begin_payment('lives_3','locked')
        self.assertEqual(g.mode,'payment')
        self.assertEqual(self.store.wallet()['lives'],0)  # no credit before confirmation
        g.finish_payment()
        self.assertEqual(g.mode,'receipt')
        self.assertEqual(self.store.wallet()['lives'],3)
        g.close_receipt()
        self.assertEqual(g.mode,'menu')
        g.start()
        self.assertEqual(g.mode,'play')

    def test_premium_allows_retry_without_charge(self):
        g=self.game;g.start()
        for idx in range(3):
            self.defeat_once()
            if idx<2:g.result_next()
        g.begin_payment('premium_pass','result')
        g.finish_payment();g.close_receipt()
        self.assertEqual(g.mode,'result')
        for _ in range(3):
            g.result_next();self.defeat_once()
        self.assertTrue(self.store.can_play())
        self.assertTrue(self.store.wallet()['unlimited'])

if __name__=='__main__':unittest.main()
