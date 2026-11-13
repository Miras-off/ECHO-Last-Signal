"""Pygame UI, drawing and input. Data/art not hardcoded: see maps/*.tmj and assets/.
Game logic (AI, sensor geometry, objectives) lives in world.py for headless tests.
"""
import math, sys, time
from pathlib import Path
import pygame
from .world import World,ROOT,distance,COLORS,SOLUTIONS
from .voice import VoiceListener
from .storage import Storage
from .commands import ACTIONS
from .config import read_settings, save_settings
from .adaptive import AdaptiveDirector
from .audio import AudioDirector

CFG=read_settings()
W,H=int(CFG['screen_width']),int(CFG['screen_height'])
HUD_W=360
VW=W-HUD_W
VH=H
T=int(CFG.get('tile_pixels',64))
PAL=CFG['palette']
def color(key):return pygame.Color(PAL.get(key,key))

class Game:
    def __init__(self):
        global W,H,VW,VH,PAL
        pygame.mixer.pre_init(24000,-16,2,512)
        pygame.init()
        try:pygame.display.set_caption('ECHO: Последний сигнал • Атлас-9')
        except Exception:pass
        W,H=int(CFG['screen_width']),int(CFG['screen_height'])
        flags=(pygame.FULLSCREEN|pygame.SCALED) if CFG.get('fullscreen',True) else 0
        VW=W-HUD_W;VH=H
        PAL=CFG['palette']
        try:self.window=pygame.display.set_mode((W,H),flags)
        except pygame.error:
            flags=0
            self.window=pygame.display.set_mode((W,H))
        self.clock=pygame.time.Clock();self.running=True
        self.fullscreen=bool(flags & pygame.FULLSCREEN)
        self.sound_log_counter=0;self.last_alert_level=0;self.last_combat_audio_id=0
        self.camera_warning_ids=set();self.previous_drone_states={};self.turret_armed=False
        self.fonts={}
        self.glow_cache={}
        self.ring_cache={}
        self.image_cache={}
        self.text_cache={}
        self.combat_layer=pygame.Surface((VW,VH),pygame.SRCALPHA)
        self.mode='menu';self.world=None
        self.storage=Storage();self.voice=VoiceListener()
        self.wallet_cache=self.storage.wallet()
        self.last_wallet_refresh=time.monotonic()
        self.loss_accounted=False
        self.payment_product=None;self.payment_origin='store';self.payment_receipt=None
        self.assets={};self.cover=None;self.tiles=None
        self.buttons=[];self.action_open=False;self.map_open=False;self.notes_open=False
        self.message_note='';self.total_score=0;self.game_ending='';self.prev_level=1
        self.hover_object=None
        self.puzzle_open=None
        self.director=AdaptiveDirector(ROOT/"save_data"/"adaptive_qtable.json")
        self.room_key=None
        self.load_art()
        self.load_sounds()
        self.apply_audio_settings()
    def load_sounds(self):
        self.audio=AudioDirector(ROOT/'assets'/'audio',CFG)

    def apply_audio_settings(self):
        self.audio.configure(CFG)

    def persist_settings(self):
        global CFG,PAL
        CFG=save_settings(CFG)
        PAL=CFG['palette']
        self.apply_audio_settings()

    def sound(self,key,**kwargs):
        return self.audio.play(key,**kwargs)

    def toggle_fullscreen(self):
        global W,H,VW,VH
        self.fullscreen=not self.fullscreen
        W,H=int(CFG['screen_width']),int(CFG['screen_height'])
        self.window=pygame.display.set_mode((W,H),(pygame.FULLSCREEN|pygame.SCALED) if self.fullscreen else 0)
        VW=W-HUD_W;VH=H
    def set_toggle(self,key):
        CFG[key]=not CFG.get(key,False)
        if key=='fullscreen':
            self.toggle_fullscreen()
            CFG['fullscreen']=self.fullscreen
        self.persist_settings()

    def adjust_value(self,key,delta,lo=0,hi=100):
        CFG[key]=max(lo,min(hi,int(CFG.get(key,0))+delta))
        self.persist_settings()

    def font(self,size,bold=False):
        key=(size,bold)
        if key not in self.fonts:
            self.fonts[key]=pygame.font.SysFont('arial,dejavusans,liberationsans',size,bold=bold)
        return self.fonts[key]
    def load_art(self):
        src=ROOT/'assets'/'sprites'
        for img in src.glob('*.png'):
            try:self.assets[img.stem]=pygame.image.load(str(img)).convert_alpha()
            except pygame.error:pass
        try:self.tiles=pygame.image.load(str(ROOT/'assets/tiles/tileset.png')).convert_alpha()
        except pygame.error:self.tiles=None
        cover_path=ROOT/'assets'/'ui'/'menu_backdrop.png'
        if not cover_path.exists():cover_path=ROOT/'assets'/'ui'/'cover.png'
        try:self.cover=pygame.image.load(str(cover_path)).convert_alpha()
        except pygame.error:pass
    def text(self,s,x,y,size=21,tone='text',bold=False,maxw=0,center=False):
        value=str(s);key=(value,size,tone,bool(bold));surface=self.text_cache.get(key)
        if surface is None:
            surface=self.font(size,bold).render(value,True,color(tone))
        if maxw and surface.get_width()>maxw:
            while size>11 and surface.get_width()>maxw:
                size-=1;surface=self.font(size,bold).render(value,True,color(tone))
        if len(self.text_cache)>768:self.text_cache.clear()
        self.text_cache[key]=surface
        target=(x-surface.get_width()//2 if center else x,y)
        self.window.blit(surface,target)
        return surface.get_width()
    def wrap(self,string,width,size=17):
        words=str(string).split();lines=[];line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if self.font(size).size(candidate)[0]>width and line:
                lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
        return lines
    def paragraph(self,string,x,y,width,size=17,line_h=None,tone='muted',maxlines=8):
        for j,line in enumerate(self.wrap(string,width,size)[:maxlines]):
            self.text(line,x,y+j*(line_h or size+5),size,tone)
        return y+min(len(self.wrap(string,width,size)),maxlines)*(line_h or size+5)
    def rect(self,r,fill='panel',edge=None,rad=9,width=0):
        pygame.draw.rect(self.window,color(fill),r,border_radius=rad)
        if edge:pygame.draw.rect(self.window,color(edge),r,width or 1,border_radius=rad)
    def glow(self,position,radius,tone,alpha=42):
        """Soft additive glow used by practical lights and interactive objects."""
        key=(int(radius),tone,int(alpha));layer=self.glow_cache.get(key)
        if layer is None:
            rgb=color(tone)[:3]
            size=max(8,int(radius*2.4));layer=pygame.Surface((size,size),pygame.SRCALPHA)
            center=size//2
            for step in range(7,0,-1):
                rr=int(radius*step/7)
                pygame.draw.circle(layer,(*rgb,max(1,int(alpha*(1-step/8)**1.6))),(center,center),rr)
            self.glow_cache[key]=layer
        center=layer.get_width()//2
        self.window.blit(layer,(int(position[0]-center),int(position[1]-center)))
    def smooth_ring(self,position,radius,tone,alpha=185,width=1.5):
        """Draw a cached supersampled ring with a soft edge and stable geometry."""
        radius=round(max(2,float(radius))*4)/4;width=max(.75,float(width))
        key=(radius,tone,round(width,2));layer=self.ring_cache.get(key)
        if layer is None:
            rgb=color(tone)[:3]
            scale=4;pad=5
            side=max(13,int(math.ceil(radius+pad))*2+1)
            high=pygame.Surface((side*scale,side*scale),pygame.SRCALPHA)
            center=(high.get_width()//2,high.get_height()//2)
            rr=int(round(radius*scale));stroke=max(scale,int(round(width*scale)))
            pygame.draw.circle(high,(*rgb,34),center,rr+scale,stroke+scale*2)
            pygame.draw.circle(high,(*rgb,238),center,rr,stroke)
            layer=pygame.transform.smoothscale(high,(side,side))
            self.ring_cache[key]=layer
        layer.set_alpha(max(0,min(255,int(alpha))))
        self.window.blit(layer,(int(round(position[0]-layer.get_width()/2)),int(round(position[1]-layer.get_height()/2))))
    def animated_ring(self,position,base_radius,tone,clock,phase=0,width=1.35,hover=False,travel=2.25):
        """Breathing marker ring with a clearly visible rotating highlight."""
        wave=.5+.5*math.sin(clock*math.tau*.72+phase)
        radius=float(base_radius)+float(travel)*wave
        self.smooth_ring(position,radius,tone,255 if hover else 118+int(112*wave),2 if hover else width)
        angle=clock*2.75+phase
        rgb=color(tone)[:3]
        highlight=tuple(min(255,int(channel*.55+145)) for channel in rgb)
        points=[]
        for step in range(9):
            point_angle=angle+step*.065
            points.append((position[0]+math.cos(point_angle)*radius,position[1]+math.sin(point_angle)*radius))
        pygame.draw.aalines(self.window,highlight,False,points)
    def button(self,title,rect,callback,filled=False,disabled=False,small=False):
        x,y,w,h=rect;mouse=pygame.mouse.get_pos();hover=pygame.Rect(rect).collidepoint(mouse)
        fill='panel_alt' if not filled else 'accent'
        if hover and not disabled:fill='border' if not filled else 'good'
        self.rect(rect,fill,'border' if not filled else None,8)
        self.text(title,x+w//2,y+(h-(20 if not small else 16))//2,16 if small else 20,'background' if filled else ('muted' if disabled else 'text'),True,center=True)
        if not disabled:self.buttons.append((pygame.Rect(rect),callback))
    def image(self,name,cx,cy,width=48,height=None,flip=False):
        img=self.assets.get(name)
        if not img:return
        if height is None:height=width
        key=(name,int(width),int(height),bool(flip));frame=self.image_cache.get(key)
        if frame is None:
            frame=pygame.transform.smoothscale(img,(int(width),int(height)))
            if flip:frame=pygame.transform.flip(frame,True,False)
            self.image_cache[key]=frame
        self.window.blit(frame,(int(cx-width/2),int(cy-height/2)))
    @staticmethod
    def countdown(seconds):
        """Human-readable time until one free life. None means timer inactive."""
        if seconds is None:return None
        seconds=max(0,int(seconds))
        return f'{seconds//60:02d}:{seconds%60:02d}'

    def regeneration_label(self,status):
        if status['unlimited']:return 'PREMIUM: БЕЗЛИМИТНЫЕ ПОПЫТКИ'
        remaining=self.countdown(status['next_life_in'])
        if remaining is None:return 'БЕСПЛАТНЫЕ ЖИЗНИ ВОССТАНОВЛЕНЫ'
        return f'БЕСПЛАТНО +1 ЖИЗНЬ ЧЕРЕЗ {remaining}'

    def start(self,resume=False,challenge=False):
        if not self.storage.can_play():
            self.mode='locked'
            return False
        self.loss_accounted=False
        snapshot=self.storage.load() if resume else None
        if challenge:
            self.world=World(2,abilities=['scan','hack','shield','pulse','control','memory'],inventory={'medkit':2,'battery':2,'keycard':1,'lure':2},challenge=True)
        elif snapshot:
            self.world=World(snapshot['level'],snapshot.get('abilities',[]),stats=snapshot.get('stats'),inventory=snapshot.get('inventory'))
            self.world.restore(snapshot)
            # Recover from old v2.1.1 save files written after a fatal hit.
            # Account lives are checked above; this does not refill the wallet.
            if self.world.player.hp<=0:self.world.player.hp=100
            self.total_score=snapshot.get('total_score',0)
        else:
            self.world=World(1);self.total_score=0;self.storage.clear()
        self.mode='play';self.action_open=False;self.map_open=False;self.notes_open=False;self.puzzle_open=None;self.room_key=None
        self.director=AdaptiveDirector(ROOT/'save_data'/'adaptive_qtable.json')
        self.world.ai_factor=self.director.current_factor
        self.sound_log_counter=self.world.log_counter;self.last_alert_level=0
        self.last_combat_audio_id=0;self.camera_warning_ids=set();self.previous_drone_states={};self.turret_armed=False
        if not challenge:self.save()
    def save(self):
        # Keep the last playable checkpoint on defeat (never save a zero-HP snapshot).
        if self.world and not self.world.challenge and self.world.status!='lost':
            snap=self.world.snapshot();snap['total_score']=self.total_score;self.storage.save(snap)
    def restart(self):
        if not self.storage.can_play():
            self.mode='locked'
            return False
        self.loss_accounted=False
        if self.world:
            w=self.world
            self.world=World(w.level,abilities=w.abilities,inventory={'medkit':1,'battery':1,'keycard':0,'lure':0},challenge=w.challenge)
            self.sound_log_counter=self.world.log_counter;self.last_alert_level=0
            self.last_combat_audio_id=0;self.camera_warning_ids=set();self.previous_drone_states={};self.turret_armed=False
            self.mode='play';self.action_open=False;self.puzzle_open=None;self.room_key=None
    def next_level(self):
        w=self.world
        if not w:return
        self.storage.record(w,self.game_ending if w.level==3 else '')
        self.total_score+=w.score
        if w.challenge:
            self.mode='menu';return
        if w.level<3:
            self.world=World(w.level+1,abilities=w.abilities,stats=w.stats,inventory={'medkit':max(1,w.inventory['medkit']),'battery':max(1,w.inventory['battery']),'keycard':0,'lure':w.inventory['lure']})
            self.mode='play';self.sound_log_counter=self.world.log_counter;self.last_alert_level=0;self.last_combat_audio_id=0;self.camera_warning_ids=set();self.previous_drone_states={};self.turret_armed=False;self.puzzle_open=None;self.room_key=None;self.save()
        else:
            self.storage.clear();self.mode='credits'
    def handle_click(self,pos):
        for rect,cb in reversed(self.buttons):
            if rect.collidepoint(pos):self.sound('ui_click');cb();break
    def keyboard_action(self,key):
        mapping={pygame.K_1:'scan',pygame.K_2:'connect',pygame.K_3:'hack',pygame.K_4:'open',pygame.K_5:'shield',pygame.K_6:'pulse',pygame.K_7:'help',pygame.K_8:'off_red',pygame.K_9:'on_yellow',pygame.K_0:'off_blue',pygame.K_MINUS:'on_red',pygame.K_EQUALS:'off_yellow',pygame.K_BACKSPACE:'on_blue'}
        return mapping.get(key)
    def event(self,evt):
        if evt.type==pygame.QUIT:self.running=False;return
        if evt.type==pygame.MOUSEBUTTONDOWN and evt.button==1:self.handle_click(evt.pos);return
        if evt.type!=pygame.KEYDOWN:return
        if evt.key==pygame.K_F11:
            self.toggle_fullscreen();return
        if evt.key==pygame.K_ESCAPE:
            if self.action_open:self.action_open=False;return
            if self.map_open:self.map_open=False;return
            if self.notes_open:self.notes_open=False;return
            if self.puzzle_open:self.puzzle_open=None;self.sound('ui_back');return
            if self.mode=='play':self.mode='pause';self.sound('ui_back');self.save()
            elif self.mode=='pause':self.mode='play';self.sound('ui_click')
            elif self.mode=='settings':self.mode=getattr(self,'settings_return_mode','menu');self.sound('ui_back')
            else:self.mode='menu';self.sound('ui_back')
            return
        if self.mode=='play':
            w=self.world
            if self.puzzle_open:
                if evt.key in (pygame.K_1,pygame.K_2,pygame.K_3):
                    self.answer_puzzle(evt.key-pygame.K_1)
                return
            if evt.key in (pygame.K_e,pygame.K_SPACE):
                obj=w.nearby('puzzle',r=1.9)
                if obj and obj.get('puzzle_id') not in w.solved_puzzles:
                    self.puzzle_open=obj['puzzle_id'];self.sound('terminal_open');return
                w.interact();return
            if evt.key==pygame.K_TAB:self.action_open=not self.action_open;return
            if evt.key==pygame.K_m:self.map_open=not self.map_open;return
            if evt.key==pygame.K_n:self.notes_open=not self.notes_open;return
            if evt.key==pygame.K_v:
                self.sound('ui_click')
                if self.voice.state=='СЛУШАЕТ':self.voice.stop()
                else:self.voice.start()
                return
            if evt.key==pygame.K_h:w.use_item('medkit');return
            if evt.key==pygame.K_b:w.use_item('battery');return
            if evt.key==pygame.K_g:w.use_item('lure');return
            action=self.keyboard_action(evt.key)
            if action:w.command(action);return
        if self.mode=='result':
            if evt.key in (pygame.K_RETURN,pygame.K_SPACE):
                if self.world.status=='won':
                    if self.world.level==3 and not self.world.challenge:self.mode='ending_choice'
                    else:self.next_level()
                else:self.result_next()
        if self.mode=='ending_choice':
            if evt.key==pygame.K_1:self.choose_ending('Свобода')
            if evt.key==pygame.K_2 and 'memory' in self.world.abilities:self.choose_ending('Последний протокол')
    def answer_puzzle(self,index):
        if not self.puzzle_open or not self.world:return
        if self.world.solve_puzzle(self.puzzle_open,index):
            self.puzzle_open=None;self.save();self.sound('puzzle_ok')
        else:self.sound('puzzle_error')
        self.sound_log_counter=self.world.log_counter  # handled immediately; do not replay after leaving puzzle overlay

    def choose_ending(self,value):
        self.game_ending=value;self.world.ending=value;self.next_level()
    def read_voice(self):
        for tag,payload in self.voice.poll():
            if tag=='command' and self.world and self.mode=='play' and not self.puzzle_open:self.world.command(payload,'voice')
            elif tag=='notice' and self.world:self.world.message(payload,'info')
            elif tag=='heard' and self.world:self.world.message('РАСПОЗНАНО: '+payload,'voice')
    def tick(self,dt):
        self.read_voice()
        # A slow refresh keeps the in-game HUD in sync without querying SQLite
        # every frame. Menus use recovery_status() directly for live countdowns.
        if time.monotonic()-getattr(self,'last_wallet_refresh',0)>=1:
            self.wallet_cache=self.storage.wallet()
            self.last_wallet_refresh=time.monotonic()
        if self.mode!='play' or not self.world:
            self.audio.update(dt,self.mode,self.world)
            return
        if self.action_open or self.map_open or self.notes_open or self.puzzle_open:
            self.audio.update(dt,'play',self.world,overlay=True)
            return
        keys=pygame.key.get_pressed()
        dx=int(keys[pygame.K_d] or keys[pygame.K_RIGHT])-int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy=int(keys[pygame.K_s] or keys[pygame.K_DOWN])-int(keys[pygame.K_w] or keys[pygame.K_UP])
        self.world.step(dt,dx,dy,bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]))
        # Adaptive AI decisions stay stable within a room.
        if not self.world.is_portal_tile(int(self.world.player.x),int(self.world.player.y)):
            new_key=frozenset(self.world.room_tiles())
            if self.room_key is None:self.room_key=new_key
            elif self.room_key!=new_key:
                self.room_key=new_key
                factor,reason=self.director.advance(self.world.stats,self.world.player.hp,self.world.time)
                self.world.ai_factor=factor
                self.world.message(f'AI DIRECTOR: {reason} ({factor:.2f}x)','nova')
                self.save()
        self.audio_events()
        self.audio.update(dt,'play',self.world)
        if self.world.status!='playing':
            if self.world.status=='lost' and not self.loss_accounted:
                self.wallet_cache=self.storage.record_defeat()
                self.loss_accounted=True
            self.sound('victory' if self.world.status=='won' else 'fail')
            self.mode='result';self.save()

    def audio_events(self):
        """Emit one distinct cue per gameplay event, never on every rendered frame."""
        w=self.world
        if w is None:return
        entries=w.log
        new_count=min(max(0,w.log_counter-self.sound_log_counter),len(entries))
        for _,msg,kind in (entries[-new_count:] if new_count else []):
            t=msg.lower()
            if 'дрон обнаружил' in t:self.sound('drone_alert')
            elif 'камера навела' in t:self.sound('camera_lock')
            elif 'импульс дрона' in t or 'выстрел турели' in t:self.sound('player_hit')
            elif 'аптечка использована' in t:self.sound('medkit')
            elif 'энергия новы восстановлена' in t:self.sound('battery')
            elif 'маяк запущен' in t:self.sound('lure')
            elif 'карта' in t and 'найдено' in t:self.sound('keycard')
            elif 'модуль' in t and 'установлен' in t:self.sound('module')
            elif 'найдено' in t or t.startswith('архив:'):self.sound('pickup')
            elif 'шлюз' in t and 'открыт' in t:self.sound('door')
            elif 'ядро отключено' in t:self.sound('power_down')
            elif 'ядро активировано' in t:self.sound('power_up')
            elif 'сканирован' in t:self.sound('scan')
            elif 'взлом' in t or 'шифрование' in t:self.sound('hack')
            elif 'маскировочное поле активировано' in t:self.sound('shield_on')
            elif 'импульс активирован' in t or 'оглушено дронов' in t:self.sound('pulse_blast')
            elif 'соединение активно' in t or 'терминал подключ' in t:self.sound('terminal_open')
            elif kind=='warning' and 'невер' in t:self.sound('puzzle_error')
        self.sound_log_counter=w.log_counter
        # Track targeting stage before the camera crosses the critical 100% lock threshold.
        active_warning={id for id,v in w.camera_suspicion.items() if .32<=v<1.0}
        if active_warning-self.camera_warning_ids:self.sound('camera_warning')
        self.camera_warning_ids=active_warning
        # Combat events contain stable IDs, unlike visual animations (which are frame based).
        for event in w.combat_events:
            eid=event['id']
            if eid<=self.last_combat_audio_id:continue
            kind=event['kind']
            if kind=='turret_shot':self.sound('turret_fire')
            elif kind=='drone_attack':self.sound('drone_attack')
            elif kind=='player_pulse':self.sound('pulse_blast')
            self.last_combat_audio_id=eid
        if w.alert>=47:
            turret_aim=any(o['type']=='turret' and distance((o['x'],o['y']),(w.player.x,w.player.y))<=float(o.get('range',7)) and w.ray_clear(o['x'],o['y'],w.player.x,w.player.y) for o in w.objects)
        else:turret_aim=False
        if turret_aim and not self.turret_armed:self.sound('turret_target')
        self.turret_armed=turret_aim
        for idx,drone in enumerate(w.drones):
            old=self.previous_drone_states.get(idx)
            if old and drone.state=='search' and old not in ('search','chase','stunned'):
                self.sound('drone_search')
            self.previous_drone_states[idx]=drone.state
        if self.last_alert_level<2<=w.alert_level:self.sound('security_alarm')
        self.last_alert_level=w.alert_level

    def draw_background(self):
        self.window.fill(color('background'))
        for y in range(0,H,52):pygame.draw.line(self.window,(17,36,52),(0,y),(W,y))
        for x in range(0,W,52):pygame.draw.line(self.window,(17,36,52),(x,0),(x,H))
        glow=pygame.Surface((W,H),pygame.SRCALPHA)
        pygame.draw.circle(glow,(67,214,224,18),(W-180,110),220)
        pygame.draw.circle(glow,(242,120,133,14),(110,H-80),170)
        self.window.blit(glow,(0,0))
    def menu(self):
        self.draw_background()
        if self.cover:
            img=pygame.transform.smoothscale(self.cover,(W,H));self.window.blit(img,(0,0))
            tint=pygame.Surface((W,H),pygame.SRCALPHA);tint.fill((3,12,23,112));self.window.blit(tint,(0,0))
        self.text('E C H O',W-340,45,54,'text',True,center=True)
        self.text('ПОСЛЕДНИЙ СИГНАЛ',W-340,108,15,'accent',True,center=True)
        pygame.draw.line(self.window,color('accent'),(W-505,137),(W-175,137),2)
        pygame.draw.rect(self.window,(7,21,35),(29,266,525,444),border_radius=16)
        self.rect((42,285,500,417),'panel','border',14)
        self.text('АТЛАС-9  /  ЭВАКУАЦИЯ',77,309,17,'accent',True)
        wallet=self.storage.recovery_status()
        if wallet['unlimited']:
            life_text='ЖИЗНИ: БЕЗЛИМИТ'
        else:
            life_text=f'ЖИЗНИ: {wallet["lives"]}'
            if wallet['next_life_in'] is not None:
                life_text+=f'  •  +1 БЕСПЛАТНО: {self.countdown(wallet["next_life_in"])}'
        self.text(life_text,77,430,15,'good' if wallet['lives']>0 or wallet['unlimited'] else 'gold',True)
        self.paragraph('Ты очнулся на заброшенном военном корабле. Восстанови Нову, избегай охраны и найди спасательную шлюпку.',77,353,425,20,28,'text')
        self.button('НОВАЯ ИГРА' if self.storage.can_play() else 'ВОССТАНОВЛЕНИЕ / МАГАЗИН',(73,454,432,51),lambda:self.start(),True)
        self.button('ПРОДОЛЖИТЬ',(73,514,210,48),lambda:self.start(resume=True),disabled=self.storage.load() is None or not self.storage.can_play(),small=True)
        self.button('КАК ИГРАТЬ',(296,514,209,48),lambda:self.set_mode('help'),small=True)
        self.button('РЕКОРДЫ',(73,574,210,48),lambda:self.set_mode('records'),small=True)
        self.button('НАСТРОЙКИ',(296,574,209,48),lambda:self.set_mode('settings'),small=True)
        self.button('МАГАЗИН / PREMIUM',(73,634,210,44),lambda:self.set_mode('store'),small=True)
        self.button('ВЫХОД',(296,634,209,44),lambda:setattr(self,'running',False),small=True)
        self.text('v2.1.3 • FREE LIFE EVERY 15 MIN / DEMO PAYMENTS',23,746,14,'muted')
    def set_mode(self,value):
        if value=='settings':self.settings_return_mode='pause' if self.mode=='pause' else 'menu'
        self.mode=value
    def world_camera(self):
        p=self.world.player
        look_x=(0.22 if p.facing=='right' else -0.22 if p.facing=='left' else 0)*T
        look_y=(0.20 if p.facing=='down' else -0.12 if p.facing=='up' else 0)*T
        target_x=p.x*T-VW*0.5+look_x
        target_y=p.y*T-VH*0.5+look_y
        return (max(0,min(self.world.width*T-VW,target_x)),max(0,min(self.world.height*T-VH,target_y)))
    def px(self,x,y,camera):return (int(x*T-camera[0]),int(y*T-camera[1]))
    def draw_map_tiles(self,camera):
        w=self.world
        self.window.set_clip(pygame.Rect(0,0,VW,VH))
        sx=max(0,int(camera[0]/T));ex=min(w.width,math.ceil((camera[0]+VW)/T)+1)
        sy=max(0,int(camera[1]/T));ey=min(w.height,math.ceil((camera[1]+VH)/T)+1)
        for y in range(sy,ey):
            for x in range(sx,ex):
                gid=w.tiles[y*w.width+x]
                xx=int(x*T-camera[0]);yy=int(y*T-camera[1])
                # Broad, layered deck plates: details are smaller than a logical tile,
                # which removes the old board-game grid look without changing physics.
                floor=(20,31,45) if (x//4+y//3)%2 else (24,38,53)
                pygame.draw.rect(self.window,floor,(xx,yy,T,T))
                pygame.draw.line(self.window,(42,62,78),(xx,yy),(xx+T,yy),1)
                pygame.draw.line(self.window,(10,19,29),(xx,yy+T-1),(xx+T,yy+T-1),1)
                if (x*17+y*31)%11==0:
                    pygame.draw.line(self.window,(47,68,82),(xx+8,yy+13),(xx+39,yy+13),1)
                    pygame.draw.circle(self.window,(8,15,23),(xx+9,yy+38),2)
                    pygame.draw.circle(self.window,(66,83,94),(xx+39,yy+38),1)
                if x%4==0:pygame.draw.line(self.window,(55,76,91),(xx,yy+4),(xx,yy+T-4),2)
                if y%3==0:pygame.draw.line(self.window,(49,69,86),(xx+4,yy),(xx+T-4,yy),2)
                if gid in (2,5):
                    # Thick bulkhead with crown, inset machinery and a cast lower shadow.
                    pygame.draw.rect(self.window,(7,13,21),(xx+4,yy+7,T,T),border_radius=5)
                    pygame.draw.rect(self.window,(31,45,59),(xx,yy,T,T),border_radius=4)
                    pygame.draw.polygon(self.window,(67,88,104),[(xx+3,yy+4),(xx+T-3,yy+4),(xx+T-9,yy+12),(xx+9,yy+12)])
                    pygame.draw.rect(self.window,(19,30,43),(xx+7,yy+15,T-14,T-22),border_radius=3)
                    pygame.draw.rect(self.window,(49,68,83),(xx+10,yy+18,T-20,T-29),2,border_radius=2)
                    pygame.draw.line(self.window,(9,16,25),(xx+3,yy+T-4),(xx+T-3,yy+T-4),5)
                    if (x*5+y)%4==0:
                        lamp='bad' if (x+y)%9==0 else 'accent'
                        pygame.draw.rect(self.window,color(lamp),(xx+17,yy+8,14,3),border_radius=2)
                        self.glow((xx+24,yy+10),24,lamp,24)
                    else:
                        pygame.draw.circle(self.window,(93,111,122),(xx+9,yy+9),2)
                        pygame.draw.circle(self.window,(7,13,21),(xx+39,yy+9),2)
                elif gid in (3,4,6,7,8):
                    if gid==3:
                        pygame.draw.circle(self.window,(55,100,120),(xx+24,yy+24),10,2)
                        pygame.draw.circle(self.window,(38,69,93),(xx+24,yy+24),5)
                    elif gid==4:
                        pygame.draw.rect(self.window,(43,74,97),(xx+9,yy+7,30,34),border_radius=4)
                        pygame.draw.rect(self.window,(86,141,156),(xx+12,yy+10,24,28),2,border_radius=3)
                        for k in range(3):pygame.draw.line(self.window,(75,125,147),(xx+15,yy+16+k*7),(xx+32,yy+16+k*7),1)
                    else:
                        pygame.draw.line(self.window,(49,100,121),(xx+7,yy+24),(xx+41,yy+24),3)
        self.window.set_clip(None)

    def draw_environment_details(self,camera):
        """Non-colliding set dressing derived deterministically from map geometry."""
        w=self.world;room=w.room_view_tiles();self.window.set_clip(pygame.Rect(0,0,VW,VH))
        for gx,gy in room:
            if not w.is_walkable_tile(gx,gy):continue
            sx,sy=self.px(gx+.5,gy+.5,camera)
            seed=(gx*92821+gy*68917+w.level*101)%97
            # Wall-mounted consoles, pipe runs and hazard markings.
            adjacent=not w.is_walkable_tile(gx,gy-1)
            if adjacent and seed in (2,7,13,31):
                pygame.draw.rect(self.window,(5,10,17),(sx-22,sy-21,44,13),border_radius=3)
                pygame.draw.rect(self.window,(42,65,78),(sx-20,sy-20,40,10),border_radius=2)
                screen='bad' if seed==31 else 'accent'
                pygame.draw.rect(self.window,color(screen),(sx-13,sy-17,20,4),border_radius=2)
                pygame.draw.line(self.window,(116,129,130),(sx+12,sy-17),(sx+17,sy-17),2)
                self.glow((sx-3,sy-16),28,screen,22)
            elif adjacent and seed in (43,59):
                pygame.draw.line(self.window,(9,13,18),(sx-20,sy-18),(sx+21,sy+17),8)
                pygame.draw.line(self.window,(73,57,42),(sx-20,sy-18),(sx+21,sy+17),3)
                for n in (-12,0,12):pygame.draw.circle(self.window,(122,92,56),(sx+n,sy+n//2),3,1)
            # Floor vents and maintenance labels add scale without blocking movement.
            if seed in (5,17):
                pygame.draw.rect(self.window,(10,18,25),(sx-15,sy-9,30,18),border_radius=2)
                pygame.draw.rect(self.window,(48,66,76),(sx-14,sy-8,28,16),1,border_radius=2)
                for n in range(-10,13,5):pygame.draw.line(self.window,(43,58,68),(sx+n,sy-6),(sx+n,sy+6),1)
            elif seed==73:
                pygame.draw.line(self.window,(151,104,45),(sx-20,sy+15),(sx+20,sy+15),3)
                for n in range(-16,18,8):pygame.draw.line(self.window,(16,22,28),(sx+n,sy+11),(sx+n+8,sy+19),3)
        self.window.set_clip(None)

    def draw_practical_lights(self,camera):
        w=self.world;room=w.room_view_tiles();self.window.set_clip(pygame.Rect(0,0,VW,VH))
        for o in w.objects:
            if o.get('taken') or (int(o['x']),int(o['y'])) not in room:continue
            if o['type'] not in ('main_terminal','aux_terminal','core','exit','camera','turret','puzzle','gate'):continue
            sx,sy=self.px(o['x'],o['y'],camera)
            tone='bad' if o['type'] in ('camera','turret','gate') else 'gold' if o['type']=='core' else 'good' if o['type']=='exit' else 'accent'
            self.glow((sx,sy),54 if o['type'] in ('core','exit') else 38,tone,36)
        p=w.player;sx,sy=self.px(p.x,p.y,camera)
        self.glow((sx-43,sy-40),58,'accent',42)
        self.window.set_clip(None)

    def draw_fog(self,camera):
        w=self.world
        overlay=pygame.Surface((VW,VH),pygame.SRCALPHA)
        overlay.fill((3,8,15,255))
        for gx,gy in w.room_view_tiles():
            rx=int(gx*T-camera[0]);ry=int(gy*T-camera[1])
            pygame.draw.rect(overlay,(0,0,0,0),(rx,ry,T,T))
        self.window.blit(overlay,(0,0))

    def draw_cones(self,camera):
        w=self.world
        layer=pygame.Surface((VW,VH),pygame.SRCALPHA)
        def cast_sector(sx,sy,angle,radius,width,rgb,opacity,samples=96,outline=None):
            origin=self.px(sx,sy,camera)
            pts=[origin]
            for i in range(samples+1):
                theta=math.radians(angle-width/2+i*width/max(1,samples))
                stop=radius
                # Sub-tile ray steps are sufficient for 64 px walls and keep the
                # clipped sensor geometry inexpensive enough for 60 FPS.
                steps=max(6,int(radius*3))
                for n in range(1,steps+1):
                    dist=radius*n/steps
                    x=sx+math.cos(theta)*dist;y=sy+math.sin(theta)*dist
                    if w.collides(x,y,.04):
                        stop=max(0,dist-radius/steps)
                        break
                pts.append(self.px(sx+math.cos(theta)*stop,sy+math.sin(theta)*stop,camera))
            if len(pts)>2:
                pygame.draw.polygon(layer,(*rgb,opacity),pts)
                if outline and width<360:
                    pygame.draw.aalines(layer,(*outline,210),False,pts[1:])
                    pygame.draw.aaline(layer,(*outline,210),origin,pts[1])
                    pygame.draw.aaline(layer,(*outline,210),origin,pts[-1])
        for o in w.objects:
            if o['type']=='camera' and w.time>=w.cam_disable_until:
                angle=o.get('angle',0)+math.sin(w.time*.85+o['x'])*o.get('sweep',50)
                cast_sector(o['x'],o['y'],angle,o.get('range',7),64,(242,87,108),46,samples=26,outline=(255,157,170))
        for drone in w.drones:
            if w.time>=drone.stunned:
                cast_sector(drone.x,drone.y,0,min(3.7,drone.vision),360,(245,197,95),24,samples=26)
                tx,ty=((w.player.x,w.player.y) if drone.state=='chase' else
                       ((drone.base_x,drone.base_y) if drone.patrol_backward else (drone.target_x,drone.target_y)))
                heading=math.degrees(math.atan2(ty-drone.y,tx-drone.x))
                cast_sector(drone.x,drone.y,heading,min(2.7,drone.vision),66,(244,88,104),35,samples=20,outline=(255,135,148))
        self.window.blit(layer,(0,0))

    def draw_entities(self,camera):
        w=self.world
        room=w.room_view_tiles()
        self.window.set_clip(pygame.Rect(0,0,VW,VH))
        mouse=pygame.mouse.get_pos()
        self.hover_object=None
        names={'main_terminal':'terminal','aux_terminal':'terminal','broken_terminal':'terminal','exit':'exit','core':'core','module':'module','medkit':'medkit','battery':'battery','keycard':'keycard','lure':'lure','note':'note','camera':'camera','turret':'turret','puzzle':'puzzle'}
        marker_colors={
            'module':'good','medkit':'bad','battery':'accent','keycard':'gold','lure':'gold','note':'muted','puzzle':'accent',
            'main_terminal':'accent','aux_terminal':'accent','core':'gold','exit':'good','camera':'bad','turret':'bad'
        }
        marker_labels={
            'module':'МОДУЛЬ','medkit':'АПТЕЧКА','battery':'БАТАРЕЯ','keycard':'КЛЮЧ','lure':'МАЯК',
            'note':'ЗАПИСЬ','main_terminal':'ТЕРМИНАЛ','aux_terminal':'КОНСОЛЬ','core':'ЯДРО','exit':'ВЫХОД',
            'camera':'КАМЕРА','turret':'ТУРЕЛЬ','puzzle':'ЗАГАДКА'
        }
        marker_time=pygame.time.get_ticks()/1000.0
        for o in w.objects:
            if o['taken'] or o['type']=='spawn':continue
            if (int(o['x']),int(o['y'])) not in room:continue
            typ=o['type'];sx,sy=self.px(o['x'],o['y'],camera)
            if typ=='puzzle' and o.get('puzzle_id') in w.solved_puzzles:continue
            if not (-50<sx<VW+50 and -50<sy<VH+50):continue
            if typ=='gate':
                if w.gates[o['gate_id']]:
                    self.animated_ring((sx,sy),7,'good',marker_time,float(o['x'])+float(o['y']),1.5,travel=1.25)
                    self.text('ОТКР.',sx,sy-18,10,'good',True,center=True)
                    continue
                self.image('gate',sx,sy,58,58)
                pygame.draw.rect(self.window,(10,28,42),(sx-18,sy-30,36,14),border_radius=5)
                self.text('ШЛЮЗ',sx,sy-29,9,'bad',True,center=True)
                continue
            asset=names.get(typ)
            if not asset:continue
            size=50 if typ not in ('camera','turret') else 56
            pygame.draw.ellipse(self.window,(0,0,0,105),(sx-size//2+4,sy+size//3-3,size-8,11))
            self.image(asset,sx,sy,size)
            obj_rect=pygame.Rect(int(sx-size/2),int(sy-size/2),size,size)
            hover=obj_rect.collidepoint(mouse)
            key=marker_colors.get(typ)
            ring_phase=float(o['x'])*.73+float(o['y'])*.41
            if key and typ not in ('camera','turret'):
                ring_width=2 if hover or typ in ('main_terminal','core','exit') else 1.35
                self.animated_ring((sx,sy),size//2+5,key,marker_time,ring_phase,ring_width,hover)
            if typ=='camera':
                self.animated_ring((sx,sy),21,'bad',marker_time,ring_phase,1.35,hover,1.75)
                pygame.draw.aaline(self.window,color('bad'),(sx,sy),(sx,sy+22))
            if typ=='turret':
                self.animated_ring((sx,sy),23,'bad',marker_time,ring_phase,1.35,hover,1.75)
            if typ=='broken_terminal':pygame.draw.line(self.window,color('bad'),(sx-15,sy-15),(sx+15,sy+15),3)
            if hover:
                self.hover_object=o
                if not key:self.smooth_ring(obj_rect.center,max(18,size//2+8),'accent',235,2)
            if typ in marker_labels and (hover or distance((o['x'],o['y']),(w.player.x,w.player.y))<2.8 or typ in ('main_terminal','core','exit')):
                lab=marker_labels[typ]
                tw=self.font(10,True).size(lab)[0]
                bx=sx-(tw+10)//2
                by=sy-size//2-18
                self.rect((bx,by,tw+10,14),'panel','border',5)
                self.text(lab,sx,by+2,10,key if key else 'muted',True,center=True)
        for drone in w.drones:
            if (int(drone.x),int(drone.y)) not in room:continue
            sx,sy=self.px(drone.x,drone.y,camera)
            pygame.draw.ellipse(self.window,(0,0,0,125),(sx-24,sy+16,48,12))
            self.image('drone',sx,sy,56)
            self.animated_ring((sx,sy),25,'gold',marker_time,drone.x*.57+drone.y*.39,1.35,travel=2)
            state_label={'patrol':'ПАТРУЛЬ','search':'ПОИСК','chase':'ПРЕСЛЕД.','stunned':'ОГЛУШЁН'}.get(drone.state,'ДРОН')
            tone='bad' if drone.state=='chase' else 'gold' if drone.state=='search' else 'accent' if drone.state=='stunned' else 'muted'
            self.rect((sx-33,sy-35,66,14),'panel','border',5)
            self.text(state_label,sx,sy-33,9,tone,True,center=True)
            if drone.state in ('chase','search'):self.text('!',sx,sy-49,22,'bad',True,center=True)
        p=w.player;sx,sy=self.px(p.x,p.y,camera)
        pygame.draw.ellipse(self.window,(0,0,0,145),(sx-21,sy+18,42,13))
        if w.shielded:
            glow=pygame.Surface((110,110),pygame.SRCALPHA)
            pygame.draw.circle(glow,(67,219,236,45),(55,55),49)
            self.window.blit(glow,(sx-55,sy-55))
            self.smooth_ring((sx,sy),41,'good',155,2.5)
        if p.hp<30:sprite='alex_hurt'
        elif int(p.walk_anim)%2 and (pygame.key.get_pressed()[pygame.K_w] or pygame.key.get_pressed()[pygame.K_s] or pygame.key.get_pressed()[pygame.K_a] or pygame.key.get_pressed()[pygame.K_d]):sprite='alex_walk'
        else:sprite='alex_idle'
        self.image(sprite,sx,sy,55,61,flip=p.facing=='left')
        nx,ny=sx-51,sy-48+math.sin(w.time*3)*4
        self.image('nova',nx,ny,38)
        if w.lure_pos and w.time<w.lure_until and (int(w.lure_pos[0]),int(w.lure_pos[1])) in room:
            lx,ly=self.px(*w.lure_pos,camera);self.animated_ring((lx,ly),11,'gold',marker_time,w.lure_pos[0]+w.lure_pos[1],1.5,travel=1.5)
        n=w.nearby(r=1.4)
        if n:
            self.rect((max(10,min(VW-280,sx-120)),max(6,sy-86),258,27),'panel','border',5)
            self.text('[E] '+n['name'],max(18,min(VW-273,sx-112)),max(7,sy-82),15,'text',maxw=242)
        if self.hover_object:
            label=self.hover_object['name'] or self.hover_object['type']
            tw=self.font(14,True).size(label)[0]
            mx,my=mouse
            self.rect((mx+16,my+14,tw+18,28),'panel','border',6)
            self.text(label,mx+25,my+20,14,'text',True)
        self.window.set_clip(None)

    def draw_combat_effects(self,camera):
        """Render short event-driven combat animations below the fog layer."""
        events=getattr(self.world,'combat_events',())
        if not events:return
        if self.combat_layer.get_size()!=(VW,VH):
            self.combat_layer=pygame.Surface((VW,VH),pygame.SRCALPHA)
        layer=self.combat_layer;layer.fill((0,0,0,0))

        def limit(value):return max(0.0,min(1.0,float(value)))
        def ease(value):
            value=limit(value);return 1-(1-value)**3
        def blend(a,b,value):return a+(b-a)*value
        def point_between(a,b,value):return (blend(a[0],b[0],value),blend(a[1],b[1],value))
        def aa_ring(center,radius,rgba,segments=72):
            if radius<1:return
            points=[(center[0]+math.cos(math.tau*i/segments)*radius,center[1]+math.sin(math.tau*i/segments)*radius) for i in range(segments)]
            pygame.draw.aalines(layer,rgba,True,points)
        def impact(center,value,tone=(255,88,108)):
            value=limit(value);alpha=int(235*(1-value)**2);radius=7+28*ease(value)
            aa_ring(center,radius,(*tone,alpha),48)
            for ray in range(6):
                angle=ray*math.tau/6+value*.7
                inner=5+12*value;outer=inner+10*(1-value)
                pygame.draw.aaline(layer,(*tone,alpha),(center[0]+math.cos(angle)*inner,center[1]+math.sin(angle)*inner),(center[0]+math.cos(angle)*outer,center[1]+math.sin(angle)*outer))

        for event in events:
            duration=max(.05,float(event.get('duration',.5)))
            progress=limit((self.world.time-float(event.get('start',self.world.time)))/duration)
            source=self.px(*event['source'],camera)
            event_id=int(event.get('id',0))
            kind=event.get('kind')

            if kind=='turret_shot':
                target=self.px(*event['target'],camera)
                travel=ease(limit((progress-.06)/.58))
                head=point_between(source,target,travel)
                tail=point_between(source,target,max(0,travel-.22))
                beam_alpha=int(230*(1-progress*.72))
                pygame.draw.line(layer,(255,48,76,max(18,beam_alpha//3)),tail,head,10)
                pygame.draw.line(layer,(255,105,127,max(25,beam_alpha)),tail,head,4)
                pygame.draw.aaline(layer,(255,240,243,max(40,beam_alpha)),tail,head)
                if progress<.42:
                    charge=progress/.42
                    aa_ring(source,5+15*charge,(255,88,108,int(230*(1-charge))),40)
                    pygame.draw.circle(layer,(255,210,218,190),(round(source[0]),round(source[1])),max(2,round(7*(1-charge))))
                if progress>.36:impact(target,(progress-.36)/.64)

            elif kind=='drone_attack':
                target=self.px(*event['target'],camera)
                if progress<.28:
                    charge=progress/.28
                    aa_ring(source,22-12*ease(charge),(246,196,89,int(245*(1-charge*.35))),44)
                    pygame.draw.circle(layer,(255,92,112,150),(round(source[0]),round(source[1])),max(3,round(4+6*charge)))
                flight=ease(limit((progress-.16)/.60))
                if flight>0:
                    head=point_between(source,target,flight)
                    dx=head[0]-source[0];dy=head[1]-source[1];length=max(1,math.hypot(dx,dy));nx=-dy/length;ny=dx/length
                    bolt=[source]
                    for index in range(1,10):
                        frac=index/10
                        base=point_between(source,head,frac)
                        jitter=math.sin(index*2.31+event_id*.73+progress*18)*7*math.sin(math.pi*frac)
                        bolt.append((base[0]+nx*jitter,base[1]+ny*jitter))
                    bolt.append(head)
                    pygame.draw.lines(layer,(255,71,91,70),False,bolt,8)
                    pygame.draw.lines(layer,(244,184,80,205),False,bolt,3)
                    pygame.draw.aalines(layer,(255,242,190,245),False,bolt)
                    pygame.draw.circle(layer,(255,235,171,190),(round(head[0]),round(head[1])),6)
                if progress>.46:impact(target,(progress-.46)/.54,(245,181,78))

            elif kind=='player_pulse':
                max_radius=5.1*T
                radius=max_radius*ease(progress)
                center=(round(source[0]),round(source[1]))
                pulse_alpha=int(220*(1-progress)**.55)
                if radius>2:
                    pygame.draw.circle(layer,(61,224,242,max(8,pulse_alpha//5)),center,round(radius),10)
                    aa_ring(source,radius,(118,255,225,pulse_alpha),108)
                if progress>.12:
                    echo=ease((progress-.12)/.88);echo_radius=max_radius*echo
                    aa_ring(source,echo_radius,(64,203,239,int(135*(1-echo))),96)
                pygame.draw.circle(layer,(76,225,243,int(95*(1-progress))),center,max(4,round(42*(1-progress)+8)))
                for target_world in event.get('targets',()):
                    target=self.px(*target_world,camera)
                    fraction=min(1,distance(event['source'],target_world)/5.1)
                    hit_progress=1-(1-fraction)**(1/3)
                    local=(progress-hit_progress)/.30
                    if 0<=local<=1:
                        impact(target,local,(94,239,208))
                        pygame.draw.aaline(layer,(173,255,241,int(220*(1-local))),source,target)

        self.window.blit(layer,(0,0))

    def bar(self,label,value,x,y,width,tone):
        self.text(label,x,y,14,'muted',True)
        pygame.draw.rect(self.window,(37,61,79),(x,y+22,width,13),border_radius=5)
        pygame.draw.rect(self.window,color(tone),(x,y+22,max(0,int(width*min(1,value/100))),13),border_radius=5)
        self.text(f'{int(value)}%',x+width-45,y,14,'text',True)
    def hud(self):
        w=self.world;x=VW+12;pw=W-VW-24
        pygame.draw.rect(self.window,(3,9,15),(VW,0,W-VW,VH))
        pygame.draw.line(self.window,color('accent'),(VW+2,0),(VW+2,VH),2)
        self.rect((VW+8,8,W-VW-16,VH-16),'panel_alt','border',10)
        # Compact logo and deck identity.
        self.text('E C H O',x+10,17,29,'text',True)
        self.text('ПОСЛЕДНИЙ СИГНАЛ',x+12,51,11,'accent',True)
        self.text(f'A{w.level} / {w.title}',x+176,22,13,'muted',True,maxw=132)
        self.text('VOSK: '+self.voice.state,x+176,45,11,'good' if self.voice.state=='СЛУШАЕТ' else 'gold',True,maxw=132)
        pygame.draw.line(self.window,color('border'),(x+8,70),(x+pw-8,70),1)
        # Portrait cards echo the supplied reference while retaining live values.
        card_w=(pw-26)//2
        for i,(name,asset,value,tone,label) in enumerate((('ALEX','alex_idle',w.player.hp,'bad','ЗДОРОВЬЕ'),('НОВА','nova',w.player.energy,'accent','ЭНЕРГИЯ'))):
            cx=x+8+i*(card_w+8);self.rect((cx,78,card_w,72),'panel','border',7)
            pygame.draw.rect(self.window,(7,17,27),(cx+6,84,50,58),border_radius=5)
            self.image(asset,cx+31,113,44,48 if asset=='alex_idle' else 44)
            self.text(name,cx+63,87,14,'text',True)
            self.text(label,cx+63,108,9,'muted',True)
            for n in range(6):
                seg=(card_w-72)//6;active=n<math.ceil(value/100*6)
                pygame.draw.rect(self.window,color(tone) if active else color('border'),(cx+63+n*seg,129,max(3,seg-2),6),border_radius=2)
        # Alarm strip.
        self.text('УРОВЕНЬ ТРЕВОГИ',x+8,159,11,'muted',True)
        states=('НИЗКИЙ','НАБЛЮДЕНИЕ','ВЫСОКИЙ','КРИТИЧЕСКИЙ');al=w.alert_level
        self.text(states[al],x+pw-106,159,10,'bad' if al>1 else 'gold',True,maxw=98)
        for n in range(8):
            active=n<math.ceil(w.alert/12.5)
            pygame.draw.rect(self.window,color('bad') if active else color('border'),(x+8+n*((pw-18)//8),178,(pw-18)//8-3,8),border_radius=2)
        near_core=w.nearby('core',r=3.7) is not None
        self.text('СХЕМА ЯДЕР' if near_core else 'ТЕКУЩАЯ ЦЕЛЬ',x+8,199,11,'accent',True)
        self.rect((x+7,217,pw-14,74),'panel','border',7)
        if near_core:
            self.paragraph(w.clue,x+17,226,pw-34,11,14,'text',3)
            off,on=SOLUTIONS[w.level]
            self.text('ОТКЛ. '+COLORS[off],x+17,269,10,'bad',True)
            self.text('ВКЛ. '+COLORS[on],x+171,269,10,'good',True)
            tag='ИНЖЕНЕРНАЯ СХЕМА: '+w.clue
            if tag not in w.history:w.history.append(tag)
        else:
            self.paragraph(w.mission,x+17,229,pw-34,13,18,'text',3)
        self.text('МОДУЛИ НОВЫ',x+8,301,11,'accent',True)
        descriptions={'scan':'СКАН','hack':'ВЗЛОМ','shield':'ЩИТ','pulse':'ИМПУЛЬС','control':'УПРАВЛ.','memory':'ПАМЯТЬ'}
        cell_w=(pw-28)//3
        for i,(a,label) in enumerate(descriptions.items()):
            rx=x+8+(i%3)*(cell_w+4);ry=319+(i//3)*31
            self.rect((rx,ry,cell_w,25),'panel_soft' if a in w.abilities else 'background','good' if a in w.abilities else 'border',5)
            self.text(label,rx+cell_w//2,ry+6,10,'good' if a in w.abilities else 'muted',True,center=True)
        self.text('ТАКТИЧЕСКАЯ КАРТА',x+8,386,11,'accent',True)
        self.mini_map(x+45,428,5)
        inventory=f"H {w.inventory['medkit']}   B {w.inventory['battery']}   G {w.inventory['lure']}   КАРТА {w.inventory['keycard']}"
        self.text(inventory,x+10,599,11,'text',True,maxw=pw-20)
        self.text(f"ЗАГАДКИ {len(w.solved_puzzles)}/3  •  AI {w.ai_factor:.2f}x  •  {int(w.time)//60:02d}:{int(w.time)%60:02d}",x+10,620,11,'gold',True,maxw=pw-20)
        self.text(f'ОЧКИ {w.score+self.total_score:06d}',x+10,640,12,'muted',True)
        attempts=self.wallet_cache
        life_label='ЖИЗНИ: ∞' if attempts['unlimited'] else f'ЖИЗНИ: {attempts["lives"]}'
        self.text(life_label,x+pw-112,640,12,'good' if attempts['unlimited'] else 'gold',True,maxw=104)
        btn_y=665;bw=(pw-24)//3
        self.button('TAB',(x+8,btn_y,bw,29),lambda:setattr(self,'action_open',not self.action_open),small=True)
        self.button('N ЗАМЕТКИ',(x+12+bw,btn_y,bw,29),lambda:setattr(self,'notes_open',not self.notes_open),small=True)
        self.button('M КАРТА',(x+16+bw*2,btn_y,bw,29),lambda:setattr(self,'map_open',not self.map_open),small=True)
        self.text('WASD  •  SHIFT  •  E  •  V  •  F11',x+pw//2,710,10,'muted',True,center=True)
    def messages(self):
        w=self.world
        if not w.log:return
        _,text,typ=w.log[-1]
        tone={'danger':'bad','warning':'gold','success':'good','nova':'accent','voice':'muted','info':'text'}.get(typ,'text')
        width=min(530,VW-120)
        y=18
        self.rect((18,y,width,38),'panel','border',8)
        self.text(text,32,y+11,14,tone,True,maxw=width-28)

    def notes_panel(self):
        notes=self.world.history or ['Записей пока нет.']
        self.rect((86,60,VW-172,VH-120),'panel','accent',14)
        self.text('ЗАМЕТКИ И АРХИВЫ [N]',VW//2,86,24,'accent',True,center=True)
        self.text('Собранные записи корабля и подсказки к головоломкам',VW//2,117,15,'muted',center=True)
        y=152
        for i,note in enumerate(notes[-8:],1):
            h=56
            self.rect((112,y,VW-224,h),'panel_alt','border',9)
            self.text(f'{i}.',128,y+10,17,'accent',True)
            self.paragraph(note,162,y+10,VW-292,16,20,'text',2)
            y+=64
            if y>VH-120:break

    def mini_map(self,x,y,scale=7):
        w=self.world
        room=w.room_view_tiles()
        self.rect((x-13,y-25,w.width*scale+26,w.height*scale+36),'panel','border',7)
        for yy in range(w.height):
            for xx in range(w.width):
                tile=w.tiles[yy*w.width+xx]
                if (xx,yy) not in room:
                    shade=(11,20,29)
                else:
                    shade=(68,86,104) if tile in(2,5) else (31,54,72)
                pygame.draw.rect(self.window,shade,(x+xx*scale,y+yy*scale,scale,scale))
        for o in w.objects:
            if o.get('taken'):continue
            if (int(o['x']),int(o['y'])) not in room:continue
            sx=x+int(o['x']*scale);sy=y+int(o['y']*scale)
            shade=(84,215,217) if o['type']=='main_terminal' else (240,208,114) if o['type']=='core' else (119,230,160) if o['type']=='exit' else None
            if o['type']=='gate' and not w.gates[o['gate_id']]:shade=(239,114,125)
            if o['type'] in ('camera','turret'):shade=(239,80,98)
            if shade:pygame.draw.circle(self.window,shade,(sx,sy),4)
        for d in w.drones:
            if (int(d.x),int(d.y)) in room:pygame.draw.circle(self.window,(239,80,98),(x+int(d.x*scale),y+int(d.y*scale)),3)
        pygame.draw.circle(self.window,(241,250,252),(x+int(w.player.x*scale),y+int(w.player.y*scale)),5)

    def action_menu(self):
        self.rect((145,55,VW-290,VH-105),'panel','accent',13)
        self.text('ГОЛОСОВЫЕ КОМАНДЫ НОВЫ',VW//2,78,26,'accent',True,center=True)
        self.text('Произнеси команду либо нажми указанную клавишу. V — микрофон.',VW//2,114,16,'muted',center=True)
        for i,(cmd,label,key) in enumerate(ACTIONS):
            col=i%2;row=i//2
            bx=165+col*326;by=156+row*58
            self.button(f'[{key}] {label}',(bx,by,300,43),lambda c=cmd:self.select_action(c),small=True)
        self.text('Медпакет [H] • Батарея [B] • Маяк [G] • Взаимодействие [E]',VW//2,567,16,'muted',center=True)
        self.button('ЗАКРЫТЬ [TAB]',(VW//2-132,607,264,42),lambda:setattr(self,'action_open',False),small=True)
    def select_action(self,command):
        self.world.command(command)
        self.action_open=False
    def puzzle_panel(self):
        p=self.world.puzzles.get(self.puzzle_open)
        if not p:return
        overlay=pygame.Surface((VW,VH),pygame.SRCALPHA)
        overlay.fill((1,7,15,198))
        self.window.blit(overlay,(0,0))
        bx=max(36,VW//2-405);by=max(35,VH//2-276);bw=min(810,VW-72)
        self.rect((bx,by,bw,552),'panel','accent',17)
        self.text('ТЕРМИНАЛ  /  '+p['type'].upper(),bx+28,by+25,15,'accent',True)
        self.text(p['title'],bx+28,by+61,29,'text',True,maxw=bw-60)
        self.rect((bx+24,by+108,bw-48,132),'panel_alt','border',10)
        self.paragraph(p['question'],bx+38,by+124,bw-80,18,28,'text',4)
        for i,opt in enumerate(p['options']):
            self.button(f'{i+1}    {opt}',(bx+30,by+262+i*61,bw-60,50),lambda j=i:self.answer_puzzle(j),small=True)
        self.text('Выбор: клавиши 1, 2, 3 или мышь. Esc — выйти.',bx+30,by+502,15,'muted')

    def play(self):
        self.window.fill((7,16,27))
        camera=self.world_camera()
        self.draw_map_tiles(camera)
        self.draw_environment_details(camera)
        self.draw_cones(camera)
        self.draw_entities(camera)
        self.draw_practical_lights(camera)
        self.draw_combat_effects(camera)
        if CFG.get('fog_enabled',True):self.draw_fog(camera)
        self.hud();self.messages()
        self.rect((18,H-30,390,18),'panel','border',8)
        self.text('WASD • Shift • E • Tab • M • N • V • F11',28,H-27,11,'muted',True)
        if self.map_open:
            self.rect((VW//2-190,72,380,300),'panel','accent',12)
            self.mini_map(VW//2-140,123,7)
        if self.notes_open:self.notes_panel()
        if self.action_open:self.action_menu()
        if self.puzzle_open:self.puzzle_panel()
    def panel_base(self,title,subtitle=''):
        self.draw_background();self.text('ECHO',W//2,42,63,'accent',True,center=True)
        self.text(title,W//2,140,31,'text',True,center=True)
        if subtitle:self.text(subtitle,W//2,190,18,'muted',center=True)
    def pause(self):
        self.panel_base('ПАУЗА','Прогресс сохраняется при переходах и выходе в меню')
        self.button('ПРОДОЛЖИТЬ',(W//2-215,292,430,58),lambda:self.set_mode('play'),True)
        self.button('СОХРАНИТЬ И В МЕНЮ',(W//2-215,370,430,58),self.pause_to_menu)
        self.button('ПОМОЩЬ',(W//2-215,448,430,58),lambda:self.set_mode('help'))
        self.button('НАСТРОЙКИ',(W//2-215,526,430,52),lambda:self.set_mode('settings'))
    def pause_to_menu(self):self.save();self.mode='menu'
    def help(self):
        self.panel_base('ИНСТРУКЦИЯ УПРАВЛЕНИЯ','Побег из военного комплекса «Атлас-9»')
        info=[
            'WASD / стрелки — идти; Shift — бежать (создаёт шум); E / Space — подобрать или изучить.',
            'Tab — открыть список всех команд. Клавиши 1–0, - , =, Backspace повторяют голос.',
            'V — включить или выключить микрофон. F11 — полноэкранный режим. Без модели Vosk можно проходить с клавиатурой.',
            'M — карта. N — заметки. H — аптечка. B — батарея. G — отвлекающий маяк.',
            'Сначала ищи модули Новы и карту персонала. Затем найди главный терминал.',
            'Терминал: Подключение → Сканируй → Взломай → Открой.',
            'Энергетическое ядро: Сканируй → Отключи нужный контур → Активируй другой → Открой.',
            'Камеры вызывают турели. Дроны преследуют и атакуют. Прячься за стенами.',
            'Щит скрывает от сканеров 7 секунд; импульс оглушает ближайших дронов на 5 секунд.',
            'Логические терминалы: E — открыть, 1–3 — выбрать ответ. Для шлюзов A/B нужны задания.',
            'После потери жизни восстановление +1 бесплатно каждые 15 минут (до 3). В магазине — демо-покупки и Premium.',
            'Редактирование: карты — Tiled (*.tmj), персонажи — Inkscape (*.svg), сценарии — JSON.'
        ]
        y=229
        for line in info:
            self.rect((118,y-4,W-236,35),'panel_alt','border',6)
            self.text('• '+line,133,y+3,15,'text',maxw=W-275)
            y+=40
        self.button('НАЗАД',(W//2-180,716,360,46),lambda:self.set_mode('pause' if self.world and self.world.status=='playing' else 'menu'))
    def settings(self):
        self.panel_base('НАСТРОЙКИ','Звук, интерфейс и экран • изменения сохраняются сразу')
        self.rect((W//2-410,208,820,516),'panel','border',16)
        left=W//2-368
        rows=[
            ('Полноэкранный режим','fullscreen',CFG.get('fullscreen',True)),
            ('Музыкальное сопровождение','music_enabled',CFG.get('music_enabled',True)),
            ('Звуковые эффекты','sound_enabled',CFG.get('sound_enabled',True)),
            ('Шумы корабля / вентиляция','ambient_enabled',CFG.get('ambient_enabled',False)),
            ('Туман войны','fog_enabled',CFG.get('fog_enabled',True)),
        ]
        y=220
        for title,key,val in rows:
            self.rect((left,y,736,42),'panel_alt','border',9)
            self.text(title,left+20,y+10,17,'text',True)
            state='ВКЛ' if val else 'ВЫКЛ'
            self.button(state,(left+576,y+5,129,32),lambda k=key:self.set_toggle(k),filled=val,small=True)
            y+=46
        volume_rows=[
            ('Общая громкость','master_volume',70),
            ('Музыка','music_volume',50),
            ('Эффекты','sfx_volume',72),
            ('Сигналы Новы','voice_volume',70),
        ]
        y+=4
        for title,key,default in volume_rows:
            level=max(0,min(100,int(CFG.get(key,default))))
            self.rect((left,y,736,43),'panel_alt','border',9)
            self.text(title,left+20,y+10,17,'text',True)
            self.text(f'{level}%',left+329,y+10,17,'accent',True)
            self.button('−',(left+452,y+5,39,32),lambda k=key:self.adjust_value(k,-5),small=True)
            pygame.draw.rect(self.window,(36,60,78),(left+512,y+18,120,9),border_radius=4)
            pygame.draw.rect(self.window,color('accent'),(left+512,y+18,int(120*level/100),9),border_radius=4)
            self.button('+',(left+665,y+5,39,32),lambda k=key:self.adjust_value(k,5),small=True)
            y+=47
        y+=9
        self.button('СБРОСИТЬ СОХРАНЕНИЕ',(left,y,304,42),self.reset_progress,small=True)
        self.button('НАЗАД',(left+432,y,304,42),lambda:self.set_mode(getattr(self,'settings_return_mode','menu')),small=True)
        self.text('Музыка и эффекты — отдельные каналы. Vosk распознаёт микрофон независимо от этой громкости.',W//2,716,13,'muted',center=True)

    def reset_progress(self):
        self.storage.clear()
        self.total_score=0

    def records(self):
        self.panel_base('ТАБЛИЦА РЕЗУЛЬТАТОВ','SQLite • сохранение между запусками')
        self.text('СЕКТОР',170,264,17,'accent',True);self.text('ОЧКИ',365,264,17,'accent',True)
        self.text('ВРЕМЯ',570,264,17,'accent',True);self.text('ОБНАРУЖЕНИЯ',775,264,17,'accent',True)
        rows=self.storage.best()
        if not rows:self.text('Пока нет результатов. Пройди первый сектор!',W//2,342,23,'muted',center=True)
        for i,row in enumerate(rows):
            y=305+i*39
            self.rect((130,y-3,W-260,36),'panel_alt',None,4)
            self.text(str(row[0]),170,y+6,17);self.text(str(row[1]),365,y+6,17)
            self.text(str(row[2])+' c',570,y+6,17);self.text(str(row[3]),775,y+6,17)
            if row[4]:self.text(row[4],976,y+6,15,'gold')
        badges=self.storage.achievements()
        if badges:self.text('ДОСТИЖЕНИЯ:  '+ '  •  '.join(badges),W//2,684,16,'good',center=True,maxw=W-200)
        self.button('НАЗАД',(W//2-175,727,350,44),lambda:self.set_mode('menu'))
    def begin_payment(self,product,origin='store'):
        if product not in self.storage.DEMO_PRODUCTS:return
        self.payment_product=product
        self.payment_origin=origin
        self.payment_receipt=None
        self.mode='payment'
        self.sound('ui_click')

    def finish_payment(self):
        if self.payment_product not in self.storage.DEMO_PRODUCTS:return
        self.payment_receipt=self.storage.purchase_demo(self.payment_product)
        self.wallet_cache=self.storage.wallet()
        self.sound('puzzle_ok')
        self.mode='receipt'

    def close_receipt(self):
        origin=self.payment_origin
        if origin=='result' and self.world and self.world.status=='lost':
            self.mode='result'
        elif origin=='locked':
            self.mode='menu'
        else:self.mode='store'

    def locked(self):
        status=self.storage.recovery_status()
        available=status['unlimited'] or status['lives']>0
        title='ЖИЗНЬ ВОССТАНОВЛЕНА' if available else 'ПОПЫТКИ ЗАКОНЧИЛИСЬ'
        self.panel_base(title,'Бесплатно: +1 жизнь каждые 15 минут (максимум 3) • таймер работает офлайн')
        self.rect((W//2-410,254,820,409),'panel','border',16)
        self.text('МОЖНО ПРОДОЛЖАТЬ!' if available else 'ДОСТУП ВРЕМЕННО ЗАБЛОКИРОВАН',
                  W//2,291,25,'good' if available else 'bad',True,center=True)
        self.paragraph('Жизни сохраняются в SQLite. Можно подождать бесплатного восстановления или сразу воспользоваться демо-магазином без реальных платежей.',
                       W//2-345,345,690,18,27,'text',3)
        if status['unlimited']:
            timer='PREMIUM: БЕЗЛИМИТНЫЕ ПОПЫТКИ'
        elif available:
            timer=f'ВОССТАНОВЛЕНО • ДОСТУПНО ЖИЗНЕЙ: {status["lives"]}'
        else:
            timer=self.regeneration_label(status)
        self.text(timer,W//2,427,19,'good' if available else 'gold',True,center=True)
        self.button('КУПИТЬ 3 ЖИЗНИ  •  490 ₸',(W//2-320,465,640,51),lambda:self.begin_payment('lives_3','locked'),True)
        self.button('PREMIUM: БЕЗЛИМИТ  •  1 490 ₸',(W//2-320,530,640,50),lambda:self.begin_payment('premium_pass','locked'))
        if available:
            self.button('ПРОДОЛЖИТЬ ИГРУ',(W//2-235,602,470,46),lambda:self.set_mode('menu'),True)
        else:
            self.text('МОЖНО ЗАКРЫТЬ ИГРУ: ОТСЧЁТ ПРОДОЛЖИТСЯ',W//2,616,14,'muted',True,center=True)
        self.button('ГЛАВНОЕ МЕНЮ',(W//2-180,686,360,48),lambda:self.set_mode('menu'))

    def store(self):
        self.panel_base('МАГАЗИН / PREMIUM','Учебный прототип коммерциализации • покупки и цены только демонстрационные')
        self.rect((W//2-435,228,870,455),'panel','border',16)
        wallet=self.storage.recovery_status()
        lives='БЕЗЛИМИТ' if wallet['unlimited'] else str(wallet['lives'])
        self.text(f'ДОСТУПНО ЖИЗНЕЙ: {lives}',W//2,247,23,'good' if wallet['unlimited'] or wallet['lives'] else 'bad',True,center=True)
        self.text(self.regeneration_label(wallet),W//2,283,15,'gold' if wallet['next_life_in'] is not None else 'muted',True,center=True)
        self.rect((W//2-390,310,780,115),'panel_alt','border',10)
        self.text('НАБОР: +3 ЖИЗНИ',W//2-365,321,23,'text',True)
        self.text('Без срока действия • сохраняется при перезапуске',W//2-365,358,16,'muted')
        self.button('490 ₸  •  ДЕМО-ОПЛАТА',(W//2+100,350,268,52),lambda:self.begin_payment('lives_3','store'),True,small=True)
        self.rect((W//2-390,445,780,135),'panel_alt','border',10)
        self.text('PREMIUM PASS',W//2-365,460,23,'accent',True)
        self.text('Безлимитные жизни + отдельный Challenge Sector',W//2-365,491,17,'text')
        if not wallet['unlimited']:
            self.button('1 490 ₸  •  ДЕМО-ОПЛАТА',(W//2+100,516,268,48),lambda:self.begin_payment('premium_pass','store'),True,small=True)
        else:self.text('ПРИОБРЕТЕНО',W//2+155,528,19,'good',True)
        if self.storage.has_unlock('premium_challenge'):
            self.button('ИГРАТЬ CHALLENGE SECTOR',(W//2-260,613,520,43),lambda:self.start(challenge=True),small=True)
        else:
            self.text('Challenge Sector открывается с Premium Pass',W//2,619,16,'muted',center=True)
        self.button('НАЗАД',(W//2-180,699,360,48),lambda:self.set_mode('menu'))

    def payment(self):
        """Safe, clearly fictional checkout page; do not collect payment details."""
        product=self.storage.DEMO_PRODUCTS.get(self.payment_product)
        if not product:
            self.mode='store';return
        self.panel_base('ECHO PAY / ДЕМОКАССА','ИМИТАЦИЯ ПЛАТЕЖА  •  НЕ НАСТОЯЩИЙ ПЛАТЁЖ')
        self.rect((W//2-425,232,850,460),'panel','border',16)
        self.text('ОФОРМЛЕНИЕ ДЕМОЗАКАЗА',W//2,260,26,'accent',True,center=True)
        self.text('01  КОРЗИНА    /    02  ДЕМО-ОПЛАТА    /    03  ЧЕК',W//2,295,14,'muted',center=True)
        self.rect((W//2-360,319,720,180),'panel_alt','border',12)
        self.text('ТОВАР',W//2-333,339,14,'muted',True)
        self.text(product['name'],W//2-333,368,22,'text',True)
        self.text('ПОЛУЧАТЕЛЬ: ECHO / УЧЕБНЫЙ МАГАЗИН',W//2-333,410,16,'muted')
        self.text('СПОСОБ: TEST MODE  •  БЕЗ КАРТЫ И БАНКА',W//2-333,443,16,'muted')
        self.text(f'К ОПЛАТЕ:  {product["price_kzt"]:,} ₸'.replace(',',' '),W//2,519,29,'gold',True,center=True)
        self.text('Никакие реквизиты не вводятся и реальные деньги не списываются.',W//2,559,16,'muted',center=True)
        self.button('ПОДТВЕРДИТЬ ДЕМО-ОПЛАТУ',(W//2-300,606,600,54),self.finish_payment,True)
        self.button('ОТМЕНИТЬ',(W//2-180,707,360,44),lambda:self.set_mode(self.payment_origin))

    def receipt(self):
        receipt=self.payment_receipt
        if not receipt:
            self.mode='store';return
        self.panel_base('ОПЛАТА УСПЕШНА • ДЕМО','Покупка симулирована, реальные средства не использовались')
        self.rect((W//2-405,252,810,377),'panel','border',16)
        self.text('ЗАКАЗ ОБРАБОТАН ЛОКАЛЬНО',W//2,300,27,'good',True,center=True)
        self.text(receipt['name'],W//2,361,23,'text',True,center=True)
        self.text(f'СУММА: {receipt["price_kzt"]:,} ₸'.replace(',',' '),W//2,416,23,'gold',True,center=True)
        self.text('ЧЕК: '+receipt['receipt'],W//2,469,18,'muted',True,center=True)
        self.text('Данные сохранены в SQLite • офлайн • тестовый режим',W//2,526,16,'muted',center=True)
        self.button('ПРОДОЛЖИТЬ',(W//2-210,651,420,58),self.close_receipt,True)

    def result(self):
        w=self.world;won=w.status=='won'
        self.panel_base('СЕКТОР ПРОЙДЕН' if won else 'СИГНАЛ ПОТЕРЯН', 'Цель достигнута' if won else 'Алекс погиб. Нова сохранила последние данные.')
        self.rect((W//2-330,266,660,267),'panel','border',12)
        lines=[f'Очки сектора: {w.score}',f'Время: {int(w.time)//60:02d}:{int(w.time)%60:02d}',f'Обнаружения: {w.stats["detections"]}',f'Ошибки команд: {w.stats["errors"]}',f'Собранные предметы: {w.stats["items"]}']
        for i,line in enumerate(lines):self.text(line,W//2-245,288+i*43,22,'text')
        if not won:
            wallet=self.storage.recovery_status()
            count='БЕЗЛИМИТ' if wallet['unlimited'] else str(wallet['lives'])
            self.text('ОСТАЛОСЬ ЖИЗНЕЙ: '+count,W//2,523,19,'good' if self.storage.can_play() else 'bad',True,center=True)
            if wallet['next_life_in'] is not None:
                self.text(self.regeneration_label(wallet),W//2,550,13,'gold',True,center=True)
        if won or self.storage.can_play():
            self.button('ДАЛЬШЕ' if won else 'ПОВТОРИТЬ УРОВЕНЬ',(W//2-245,572,490,58),lambda:self.result_next(),True)
        else:
            self.button('КУПИТЬ ЖИЗНИ — 490 ₸ (ДЕМО)',(W//2-245,572,490,58),lambda:self.begin_payment('lives_3','result'),True)
        self.button('В МЕНЮ',(W//2-245,650,490,48),lambda:self.set_mode('menu'))
    def result_next(self):
        if self.world.status=='lost':
            if self.storage.can_play():self.restart()
            else:self.mode='locked'
        elif self.world.level==3 and not self.world.challenge:self.mode='ending_choice'
        else:self.next_level()
    def ending_choice(self):
        self.panel_base('ПРОТОКОЛ ЗАВЕРШЕНИЯ','Вы дошли до спасательной шлюпки. Как поступить с Цербером?')
        self.rect((W//2-402,266,804,360),'panel','border',12)
        self.text('1 • Отключить Цербера и улететь',W//2,306,24,'text',True,center=True)
        self.button('ФИНАЛ «СВОБОДА»',(W//2-325,365,650,56),lambda:self.choose_ending('Свобода'),True)
        self.text('2 • Изолировать опасный код, сохранив данные',W//2,448,21,'text',True,center=True)
        has='memory' in self.world.abilities
        self.button('ФИНАЛ «ПОСЛЕДНИЙ ПРОТОКОЛ»',(W//2-325,512,650,56),lambda:self.choose_ending('Последний протокол'),disabled=not has)
        if not has:self.text('Для второго финала необходим модуль памяти.',W//2,588,16,'gold',center=True)
    def credits(self):
        self.panel_base('ECHO: ПОСЛЕДНИЙ СИГНАЛ','КОНЕЦ ИСТОРИИ')
        self.rect((W//2-380,263,760,323),'panel','border',12)
        self.text('ФИНАЛ: '+self.game_ending.upper(),W//2,294,28,'accent',True,center=True)
        final='Алекс и Нова покидают Атлас-9. Цербер отключён. Но ответы на многие вопросы остаются за закрытыми дверями.' if self.game_ending=='Свобода' else 'Нова изолирует опасный протокол Цербера. Архив спасён, Алекс начинает восстанавливать свою память. Шлюпка уходит в космос.'
        self.paragraph(final,W//2-320,370,640,22,34,'text')
        self.text(f'ИТОГОВЫЕ ОЧКИ: {self.total_score}',W//2,520,22,'gold',True,center=True)
        self.button('ГЛАВНОЕ МЕНЮ',(W//2-230,642,460,59),lambda:self.set_mode('menu'),True)
    def draw(self):
        self.buttons.clear()
        if self.mode=='menu':self.menu()
        elif self.mode=='play':self.play()
        elif self.mode=='pause':self.pause()
        elif self.mode=='help':self.help()
        elif self.mode=='records':self.records()
        elif self.mode=='settings':self.settings()
        elif self.mode=='store':self.store()
        elif self.mode=='locked':self.locked()
        elif self.mode=='payment':self.payment()
        elif self.mode=='receipt':self.receipt()
        elif self.mode=='result':self.result()
        elif self.mode=='ending_choice':self.ending_choice()
        elif self.mode=='credits':self.credits()
        pygame.display.flip()
    def run(self):
        while self.running:
            dt=self.clock.tick(CFG.get('fps',60))/1000
            for event in pygame.event.get():self.event(event)
            self.tick(dt);self.draw()
        self.save();self.voice.stop();self.audio.stop();pygame.quit()

def main():
    try:Game().run()
    except Exception as exc:
        import traceback;traceback.print_exc()
        try:
            (ROOT/'crash_log.txt').write_text(traceback.format_exc(),encoding='utf-8')
            print('Отчёт сохранён в crash_log.txt')
        except OSError:pass
        raise
