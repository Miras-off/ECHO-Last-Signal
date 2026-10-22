"""Regression checks for renderer-agnostic combat animation events."""
import unittest

from echo_game.world import World


class CombatEffectsTests(unittest.TestCase):
    def test_player_pulse_captures_stunned_drone_positions(self):
        world=World(2,abilities={'pulse'})
        drone=world.drones[0]
        world.player.x,world.player.y=drone.x,drone.y
        expected=[drone.x,drone.y]
        self.assertTrue(world.command('pulse'))
        event=world.combat_events[-1]
        self.assertEqual(event['kind'],'player_pulse')
        self.assertIn(expected,event['targets'])
        self.assertGreater(drone.stunned,world.time)
        self.assertNotIn('combat_events',world.snapshot())

    def test_drone_attack_emits_event_with_fixed_endpoints(self):
        world=World(1)
        drone=world.drones[0]
        world.player.x,world.player.y=drone.x+.25,drone.y
        drone.state='chase';drone.attack_cooldown=0;drone.path_timer=99
        world.last_damage=-10
        world._drone_step(drone,.01)
        event=next(event for event in world.combat_events if event['kind']=='drone_attack')
        self.assertEqual(event['source'],[drone.x,drone.y])
        self.assertEqual(event['target'],[world.player.x,world.player.y])

    def test_turret_shot_emits_event_before_damage(self):
        world=World(1)
        turret=next(o for o in world.objects if o['type']=='turret')
        target=None
        for distance in (1,2,3):
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                x,y=turret['x']+dx*distance,turret['y']+dy*distance
                if not world.collides(x,y,.2) and world.ray_clear(turret['x'],turret['y'],x,y):
                    target=(x,y);break
            if target:break
        self.assertIsNotNone(target)
        world.player.x,world.player.y=target
        world.alert=100;world.last_damage=-10
        hp=world.player.hp
        world.step(.01)
        event=next(event for event in world.combat_events if event['kind']=='turret_shot')
        self.assertEqual(event['source'],[turret['x'],turret['y']])
        self.assertLess(world.player.hp,hp)

    def test_expired_combat_events_are_pruned(self):
        world=World(1)
        world.combat_fx('test',(world.player.x,world.player.y),duration=.05)
        world.step(.07);world.step(.07);world.step(.07)
        self.assertFalse(any(event['kind']=='test' for event in world.combat_events))


if __name__=='__main__':
    unittest.main()
