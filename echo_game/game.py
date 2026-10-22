"""Pygame UI, drawing and input. Data/art not hardcoded: see maps/*.tmj and assets/.
Game logic (AI, sensor geometry, objectives) lives in world.py for headless tests.
"""
import math, sys
from pathlib import Path
import pygame
from .world import World,ROOT,distance,COLORS
from .voice import VoiceListener
from .storage import Storage
from .commands import ACTIONS
from .config import read_settings, save_settings

CFG=read_settings()
W,H=int(CFG['screen_width']),int(CFG['screen_height'])
HUD_W=344
VW=W-HUD_W
VH=H
T=48
PAL=CFG['palette']
def color(key):return pygame.Color(PAL.get(key,key))

class Game:
    def __init__(self):
        global W,H,VW,VH,PAL
        pygame.init()
        try:pygame.display.set_caption('ECHO: Последний сигнал • Атлас-9')
        except Exception:pass
        flags=0
        if CFG.get('fullscreen',True):
            info=pygame.display.Info()
            W,H=info.current_w,info.current_h
            flags=pygame.FULLSCREEN
        else:
            W,H=int(CFG['screen_width']),int(CFG['screen_height'])
        VW=max(860,W-HUD_W);VH=H
        PAL=CFG['palette']
        self.window=pygame.display.set_mode((W,H),flags)
        self.clock=pygame.time.Clock();self.running=True
        self.fullscreen=bool(flags & pygame.FULLSCREEN)
        self.sounds={};self.sound_log_counter=0;self.last_alert_level=0
        self.fonts={}
        self.mode='menu';self.world=None
        self.storage=Storage();self.voice=VoiceListener()
        self.assets={};self.cover=None;self.tiles=None
        self.buttons=[];self.action_open=False;self.map_open=False;self.notes_open=False
        self.message_note='';self.total_score=0;self.game_ending='';self.prev_level=1
        self.hover_object=None
        self.load_art()
        self.load_sounds()
        self.apply_audio_settings()
    def load_sounds(self):
        try:
            if pygame.mixer.get_init() is None:pygame.mixer.init()
            for wav in (ROOT/"assets"/"audio").glob("*.wav"):
                self.sounds[wav.stem]=pygame.mixer.Sound(str(wav))
        except pygame.error:pass  # Audio devices are optional; the game remains playable

    def apply_audio_settings(self):
        master=max(0,min(100,int(CFG.get('master_volume',70))))/100
        for key,snd in self.sounds.items():
            base=.10 if key=='ambient' else .34
            snd.set_volume(base*master if CFG.get('sound_enabled',True) else 0)
        try:
            if 'ambient' in self.sounds:
                self.sounds['ambient'].stop()
                if CFG.get('sound_enabled',True) and CFG.get('ambient_enabled',False):
                    self.sounds['ambient'].play(-1)
        except pygame.error:
            pass

    def persist_settings(self):
        global CFG,PAL
        CFG=save_settings(CFG)
        PAL=CFG['palette']
        self.apply_audio_settings()

    def sound(self,key):
        try:
            if CFG.get("sound_enabled",True) and key in self.sounds:self.sounds[key].play()
        except pygame.error:pass
    def toggle_fullscreen(self):
        global W,H,VW,VH
        self.fullscreen=not self.fullscreen
        if self.fullscreen:
            info=pygame.display.Info()
            W,H=info.current_w,info.current_h
            self.window=pygame.display.set_mode((W,H),pygame.FULLSCREEN)
        else:
            W,H=int(CFG['screen_width']),int(CFG['screen_height'])
            self.window=pygame.display.set_mode((W,H))
        VW=max(860,W-HUD_W);VH=H
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
        try:self.cover=pygame.image.load(str(ROOT/'assets/ui/cover.png')).convert_alpha()
        except pygame.error:pass
    def text(self,s,x,y,size=21,tone='text',bold=False,maxw=0,center=False):
        surface=self.font(size,bold).render(str(s),True,color(tone))
        if maxw and surface.get_width()>maxw:
            while size>11 and surface.get_width()>maxw:
                size-=1;surface=self.font(size,bold).render(str(s),True,color(tone))
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
        frame=pygame.transform.smoothscale(img,(int(width),int(height)))
        if flip:frame=pygame.transform.flip(frame,True,False)
        self.window.blit(frame,(int(cx-width/2),int(cy-height/2)))
    def start(self,resume=False,challenge=False):
        snapshot=self.storage.load() if resume else None
        if challenge:
            self.world=World(2,abilities=['scan','hack','shield','pulse','control','memory'],inventory={'medkit':2,'battery':2,'keycard':1,'lure':2},challenge=True)
        elif snapshot:
            self.world=World(snapshot['level'],snapshot.get('abilities',[]),stats=snapshot.get('stats'),inventory=snapshot.get('inventory'))
            self.total_score=snapshot.get('total_score',0)
        else:
            self.world=World(1);self.total_score=0;self.storage.clear()
        self.mode='play';self.action_open=False;self.map_open=False;self.notes_open=False
        self.sound_log_counter=self.world.log_counter;self.last_alert_level=0
        if not challenge:self.save()
    def save(self):
        if self.world and not self.world.challenge:
            snap=self.world.snapshot();snap['total_score']=self.total_score;self.storage.save(snap)
    def restart(self):
        if self.world:
            w=self.world
            self.world=World(w.level,abilities=w.abilities,inventory={'medkit':1,'battery':1,'keycard':0,'lure':0},challenge=w.challenge)
            self.sound_log_counter=self.world.log_counter;self.last_alert_level=0
            self.mode='play';self.action_open=False
    def next_level(self):
        w=self.world
        if not w:return
        self.storage.record(w,self.game_ending if w.level==3 else '')
        self.total_score+=w.score
        if w.challenge:
            self.mode='menu';return
        if w.level<3:
            self.world=World(w.level+1,abilities=w.abilities,stats=w.stats,inventory={'medkit':max(1,w.inventory['medkit']),'battery':max(1,w.inventory['battery']),'keycard':0,'lure':w.inventory['lure']})
            self.mode='play';self.sound_log_counter=self.world.log_counter;self.last_alert_level=0;self.save()
        else:
            self.storage.clear();self.mode='credits'
    def handle_click(self,pos):
        for rect,cb in reversed(self.buttons):
            if rect.collidepoint(pos):cb();break
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
            if self.mode=='play':self.mode='pause';self.save()
            elif self.mode=='pause':self.mode='play'
            else:self.mode='menu'
            return
        if self.mode=='play':
            w=self.world
            if evt.key in (pygame.K_e,pygame.K_SPACE):w.interact();return
            if evt.key==pygame.K_TAB:self.action_open=not self.action_open;return
            if evt.key==pygame.K_m:self.map_open=not self.map_open;return
            if evt.key==pygame.K_n:self.notes_open=not self.notes_open;return
            if evt.key==pygame.K_v:
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
                else:self.restart()
        if self.mode=='ending_choice':
            if evt.key==pygame.K_1:self.choose_ending('Свобода')
            if evt.key==pygame.K_2 and 'memory' in self.world.abilities:self.choose_ending('Последний протокол')
    def choose_ending(self,value):
        self.game_ending=value;self.world.ending=value;self.next_level()
    def read_voice(self):
        for tag,payload in self.voice.poll():
            if tag=='command' and self.world and self.mode=='play':self.world.command(payload,'voice')
            elif tag=='notice' and self.world:self.world.message(payload,'info')
            elif tag=='heard' and self.world:self.world.message('РАСПОЗНАНО: '+payload,'voice')
    def tick(self,dt):
        self.read_voice()
        if self.mode!='play' or not self.world:return
        if self.action_open or self.map_open or self.notes_open:return
        keys=pygame.key.get_pressed()
        dx=int(keys[pygame.K_d] or keys[pygame.K_RIGHT])-int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy=int(keys[pygame.K_s] or keys[pygame.K_DOWN])-int(keys[pygame.K_w] or keys[pygame.K_UP])
        self.world.step(dt,dx,dy,bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]))
        self.audio_events()
        if self.world.status!='playing':self.mode='result';self.save()
    def audio_events(self):
        if self.world is None:return
        entries=self.world.log
        new_count=min(max(0,self.world.log_counter-self.sound_log_counter),len(entries))
        for _,msg,kind in (entries[-new_count:] if new_count else []):
            t=msg.lower()
            if 'модуль' in t and 'установлен' in t:self.sound('module')
            elif 'найдено' in t:self.sound('pickup')
            elif 'шлюз' in t and 'открыт' in t:self.sound('door')
            elif 'сканирован' in t:self.sound('scan')
            elif 'взлом' in t:self.sound('hack')
            elif 'импульс' in t and 'оглуш' in t:self.sound('pulse')
            elif kind=='danger':self.sound('damage')
        self.sound_log_counter=self.world.log_counter
        if self.last_alert_level<2<=self.world.alert_level:self.sound('alarm')
        self.last_alert_level=self.world.alert_level
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
            img=pygame.transform.smoothscale(self.cover,(W,713));self.window.blit(img,(0,0))
            tint=pygame.Surface((W,H),pygame.SRCALPHA);tint.fill((4,13,24,60));self.window.blit(tint,(0,0))
        self.rect((42,285,500,417),'panel','border',14)
        self.text('АТЛАС-9  /  ЭВАКУАЦИЯ',77,309,17,'accent',True)
        self.paragraph('Ты очнулся на заброшенном военном корабле. Восстанови Нову, избегай охраны и найди спасательную шлюпку.',77,353,425,20,28,'text')
        self.button('НОВАЯ ИГРА',(73,454,432,51),lambda:self.start(),True)
        self.button('ПРОДОЛЖИТЬ',(73,514,210,48),lambda:self.start(resume=True),disabled=self.storage.load() is None,small=True)
        self.button('КАК ИГРАТЬ',(296,514,209,48),lambda:self.set_mode('help'),small=True)
        self.button('РЕКОРДЫ',(73,574,210,48),lambda:self.set_mode('records'),small=True)
        self.button('НАСТРОЙКИ',(296,574,209,48),lambda:self.set_mode('settings'),small=True)
        self.button('PREMIUM',(73,634,210,44),lambda:self.set_mode('store'),small=True)
        self.button('ВЫХОД',(296,634,209,44),lambda:setattr(self,'running',False),small=True)
        self.text('v1.0 • Авторские SVG / карты Tiled / Python + Vosk',23,757,15,'muted')
    def set_mode(self,value):self.mode=value
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
                base=(25,43,63) if (x+y)%2==0 else (28,47,68)
                pygame.draw.rect(self.window,base,(xx,yy,T,T))
                pygame.draw.rect(self.window,(34,58,82),(xx,yy,T,T),1)
                if gid in (2,5):
                    fill=(61,82,103) if gid==2 else (73,95,116)
                    pygame.draw.rect(self.window,fill,(xx+2,yy+2,T-4,T-4),border_radius=4)
                    pygame.draw.rect(self.window,(143,176,202),(xx+3,yy+3,T-6,T-6),2,border_radius=4)
                    pygame.draw.rect(self.window,(91,114,138),(xx+8,yy+10,T-16,5),border_radius=3)
                else:
                    if gid==3:
                        pygame.draw.circle(self.window,(70,98,126),(xx+T//2,yy+T//2),10,2)
                    elif gid==4:
                        pygame.draw.rect(self.window,(82,112,138),(xx+12,yy+8,24,32),2,border_radius=2)
                        for k in range(3):pygame.draw.line(self.window,(110,145,170),(xx+15,yy+14+k*7),(xx+33,yy+14+k*7),2)
                    elif gid in (6,7,8):
                        pygame.draw.line(self.window,(88,152,180),(xx+10,yy+24),(xx+38,yy+24),3)
        self.window.set_clip(None)

    def draw_fog(self,camera):
        w=self.world
        overlay=pygame.Surface((VW,VH),pygame.SRCALPHA)
        overlay.fill((3,8,15,238))
        px,py=w.player.x,w.player.y
        radius=6.8
        sx=max(0,int(px-radius-1));ex=min(w.width,int(px+radius+2))
        sy=max(0,int(py-radius-1));ey=min(w.height,int(py+radius+2))
        for gy in range(sy,ey):
            for gx in range(sx,ex):
                cx,cy=gx+0.5,gy+0.5
                if distance((px,py),(cx,cy))<=radius and w.ray_clear(px,py,cx,cy):
                    rx=int(gx*T-camera[0]);ry=int(gy*T-camera[1])
                    pygame.draw.rect(overlay,(0,0,0,0),(rx,ry,T,T))
        psx,psy=self.px(px,py,camera)
        pygame.draw.circle(overlay,(0,0,0,0),(psx,psy),48)
        self.window.blit(overlay,(0,0))

    def draw_cones(self,camera):
        w=self.world
        layer=pygame.Surface((VW,VH),pygame.SRCALPHA)
        def sector(sx,sy,angle,radius,width,rgb,opacity,samples=80,outline=None):
            origin=self.px(sx,sy,camera)
            pts=[origin]
            for i in range(samples+1):
                theta=math.radians(angle-width/2+i*width/max(1,samples))
                pts.append(self.px(sx+math.cos(theta)*radius,sy+math.sin(theta)*radius,camera))
            if len(pts)>2:
                pygame.draw.polygon(layer,(*rgb,opacity),pts)
                if outline and width<360:
                    pygame.draw.aalines(layer,(*outline,210),False,pts[1:])
                    pygame.draw.aaline(layer,(*outline,210),origin,pts[1])
                    pygame.draw.aaline(layer,(*outline,210),origin,pts[-1])
        for o in w.objects:
            if o['type']=='camera' and w.time>=w.cam_disable_until:
                angle=o.get('angle',0)+math.sin(w.time*.85+o['x'])*o.get('sweep',50)
                sector(o['x'],o['y'],angle,o.get('range',7),64,(242,87,108),46,samples=96,outline=(255,157,170))
        for drone in w.drones:
            if w.time>=drone.stunned:
                pos=self.px(drone.x,drone.y,camera)
                pygame.draw.circle(layer,(245,197,95,18),pos,int(min(3.7,drone.vision)*T))
                pygame.draw.circle(layer,(245,197,95,70),pos,int(min(3.7,drone.vision)*T),1)
        self.window.blit(layer,(0,0))

    def draw_entities(self,camera):
        w=self.world
        self.window.set_clip(pygame.Rect(0,0,VW,VH))
        mouse=pygame.mouse.get_pos()
        self.hover_object=None
        names={'main_terminal':'terminal','aux_terminal':'terminal','broken_terminal':'terminal','exit':'exit','core':'core','module':'module','medkit':'medkit','battery':'battery','keycard':'keycard','lure':'lure','note':'note','camera':'camera','turret':'turret'}
        marker_colors={
            'module':'good','medkit':'bad','battery':'accent','keycard':'gold','lure':'gold','note':'muted',
            'main_terminal':'accent','aux_terminal':'accent','core':'gold','exit':'good','camera':'bad','turret':'bad'
        }
        marker_labels={
            'module':'МОДУЛЬ','medkit':'АПТЕЧКА','battery':'БАТАРЕЯ','keycard':'КЛЮЧ','lure':'МАЯК',
            'note':'ЗАПИСЬ','main_terminal':'ТЕРМИНАЛ','aux_terminal':'КОНСОЛЬ','core':'ЯДРО','exit':'ВЫХОД',
            'camera':'КАМЕРА','turret':'ТУРЕЛЬ'
        }
        for o in w.objects:
            if o['taken'] or o['type']=='spawn':continue
            typ=o['type'];sx,sy=self.px(o['x'],o['y'],camera)
            if not (-50<sx<VW+50 and -50<sy<VH+50):continue
            if typ=='gate':
                if w.gates[o['gate_id']]:
                    pygame.draw.circle(self.window,color('good'),(sx,sy),8,2)
                    self.text('ОТКР.',sx,sy-18,10,'good',True,center=True)
                    continue
                self.image('gate',sx,sy,46,46)
                pygame.draw.rect(self.window,(10,28,42),(sx-18,sy-30,36,14),border_radius=5)
                self.text('ШЛЮЗ',sx,sy-29,9,'bad',True,center=True)
                continue
            asset=names.get(typ)
            if not asset:continue
            size=42 if typ not in ('camera','turret') else 46
            pulse=int((math.sin(w.time*3+o['id'])*0.5+0.5)*3)
            self.image(asset,sx,sy,size)
            obj_rect=pygame.Rect(int(sx-size/2),int(sy-size/2),size,size)
            hover=obj_rect.collidepoint(mouse)
            key=marker_colors.get(typ)
            if key and typ not in ('camera','turret'):
                pygame.draw.circle(self.window,color(key),(sx,sy),size//2+6+pulse,1)
            if typ=='camera':
                pygame.draw.circle(self.window,color('bad'),(sx,sy),22,1)
                pygame.draw.line(self.window,color('bad'),(sx,sy),(sx,sy+22),1)
            if typ=='turret':
                pygame.draw.circle(self.window,color('bad'),(sx,sy),24,1)
            if typ in ('main_terminal','core','exit'):
                pygame.draw.circle(self.window,color('accent' if typ!='core' else 'gold'),(sx,sy),25,2)
            if typ=='broken_terminal':pygame.draw.line(self.window,color('bad'),(sx-15,sy-15),(sx+15,sy+15),3)
            if hover:
                self.hover_object=o
                pygame.draw.circle(self.window,color('accent'),obj_rect.center,max(18,size//2+8),2)
            if typ in marker_labels:
                lab=marker_labels[typ]
                tw=self.font(10,True).size(lab)[0]
                bx=sx-(tw+10)//2
                by=sy-size//2-18
                self.rect((bx,by,tw+10,14),'panel','border',5)
                self.text(lab,sx,by+2,10,key if key else 'muted',True,center=True)
        for drone in w.drones:
            sx,sy=self.px(drone.x,drone.y,camera)
            self.image('drone',sx,sy,48)
            pygame.draw.circle(self.window,color('gold'),(sx,sy),26,1)
            state_label={'patrol':'ПАТРУЛЬ','search':'ПОИСК','chase':'ПРЕСЛЕД.','stunned':'ОГЛУШЁН'}.get(drone.state,'ДРОН')
            tone='bad' if drone.state=='chase' else 'gold' if drone.state=='search' else 'accent' if drone.state=='stunned' else 'muted'
            self.rect((sx-33,sy-35,66,14),'panel','border',5)
            self.text(state_label,sx,sy-33,9,tone,True,center=True)
            if drone.state in ('chase','search'):self.text('!',sx,sy-49,22,'bad',True,center=True)
        p=w.player;sx,sy=self.px(p.x,p.y,camera)
        if w.shielded:
            glow=pygame.Surface((110,110),pygame.SRCALPHA)
            pygame.draw.circle(glow,(67,219,236,45),(55,55),49)
            pygame.draw.circle(glow,(105,255,239,135),(55,55),41,3)
            self.window.blit(glow,(sx-55,sy-55))
        if p.hp<30:sprite='alex_hurt'
        elif int(p.walk_anim)%2 and (pygame.key.get_pressed()[pygame.K_w] or pygame.key.get_pressed()[pygame.K_s] or pygame.key.get_pressed()[pygame.K_a] or pygame.key.get_pressed()[pygame.K_d]):sprite='alex_walk'
        else:sprite='alex_idle'
        self.image(sprite,sx,sy,47,52,flip=p.facing=='left')
        nx,ny=sx-45,sy-43+math.sin(w.time*3)*4
        self.image('nova',nx,ny,32)
        if w.lure_pos and w.time<w.lure_until:
            lx,ly=self.px(*w.lure_pos,camera);pygame.draw.circle(self.window,color('gold'),(lx,ly),12,2)
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

    def bar(self,label,value,x,y,width,tone):
        self.text(label,x,y,14,'muted',True)
        pygame.draw.rect(self.window,(37,61,79),(x,y+22,width,13),border_radius=5)
        pygame.draw.rect(self.window,color(tone),(x,y+22,max(0,int(width*min(1,value/100))),13),border_radius=5)
        self.text(f'{int(value)}%',x+width-45,y,14,'text',True)
    def hud(self):
        w=self.world;x=VW+12;pw=W-VW-24
        self.rect((VW,0,W-VW,VH),'panel',None,0)
        self.rect((VW+8,10,W-VW-16,VH-20),'panel_alt','border',16)
        self.text('ECHO / НОВА',x+10,24,28,'accent',True)
        self.text(f'СЕКТОР {w.level}  •  {w.title}',x+10,63,15,'muted',True,maxw=pw-20)
        self.text(f'МИКРОФОН: {self.voice.state}',x+10,89,13,'good' if self.voice.state=='СЛУШАЕТ' else 'gold',True,maxw=pw-20)
        self.bar('ЗДОРОВЬЕ',w.player.hp,x+10,118,pw-24,'bad')
        self.bar('ЭНЕРГИЯ НОВЫ',w.player.energy,x+10,170,pw-24,'accent')
        self.bar('ТРЕВОГА',w.alert,x+10,222,pw-24,'gold')
        self.text('ТЕКУЩАЯ ЦЕЛЬ',x+10,280,14,'accent',True)
        self.rect((x+9,304,pw-18,94),'panel','border',10)
        self.paragraph(w.mission,x+22,319,pw-45,17,22,'text',4)
        self.text('МОДУЛИ НОВЫ',x+10,421,14,'accent',True)
        descriptions={'scan':'СКАН','hack':'ВЗЛОМ','shield':'ЩИТ','pulse':'ИМПУЛЬС','control':'УПРАВЛ.','memory':'ПАМЯТЬ'}
        cell_w=(pw-28)//3
        for i,(a,label) in enumerate(descriptions.items()):
            rx=x+10+(i%3)*(cell_w+4);ry=447+(i//3)*42
            self.rect((rx,ry,cell_w,32),'panel_soft' if a in w.abilities else 'background','good' if a in w.abilities else 'border',8)
            self.text(label,rx+cell_w//2,ry+8,12,'good' if a in w.abilities else 'muted',True,center=True)
        self.text('ИНВЕНТАРЬ',x+10,541,14,'accent',True)
        self.text(f"[H] Аптечка: {w.inventory['medkit']}",x+12,566,17)
        self.text(f"[B] Батарея: {w.inventory['battery']}",x+12,593,17)
        self.text(f"[G] Маяк: {w.inventory['lure']}",x+12,620,16)
        self.text(f"Ключ-карта: {w.inventory['keycard']}",x+140,620,16)
        info_y=VH-140
        self.text(f'ОЧКИ  {w.score+self.total_score:06d}',x+10,info_y,20,'gold',True)
        self.text(f'ВРЕМЯ  {int(w.time)//60:02d}:{int(w.time)%60:02d}',x+10,info_y+28,17,'muted')
        btn_y=VH-104
        self.button('КОМАНДЫ [TAB]',(x+10,btn_y,pw-20,30),lambda:setattr(self,'action_open',not self.action_open),small=True)
        self.button('ЗАМЕТКИ [N]',(x+10,btn_y+34,pw-20,30),lambda:setattr(self,'notes_open',not self.notes_open),small=True)
        self.button('КАРТА [M]',(x+10,btn_y+68,pw-20,30),lambda:setattr(self,'map_open',not self.map_open),small=True)
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
        self.rect((x-13,y-35,w.width*scale+26,w.height*scale+56),'panel','border',10)
        self.text('КАРТА СЕКТОРА • [M]',x,y-24,15,'accent',True)
        px,py=w.player.x,w.player.y
        radius=7.2
        for yy in range(w.height):
            for xx in range(w.width):
                cx,cy=xx+0.5,yy+0.5
                visible=distance((px,py),(cx,cy))<=radius and w.ray_clear(px,py,cx,cy)
                if not visible:
                    shade=(11,20,29)
                else:
                    tile=w.tiles[yy*w.width+xx]
                    shade=(68,86,104) if tile in(2,5) else (31,54,72)
                pygame.draw.rect(self.window,shade,(x+xx*scale,y+yy*scale,scale,scale))
        for o in w.objects:
            if o.get('taken'):continue
            visible=distance((px,py),(o['x'],o['y']))<=radius and w.ray_clear(px,py,o['x'],o['y'])
            if not visible:continue
            sx=x+int(o['x']*scale);sy=y+int(o['y']*scale)
            shade=(84,215,217) if o['type']=='main_terminal' else (240,208,114) if o['type']=='core' else (119,230,160) if o['type']=='exit' else None
            if o['type']=='gate' and not w.gates[o['gate_id']]:shade=(239,114,125)
            if shade:pygame.draw.circle(self.window,shade,(sx,sy),4)
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
    def play(self):
        self.window.fill((7,16,27))
        camera=self.world_camera()
        self.draw_map_tiles(camera)
        self.draw_cones(camera)
        self.draw_entities(camera)
        if CFG.get('fog_enabled',True):self.draw_fog(camera)
        self.hud();self.messages()
        self.rect((18,H-30,390,18),'panel','border',8)
        self.text('WASD • Shift • E • Tab • M • N • V • F11',28,H-27,11,'muted',True)
        if self.map_open:
            self.rect((VW//2-190,72,380,300),'panel','accent',12)
            self.mini_map(VW//2-140,123,7)
        if self.notes_open:self.notes_panel()
        if self.action_open:self.action_menu()
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
            'Редактирование: карты — Tiled (*.tmj), персонажи — Inkscape (*.svg), диалоги — JSON.'
        ]
        y=237
        for line in info:
            self.rect((118,y-4,W-236,38),'panel_alt','border',6)
            self.text('• '+line,133,y+3,16,'text',maxw=W-275)
            y+=46
        self.button('НАЗАД',(W//2-180,716,360,46),lambda:self.set_mode('pause' if self.world and self.world.status=='playing' else 'menu'))
    def settings(self):
        self.panel_base('НАСТРОЙКИ','Удобство управления, звук и визуальные параметры')
        self.rect((W//2-410,228,820,430),'panel','border',16)
        left=W//2-368
        rows=[
            ('Полноэкранный режим','fullscreen',CFG.get('fullscreen',True)),
            ('Звуковые эффекты','sound_enabled',CFG.get('sound_enabled',True)),
            ('Фоновый ambient','ambient_enabled',CFG.get('ambient_enabled',False)),
            ('Туман войны','fog_enabled',CFG.get('fog_enabled',True)),
        ]
        y=270
        for title,key,val in rows:
            self.rect((left,y,736,58),'panel_alt','border',10)
            self.text(title,left+24,y+17,20,'text',True)
            state='ВКЛ' if val else 'ВЫКЛ'
            self.button(state,(left+560,y+12,150,34),lambda k=key:self.set_toggle(k),filled=val,small=True)
            y+=72
        # volume row
        self.rect((left,y,736,76),'panel_alt','border',10)
        self.text('Громкость',left+24,y+18,20,'text',True)
        self.text(f"{CFG.get('master_volume',70)}%",left+318,y+19,20,'accent',True)
        self.button('−',(left+500,y+16,52,36),lambda:self.adjust_value('master_volume',-10),small=True)
        self.button('+',(left+658,y+16,52,36),lambda:self.adjust_value('master_volume',10),small=True)
        pygame.draw.rect(self.window,(36,60,78),(left+560,y+29,88,10),border_radius=5)
        fill=max(0,int(88*CFG.get('master_volume',70)/100))
        pygame.draw.rect(self.window,color('accent'),(left+560,y+29,fill,10),border_radius=5)
        y+=98
        self.button('СБРОСИТЬ СОХРАНЕНИЕ',(left,y,300,44),self.reset_progress,small=True)
        self.button('НАЗАД',(left+436,y,300,44),lambda:self.set_mode('pause' if self.world and self.mode!='menu' and self.world and self.world.status=='playing' else 'menu'),small=True)
        self.text('Изменения сохраняются сразу в файле assets/ui/theme.json',W//2,680,15,'muted',center=True)

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
    def store(self):
        self.panel_base('PREMIUM / CHALLENGE SECTOR','Учебная демонстрация коммерциализации • без реальных платежей')
        self.rect((W//2-390,245,780,340),'panel','border',16)
        self.text('ДОПОЛНИТЕЛЬНЫЙ СЕКТОР',W//2,272,28,'accent',True,center=True)
        self.paragraph('Особое испытание: усиленные дроны, оборудование Новы разблокировано сразу. Доступ открывается демонстрационной покупкой без денег.',W//2-340,337,680,22,32,'text')
        bought=self.storage.has_unlock('premium_challenge')
        self.text('СТАТУС: '+('ОТКРЫТ' if bought else 'ЗАБЛОКИРОВАН'),W//2,470,22,'good' if bought else 'gold',True,center=True)
        if not bought:self.button('РАЗБЛОКИРОВАТЬ (ДЕМО)',(W//2-235,526,470,54),lambda:self.storage.unlock('premium_challenge'),True)
        else:self.button('ИГРАТЬ ИСПЫТАНИЕ',(W//2-235,526,470,54),lambda:self.start(challenge=True),True)
        self.button('НАЗАД',(W//2-180,703,360,48),lambda:self.set_mode('menu'))
    def result(self):
        w=self.world;won=w.status=='won'
        self.panel_base('СЕКТОР ПРОЙДЕН' if won else 'СИГНАЛ ПОТЕРЯН', 'Цель достигнута' if won else 'Алекс погиб. Нова сохранила последние данные.')
        self.rect((W//2-330,266,660,267),'panel','border',12)
        lines=[f'Очки сектора: {w.score}',f'Время: {int(w.time)//60:02d}:{int(w.time)%60:02d}',f'Обнаружения: {w.stats["detections"]}',f'Ошибки команд: {w.stats["errors"]}',f'Собранные предметы: {w.stats["items"]}']
        for i,line in enumerate(lines):self.text(line,W//2-245,288+i*43,22,'text')
        self.button('ДАЛЬШЕ' if won else 'ПОВТОРИТЬ УРОВЕНЬ',(W//2-245,572,490,58),lambda:self.result_next(),True)
        self.button('В МЕНЮ',(W//2-245,650,490,48),lambda:self.set_mode('menu'))
    def result_next(self):
        if self.world.status=='lost':self.restart()
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
        elif self.mode=='result':self.result()
        elif self.mode=='ending_choice':self.ending_choice()
        elif self.mode=='credits':self.credits()
        pygame.display.flip()
    def run(self):
        while self.running:
            dt=self.clock.tick(CFG.get('fps',60))/1000
            for event in pygame.event.get():self.event(event)
            self.tick(dt);self.draw()
        self.save();self.voice.stop();pygame.quit()

def main():
    try:Game().run()
    except Exception as exc:
        import traceback;traceback.print_exc()
        try:
            (ROOT/'crash_log.txt').write_text(traceback.format_exc(),encoding='utf-8')
            print('Отчёт сохранён в crash_log.txt')
        except OSError:pass
        raise
