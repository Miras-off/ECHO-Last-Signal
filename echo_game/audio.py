"""ECHO adaptive audio mixer (pygame-ce only; game remains playable without audio device).
Original OGG scores, WAV cues, reserved channels, smooth intensity and UI volume settings.
No game simulation logic depends on successful sound output.
"""
from __future__ import annotations
from pathlib import Path
import pygame

MUSIC={f'music_level_{i}' for i in (1,2,3)} | {'music_menu','music_tension','music_chase','ambience_ship'}
VOICELIKE={'module','scan','hack','terminal_open','power_down','power_up','shield_on'}
PRIORITY={
    'camera_warning':4,'camera_lock':9,'drone_alert':9,'security_alarm':8,
    'turret_target':5,'turret_fire':9,'drone_attack':9,'player_hit':8,
    'puzzle_ok':7,'puzzle_error':7,'fail':7,'victory':10,
    'pulse_blast':9,'shield_on':7,'door':8,'power_down':7,'power_up':7,
    'ui_click':2,'ui_back':2,'pickup':4,'keycard':5,
}
COOLDOWNS={
    'ui_click':.055,'ui_back':.06,
    'camera_warning':1.65,'camera_lock':2.1,'drone_alert':2.35,
    'drone_search':2.0,'security_alarm':6.0,'turret_target':.45,
    'turret_fire':.22,'drone_attack':.25,'player_hit':.3,
    'pickup':.12,'door':.55,'pulse_blast':.33,
}


def clamp01(v):return max(0.0,min(1.0,float(v)))


class AudioDirector:
    """Indexes 0–1: crossfading score; 2,3: intensity stems; 4: ship ambience; 5–23: SFX."""
    def __init__(self,asset_folder:Path,settings:dict):
        self.folder=Path(asset_folder);self.cfg=settings
        self.available=False;self.sounds={};self.channels=[]
        self.elapsed=0.;self.last_played={};self.active_fx={}
        self.base_key=None;self.active_base=0;self.base_targets=[0.,0.]
        self.base_gains=[0.,0.];self.tension=0.;self.chase=0.;self.air=0.
        try:
            if pygame.mixer.get_init() is None:pygame.mixer.init()
            pygame.mixer.set_num_channels(max(24,pygame.mixer.get_num_channels()))
            self.channels=[pygame.mixer.Channel(i) for i in range(24)]
            for file in sorted(self.folder.iterdir()):
                if file.suffix.lower() in ('.wav','.ogg'):
                    try:self.sounds[file.stem]=pygame.mixer.Sound(str(file))
                    except (pygame.error,OSError):continue  # keep available effects if one codec is unsupported
            self.available=True
        except (pygame.error,OSError,ValueError) as exc:
            self.error=str(exc)
            self.available=False

    def configure(self,settings:dict):
        self.cfg=settings
        # Settings do not stop/restart score; tracks continue quietly and volumes ramp.
        if not self.available:return
        if not settings.get('sound_enabled',True):
            for index in range(5,len(self.channels)):self.channels[index].set_volume(0)

    def _level(self,key,enabled=True):
        if not enabled:return 0.
        return clamp01(self.cfg.get('master_volume',70)/100)*clamp01(self.cfg.get(key,70)/100)

    def play(self,key:str,priority:int|None=None,volume:float=1.,category:str|None=None):
        if not self.available or key not in self.sounds:return False
        if category is None:category='voice' if key in VOICELIKE else 'sfx'
        enabled=self.cfg.get('sound_enabled',True)
        factor=self._level('voice_volume' if category=='voice' else 'sfx_volume',enabled)
        if factor<=0:return False
        cooldown=COOLDOWNS.get(key,.09)
        if self.elapsed-self.last_played.get(key,-100.)<cooldown:return False
        prio=PRIORITY.get(key,4) if priority is None else priority
        chosen=None
        for i in range(5,24):
            if not self.channels[i].get_busy():chosen=i;break
        if chosen is None:
            # Never interrupt music, or urgent audio with a lower-priority sound.
            choices=sorted((old_prio,i) for i,(old_prio,_) in self.active_fx.items() if i>=5)
            if not choices or choices[0][0]>prio:return False
            chosen=choices[0][1]
        channel=self.channels[chosen]
        channel.stop();channel.set_volume(clamp01(factor*volume*.70))
        try:channel.play(self.sounds[key])
        except pygame.error:return False
        self.last_played[key]=self.elapsed
        self.active_fx[chosen]=(prio,key)
        return True

    def _loop(self,index:int,key:str):
        channel=self.channels[index]
        if key in self.sounds:
            channel.set_volume(0)
            channel.play(self.sounds[key],loops=-1)

    def _scene(self,key):
        if self.base_key==key:return
        self.base_key=key
        nxt=1-self.active_base if self.base_gains[self.active_base]>.01 else self.active_base
        if key in self.sounds:self._loop(nxt,key)
        self.active_base=nxt
        self.base_targets=[0.,0.]
        self.base_targets[nxt]=1.

    def update(self,dt:float,mode:str='menu',world=None,overlay=False):
        self.elapsed+=max(0,min(.25,dt))
        if not self.available:return
        game_active=(mode=='play' and world is not None and world.status=='playing' and not overlay)
        if world is None or mode in ('menu','credits','records','store','help'):
            scene='music_menu'
        else:
            scene='music_level_'+str(max(1,min(3,world.level)))
        self._scene(scene)
        music_enabled=self.cfg.get('music_enabled',True)
        music_gain=self._level('music_volume',music_enabled)
        scene_gain=.52 if game_active else .46 if mode=='menu' else .25
        if game_active:
            suspicion=max(world.camera_suspicion.values(),default=0.)
            pursuing=any(d.state=='chase' for d in world.drones)
            searching=any(d.state=='search' for d in world.drones)
            alert=float(world.alert)
            target_chase=clamp01((alert-38)/44 + (.73 if pursuing else 0))
            target_tension=clamp01(alert/48 + (.34 if searching else 0) + min(.5,suspicion*.7))*(1-target_chase*.5)
        else:target_tension=target_chase=0.
        fade=max(0,min(1,dt*1.7))
        for i in range(2):
            self.base_gains[i]+=(self.base_targets[i]-self.base_gains[i])*fade
            value=music_gain*scene_gain*self.base_gains[i]*(1-target_chase*.38)
            self.channels[i].set_volume(clamp01(value))
        for name,index,target,mult in (
            ('tension',2,target_tension,.39),('chase',3,target_chase,.60)
        ):
            if not self.channels[index].get_busy() and self.sounds.get('music_'+name):
                self._loop(index,'music_'+name)
            old=getattr(self,name)
            val=old+(target-old)*max(0,min(1,dt*1.8))
            setattr(self,name,val)
            self.channels[index].set_volume(clamp01(val*music_gain*mult))
        if not self.channels[4].get_busy() and 'ambience_ship' in self.sounds:
            self._loop(4,'ambience_ship')
        ambient_target=.20 if game_active and self.cfg.get('ambient_enabled',False) else 0.
        self.air+=(ambient_target-self.air)*max(0,min(1,dt*1.2))
        self.channels[4].set_volume(clamp01(self.air*self._level('music_volume',music_enabled)))

    def stop(self):
        if not self.available:return
        for channel in self.channels:channel.stop()
