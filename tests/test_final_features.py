import unittest
import tempfile
from pathlib import Path
from echo_game.world import World
from echo_game.adaptive import AdaptiveDirector

class FinalFeaturesTests(unittest.TestCase):
    def test_nine_puzzles_and_object_placement(self):
        for level in (1,2,3):
            w=World(level)
            self.assertEqual(len(w.puzzles),3)
            stations=[o for o in w.objects if o['type']=='puzzle']
            self.assertEqual(len(stations),3)
            for o in stations:
                self.assertIn(o['puzzle_id'],w.puzzles)
                self.assertFalse(w.collides(o['x'],o['y'],.01))

    def test_all_correct_answers_and_wrong_answer_raises_alert(self):
        for level in (1,2,3):
            w=World(level)
            for pid,p in w.puzzles.items():
                self.assertFalse(w.solve_puzzle(pid,(p['answer']+1)%3))
                self.assertTrue(w.solve_puzzle(pid,p['answer']))
                self.assertFalse(w.solve_puzzle(pid,p['answer']))
            self.assertEqual(len(w.solved_puzzles),3)
            self.assertGreater(w.alert,0)
            self.assertEqual(len(w.history),3)

    def test_saving_puzzles_and_notes(self):
        w=World(1);p=next(iter(w.puzzles.values()))
        w.solve_puzzle(p['id'],p['answer'])
        w.history.append('Архивная подсказка')
        snap=w.snapshot()
        new=World(1);new.restore(snap)
        self.assertEqual(new.solved_puzzles,w.solved_puzzles)
        self.assertIn('Архивная подсказка',new.history)
        self.assertEqual(new.score,w.score)

    def test_adaptive_learning_and_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'qtable.json'
            ai=AdaptiveDirector(path)
            factor,_=ai.advance({'damage':0,'errors':0,'detections':0},100,12)
            self.assertGreater(factor,1)
            ai.advance({'damage':30,'errors':1,'detections':2},69,34)
            self.assertEqual(ai.updates,1)
            self.assertTrue(path.exists())
            again=AdaptiveDirector(path)
            self.assertEqual(again.updates,1)
            self.assertEqual(set(again.q),set(ai.q))

    def test_ability_lock_remains_working(self):
        w=World(2)
        self.assertFalse(w.command('hack'))
        self.assertFalse(w.command('pulse'))

if __name__=='__main__': unittest.main()
