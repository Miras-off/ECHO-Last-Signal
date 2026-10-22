import unittest,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from echo_game.world import World,load_map,SOLUTIONS
from echo_game.commands import interpret,vocabulary
from echo_game.storage import Storage

class GameTests(unittest.TestCase):
    def setUp(self):self.w=World(1)
    def obj(self,kind,world=None,**kwargs):
        w=world or self.w
        return next(o for o in w.objects if o['type']==kind and all(o.get(k)==v for k,v in kwargs.items()))
    def jump(self,kind,world=None,**kwargs):
        w=world or self.w;o=self.obj(kind,w,**kwargs);w.player.x=o['x'];w.player.y=o['y'];return o
    def pick(self,kind,world=None,**kwargs):
        w=world or self.w;o=self.jump(kind,w,**kwargs);self.assertTrue(w.interact());return o
    def progress_terminal(self,w):
        self.jump('main_terminal',w)
        for name in ('connect','scan','hack','open'):self.assertTrue(w.command(name),name)
        self.assertTrue(w.gates['A']);self.assertEqual(w.terminal_stage,4)
    def progress_core(self,w):
        self.jump('core',w)
        a,b=SOLUTIONS[w.level]
        for name in ('scan','off_'+a,'on_'+b,'open'):self.assertTrue(w.command(name),name)
        self.assertTrue(w.gates['B']);self.assertEqual(w.core_stage,4)
    def test_maps_rectangular(self):
        for n in range(1,4):
            width,height,tiles,objs=load_map(n)
            self.assertEqual(len(tiles),width*height);self.assertGreaterEqual(len(objs),20)
    def test_mandatory_items_reachable(self):
        for n in range(1,4):
            w=World(n)
            for obj in w.objects:
                if obj['type'] in ('module','keycard','main_terminal') and obj['x']<13:
                    with self.subTest(n=n,name=obj['name']):
                        self.assertTrue(w.pathfind((w.player.x,w.player.y),(obj['x'],obj['y'])))
    def test_core_unreachable_until_gate_open(self):
        for n in (1,2,3):
            w=World(n);o=self.obj('core',w)
            self.assertFalse(w.pathfind((w.player.x,w.player.y),(o['x'],o['y'])))
            w.gates['A']=True
            self.assertTrue(w.pathfind((w.player.x,w.player.y),(o['x'],o['y'])))
    def test_exit_reachable_after_gates_open(self):
        for n in (1,2,3):
            w=World(n);w.gates={'A':True,'B':True};o=self.obj('exit',w)
            self.assertTrue(w.pathfind((w.player.x,w.player.y),(o['x'],o['y'])))
    def test_spawn_not_blocked(self):self.assertFalse(self.w.collides(self.w.player.x,self.w.player.y))
    def test_wall_blocks(self):self.assertTrue(self.w.collides(.5,.5))
    def test_closed_gate_blocks(self):self.assertTrue(self.w.collides(13.5,13.5))
    def test_open_gate_passable(self):self.w.gates['A']=True;self.assertFalse(self.w.collides(13.5,13.5))
    def test_wall_blocks_camera_line(self):self.assertFalse(self.w.ray_clear(12.5,7.5,15.5,7.5))
    def test_scanner_locked(self):self.assertFalse(self.w.command('scan'))
    def test_first_module_pickup(self):
        self.pick('module',ability='scan');self.assertIn('scan',self.w.abilities)
    def test_hack_locked_before_module(self):self.assertFalse(self.w.command('hack'))
    def test_terminal_order_enforced(self):
        self.w.abilities={'scan','hack'};self.w.inventory['keycard']=1
        self.jump('main_terminal')
        self.assertFalse(self.w.command('hack'));self.assertEqual(self.w.terminal_stage,0)
    def test_terminal_requires_key(self):
        self.w.abilities={'scan','hack'};self.jump('main_terminal')
        for x in ('connect','scan','hack'):self.assertTrue(self.w.command(x))
        self.assertFalse(self.w.command('open'))
    def test_terminal_sequence_works(self):
        self.w.abilities={'scan','hack'};self.w.inventory['keycard']=1
        self.progress_terminal(self.w)
    def test_wrong_core_color_rejected(self):
        self.w.abilities={'scan','hack'};self.w.inventory['keycard']=1
        self.progress_terminal(self.w);self.jump('core');self.w.command('scan')
        self.assertFalse(self.w.command('off_blue'));self.assertEqual(self.w.core_stage,1)
    def test_core_requires_scan(self):
        self.w.abilities={'scan'};self.jump('core');self.assertFalse(self.w.command('off_red'))
    def test_full_level_one_victory(self):
        self.pick('module',ability='scan');self.pick('module',ability='hack');self.pick('keycard')
        self.progress_terminal(self.w);self.progress_core(self.w)
        self.jump('exit');self.assertTrue(self.w.interact());self.assertEqual(self.w.status,'won')
    def test_full_level_two_victory(self):
        w=World(2,abilities={'scan','hack'})
        self.pick('module',w,ability='shield');self.pick('keycard',w)
        self.progress_terminal(w)
        self.pick('module',w,ability='pulse')
        self.progress_core(w);self.jump('exit',w);self.assertTrue(w.interact());self.assertEqual(w.status,'won')
    def test_full_level_three_victory(self):
        w=World(3,abilities={'scan','hack','shield','pulse'})
        self.pick('module',w,ability='control');self.pick('keycard',w)
        self.progress_terminal(w);self.progress_core(w)
        self.pick('module',w,ability='memory');self.jump('exit',w)
        self.assertTrue(w.interact());self.assertEqual(w.status,'won')
    def test_exit_before_puzzle_blocked(self):
        self.jump('exit');self.assertFalse(self.w.interact());self.assertEqual(self.w.status,'playing')
    def test_stun_is_temporary(self):
        d=self.w.drones[0]
        self.w.abilities.add('pulse');self.w.player.x=d.x;self.w.player.y=d.y
        self.w.command('pulse')
        d.stunned=-1.0
        self.w.player.x=2.5;self.w.player.y=22.5
        self.w._drone_step(d,.01)
        self.assertNotEqual(d.state,'stunned')
    def test_actual_voice_stats_only(self):
        self.w.abilities.add('scan')
        self.w.command('scan','keyboard')
        self.assertEqual(self.w.stats['voice_success'],0)
        self.w.command('scan','voice')
        self.assertEqual(self.w.stats['voice_success'],1)
    def test_shield_needs_module(self):self.assertFalse(self.w.command('shield'))
    def test_shield_works(self):
        self.w.abilities.add('shield');self.assertTrue(self.w.command('shield'))
        self.assertTrue(self.w.shielded);self.assertEqual(self.w.player.energy,71)
    def test_shield_obscures_sensors(self):
        self.w.abilities.add('shield');self.w.command('shield')
        self.assertFalse(self.w.visible_to_sensor(self.w.player.x,self.w.player.y,0,5,360))
    def test_pulse_needs_module(self):self.assertFalse(self.w.command('pulse'))
    def test_pulse_stuns(self):
        self.w.abilities.add('pulse');d=self.w.drones[0]
        self.w.player.x=d.x;self.w.player.y=d.y
        self.assertTrue(self.w.command('pulse'))
        self.assertGreater(d.stunned,self.w.time)
    def test_medkit(self):
        self.w.player.hp=42;self.w.command('medkit');self.assertEqual(self.w.player.hp,87)
    def test_battery(self):
        self.w.player.energy=3;self.w.command('battery');self.assertEqual(self.w.player.energy,63)
    def test_lure_requires_item(self):self.assertFalse(self.w.command('lure'))
    def test_lure_deploys(self):
        self.w.inventory['lure']=1;self.assertTrue(self.w.command('lure'));self.assertIsNotNone(self.w.lure_pos)
    def test_hp_zero_loses(self):
        self.w.damage(150,'Турель');self.assertEqual(self.w.status,'lost')
    def test_move_does_not_cross_wall(self):
        self.w.player.x=1.35;self.w.player.y=4.5
        self.w.step(.05,-1,0);self.assertGreaterEqual(self.w.player.x,1.35)
    def test_difficulty_adjusts_to_errors(self):
        for _ in range(5):self.w.command('what?')
        self.assertLess(self.w.difficulty,1)
    def test_commands_russian(self):
        examples={'Нова, сканируй':'scan','Подключись к терминалу':'connect','Взломай систему':'hack','открой шлюз':'open','Включи щит':'shield','примени импульс':'pulse','отключи красное ядро':'off_red','активируй жёлтое ядро':'on_yellow','включи синее':'on_blue'}
        for text,expected in examples.items():
            with self.subTest(text=text):self.assertEqual(interpret(text),expected)
    def test_blank_command_unknown(self):self.assertIsNone(interpret(' '))
    def test_vocab_contains_keywords(self):self.assertIn('сканируй',vocabulary())
    def test_storage_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Storage(Path(tmp)/'test.sqlite3')
            store.save(self.w.snapshot());self.assertEqual(store.load()['level'],1)
            store.record(self.w);self.assertEqual(store.best()[0][0],1)
            store.unlock('premium_challenge');self.assertTrue(store.has_unlock('premium_challenge'))
            store.clear();self.assertIsNone(store.load())
    def test_all_map_objects_have_valid_coordinates(self):
        for n in range(1,4):
            w=World(n)
            for o in w.objects:
                with self.subTest(n=n,o=o['name']):
                    self.assertGreaterEqual(o['x'],0);self.assertLess(o['x'],w.width)
                    self.assertGreaterEqual(o['y'],0);self.assertLess(o['y'],w.height)
                    if o['type'] in ('module','keycard','medkit','battery','note','exit','main_terminal','core'):
                        self.assertFalse(w.collides(o['x'],o['y'],.01) if o['type'] in ('exit','main_terminal','core') else w.tiles[int(o['y'])*w.width+int(o['x'])] in (2,5))

if __name__=='__main__':unittest.main(verbosity=2)
