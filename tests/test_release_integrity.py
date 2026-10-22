"""Static release checks that do not require SDL/audio hardware."""
import json, unittest, xml.etree.ElementTree as ET
from pathlib import Path
from echo_game.world import World,ROOT

class ReleaseIntegrityTests(unittest.TestCase):
    def test_puzzle_access_before_after_gates(self):
        for level in (1,2,3):
            w=World(level)
            puzzles={o['puzzle_id']:o for o in w.objects if o['type']=='puzzle'}
            start=(w.player.x,w.player.y)
            for key in (f'{level}A',f'{level}B'):
                self.assertTrue(w.pathfind(start,(puzzles[key]['x'],puzzles[key]['y'])))
            c=puzzles[f'{level}C']
            self.assertFalse(w.pathfind(start,(c['x'],c['y'])))
            w.gates['A']=True
            self.assertTrue(w.pathfind(start,(c['x'],c['y'])))

    def test_all_svg_assets_are_valid(self):
        for p in (ROOT/'assets'/'source_svg').glob('*.svg'):
            with self.subTest(asset=p.name):ET.parse(p)

    def test_puzzle_stations_have_unique_ids(self):
        for level in (1,2,3):
            w=World(level)
            ids=[o['puzzle_id'] for o in w.objects if o['type']=='puzzle']
            self.assertEqual(len(ids),len(set(ids)))
            self.assertEqual(set(ids),set(w.puzzles))

if __name__=='__main__': unittest.main()
