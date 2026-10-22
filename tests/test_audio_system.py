"""Audio integration tests; can execute without pygame/audio device."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class FakeChannel:
    def __init__(self):self.played=[];self.busy=False;self.volume=0.;self.stops=0
    def get_busy(self):return self.busy
    def play(self,sound,loops=0):self.played.append((sound,loops));self.busy=True
    def set_volume(self,v):self.volume=v
    def stop(self):self.busy=False;self.stops+=1

class FakeMixer:
    def __init__(self):self.channels=[FakeChannel() for _ in range(24)]
    def get_init(self):return (24000,-16,2)
    def set_num_channels(self,v):pass
    def get_num_channels(self):return 24
    def Channel(self,i):return self.channels[i]
    def Sound(self,path):return Path(path).stem

class AudioTests(unittest.TestCase):
    def setUp(self):
        self.mixer=FakeMixer()
        stub=types.ModuleType('pygame');stub.mixer=self.mixer;stub.error=RuntimeError
        spec=importlib.util.spec_from_file_location('_echo_test_audio',ROOT/'echo_game'/'audio.py')
        mod=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'pygame':stub}):spec.loader.exec_module(mod)
        self.audio_cls=mod.AudioDirector
        self.cfg={'master_volume':70,'music_volume':65,'sfx_volume':80,'voice_volume':75,'music_enabled':True,'sound_enabled':True,'ambient_enabled':True}
        self.audio=self.audio_cls(ROOT/'assets'/'audio',self.cfg)

    def test_complete_pack_has_music_and_event_files(self):
        needed=['music_menu','music_level_1','music_level_2','music_level_3','music_tension','music_chase','ambience_ship','drone_alert','camera_warning','camera_lock','turret_fire','drone_attack','puzzle_ok','puzzle_error','door','module','ui_click']
        for key in needed:
            with self.subTest(sound=key):self.assertIn(key,self.audio.sounds)
        self.assertTrue(self.audio.available)

    def test_different_levels_change_music_without_cutting_previous_early(self):
        world=types.SimpleNamespace(status='playing',level=1,alert=0.,camera_suspicion={},drones=[])
        self.audio.update(.2,'menu')
        self.assertEqual(self.audio.base_key,'music_menu')
        old_channel=self.audio.active_base
        self.audio.update(.2,'play',world)
        self.assertEqual(self.audio.base_key,'music_level_1')
        self.assertNotEqual(old_channel,self.audio.active_base)
        self.assertTrue(self.mixer.channels[old_channel].get_busy())
        world.level=3
        self.audio.update(.2,'play',world)
        self.assertEqual(self.audio.base_key,'music_level_3')

    def test_alert_and_chase_are_separate_music_layers(self):
        drone=types.SimpleNamespace(state='chase')
        world=types.SimpleNamespace(status='playing',level=2,alert=80,camera_suspicion={},drones=[drone])
        for _ in range(30):self.audio.update(.075,'play',world)
        self.assertGreater(self.mixer.channels[3].volume,0.05)
        world.alert=0;drone.state='patrol'
        for _ in range(85):self.audio.update(.075,'play',world)
        self.assertLess(self.mixer.channels[3].volume,0.02)

    def test_cooldown_prevents_overlapping_detection(self):
        self.audio.update(.03)
        self.assertTrue(self.audio.play('camera_lock'))
        self.assertFalse(self.audio.play('camera_lock'))
        for _ in range(80):self.audio.update(.03)
        self.assertTrue(self.audio.play('camera_lock'))

    def test_master_and_sfx_mute_do_not_disable_music(self):
        self.cfg['sound_enabled']=False
        self.audio.configure(self.cfg)
        self.assertFalse(self.audio.play('turret_fire'))
        self.audio.update(.1,'menu')
        self.assertTrue(self.mixer.channels[self.audio.active_base].get_busy())
        self.cfg['music_enabled']=False
        for _ in range(30):self.audio.update(.1,'menu')
        self.assertAlmostEqual(self.mixer.channels[self.audio.active_base].volume,0)

    def test_no_audio_device_graceful(self):
        self.audio.available=False
        self.assertFalse(self.audio.play('drone_alert'))
        self.audio.update(.016,'play',types.SimpleNamespace(status='playing',level=1,alert=40,drones=[],camera_suspicion={}))
        self.audio.stop()

if __name__=='__main__':unittest.main()
