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

    def test_room_view_includes_walls_but_not_neighboring_floor(self):
        w = World(1)
        base = w.room_tiles()
        view = w.room_view_tiles()
        self.assertTrue(base.issubset(view))
        self.assertTrue(any(not w.is_walkable_tile(*cell) for cell in view))
        self.assertTrue(all(cell in base or not w.is_walkable_tile(*cell) for cell in view))

if __name__ == '__main__':
    unittest.main()
