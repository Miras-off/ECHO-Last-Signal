"""Logic tests: run with python -m unittest discover -s tests -v (no audio required)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from echo_game.commands import clean_text, interpret, vocabulary
from echo_game.world import CACHE, CORE, EXIT, GATE, TERMINAL, World
from echo_game import storage


class CommandTests(unittest.TestCase):
    def test_russian_phrase(self):
        self.assertEqual(interpret('Нова, открой дверь!'), 'open')

    def test_natural_hack_phrase(self):
        self.assertEqual(interpret('Пожалуйста, взломай терминал'), 'hack')

    def test_yot_normalisation(self):
        self.assertEqual(clean_text('ОтчЁТ, пожалуйста!'), 'отчет пожалуйста')
        self.assertEqual(interpret('Сделай отчёт'), 'status')

    def test_unknown_command(self):
        self.assertIsNone(interpret('Доброе утро, станция'))

    def test_empty_command(self):
        self.assertIsNone(interpret('...'))

    def test_vosk_grammar(self):
        vocab = vocabulary()
        self.assertIn('сканируй', vocab)
        self.assertIn('импульс', vocab)
        self.assertIn('[unk]', vocab)


class LevelTests(unittest.TestCase):
    def test_gate_blocks_passage_before_hack(self):
        w=World()
        self.assertFalse(w._free(8.5,5.5))
        self.assertTrue(w._free(7.5,5.5))

    def test_movement_respects_walls(self):
        w=World()
        w.player.x,w.player.y = 1.35,1.5
        for _ in range(30):
            w.step(.05,-1,0)
        self.assertGreater(w.player.x,1.27)

    def test_scan_requires_proximity(self):
        w=World()
        self.assertFalse(w.command('scan'))
        self.assertEqual(w.errors,1)
        self.assertFalse(w.revealed)

    def test_hack_requires_scan(self):
        w=World()
        w.player.x,w.player.y=TERMINAL
        self.assertFalse(w.command('hack'))
        self.assertFalse(w.hacked)

    def test_complete_puzzle_in_right_order(self):
        w=World()
        w.player.x,w.player.y=TERMINAL
        self.assertTrue(w.command('scan'))
        self.assertTrue(w.command('hack'))
        w.player.x,w.player.y=GATE
        self.assertTrue(w.command('open'))
        self.assertTrue(w._free(8.5,5.5))
        w.player.x,w.player.y=CORE
        self.assertTrue(w.command('activate'))
        self.assertEqual(w.progress,4)
        w.player.x,w.player.y=EXIT
        w.step(.016)
        self.assertEqual(w.status,'won')
        self.assertGreaterEqual(w.points,630)

    def test_open_gate_without_hack_fails(self):
        w=World()
        w.player.x,w.player.y=GATE
        self.assertFalse(w.command('open'))
        self.assertFalse(w.gate_open)

    def test_shield_costs_energy_and_prevents_damage(self):
        w=World()
        self.assertTrue(w.command('shield'))
        self.assertEqual(w.player.energy,75)
        w._damage(50,'danger')
        self.assertEqual(w.player.hp,100)

    def test_insufficient_energy(self):
        w=World()
        w.player.energy=10
        self.assertFalse(w.command('shield'))
        self.assertFalse(w.shielded)

    def test_help_guides_stages(self):
        w=World()
        self.assertTrue(w.command('help'))
        self.assertIn('Сканируй',w.message)
        w.revealed=True
        self.assertTrue(w.command('help'))
        self.assertIn('Взломай',w.message)

    def test_errors_change_difficulty(self):
        w=World()
        for _ in range(4):
            w.command('scan')
        self.assertLess(w.difficulty,1)

    def test_energy_cache_pickup_once(self):
        w=World()
        w.player.energy=25
        w.player.x,w.player.y=CACHE
        w.step(.01)
        self.assertTrue(w.cache_taken)
        score=w.points
        w.step(.01)
        self.assertEqual(w.points,score)

    def test_defeat(self):
        w=World()
        w.player.hp=10
        w._damage(18,'Drone')
        self.assertEqual(w.status,'lost')

    def test_storage_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage,'SAVE_DIR', Path(tmp)):
                storage.initialize()
                storage.save_run('won',700,69,4,1)
                storage.save_run('lost',0,29,1,2)
                result=storage.summary()
        self.assertEqual(result['runs'],2)
        self.assertEqual(result['wins'],1)
        self.assertEqual(result['best'],700)


if __name__=='__main__':
    unittest.main()
