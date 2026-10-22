"""Room-only visibility regression checks for the three editable Tiled maps."""
import unittest
from echo_game.world import World


class RoomVisibilityTests(unittest.TestCase):
    def test_room_separation_and_doorway_transition(self):
        for level in (1, 2, 3):
            with self.subTest(level=level):
                w = World(level)
                candidate = None
                for y in range(1, w.height - 1):
                    for x in range(1, w.width - 1):
                        if not w.is_portal_tile(x, y):
                            continue
                        neighbors = [(nx, ny) for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                                     if w.is_walkable_tile(nx, ny) and not w.is_portal_tile(nx, ny)]
                        if len(neighbors) < 2:
                            continue
                        a, b = neighbors[0], neighbors[-1]
                        if b not in w.room_tiles(a[0] + .5, a[1] + .5):
                            candidate = (a, (x, y), b)
                            break
                    if candidate:
                        break
                self.assertIsNotNone(candidate)
                a, doorway, b = candidate
                w.player.x, w.player.y = a[0] + .5, a[1] + .5
                original_room = w.room_tiles()
                self.assertIn(a, original_room)
                self.assertNotIn(b, original_room)
                w.player.x, w.player.y = doorway[0] + .5, doorway[1] + .5
                door_room = w.room_tiles()
                self.assertIn(a, door_room)
                self.assertNotIn(b, door_room)
                w.player.x, w.player.y = b[0] + .5, b[1] + .5
                new_room = w.room_tiles()
                self.assertIn(b, new_room)
                self.assertNotIn(a, new_room)
                self.assertGreater(len(new_room), 4)

    def test_room_view_includes_bounded_doorway_preview(self):
        for level in (1, 2, 3):
            with self.subTest(level=level):
                w = World(level)
                base = w.room_tiles()
                first_step = w.room_preview_tiles(base, depth=1)
                preview = w.room_preview_tiles(base, depth=3)
                view = w.room_view_tiles()
                self.assertTrue(first_step)
                self.assertTrue(first_step.issubset(preview))
                self.assertTrue(base.isdisjoint(preview))
                self.assertTrue(all(w.is_walkable_tile(*cell) for cell in preview))
                self.assertTrue((base | preview).issubset(view))
                self.assertTrue(any(not w.is_walkable_tile(*cell) for cell in view))
                seeds = list(first_step)
                self.assertTrue(all(min(abs(x-sx)+abs(y-sy) for sx,sy in seeds) <= 2 for x,y in preview))
                self.assertLess(len(preview), len(base))

    def test_closed_gate_does_not_leak_preview(self):
        w = World(1)
        gate = next(o for o in w.objects if o['type'] == 'gate' and o['gate_id'] == 'A')
        gate_cell = (int(gate['x']), int(gate['y']))
        self.assertFalse(w.is_walkable_tile(*gate_cell))
        self.assertNotIn(gate_cell, w.room_preview_tiles())
        w.gates['A'] = True
        self.assertTrue(w.is_walkable_tile(*gate_cell))

    def test_tiny_connector_keeps_previous_room_visible(self):
        w = World(1)
        w.player.x,w.player.y = 9.5,25.5
        original = w.room_tiles()
        self.assertIn((9,25), original)
        for x,y in ((10.5,25.5),(11.5,25.5),(12.5,25.5)):
            w.player.x,w.player.y = x,y
            transition = w.room_tiles()
            self.assertIn((9,25), transition)
            self.assertIn((int(x),int(y)), transition)
            self.assertGreaterEqual(len(transition),len(original))
        w.gates['A'] = True
        w.player.x,w.player.y = 14.5,23.5
        next_room = w.room_tiles()
        self.assertIn((14,23), next_room)
        self.assertNotIn((9,25), next_room)

if __name__ == '__main__':
    unittest.main()
