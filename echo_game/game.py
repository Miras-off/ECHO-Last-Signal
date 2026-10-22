"""ECHO: Last Signal — playable Windows-friendly 2D top-down vertical slice.

Controls: WASD movement, E context action, 1..8 action shortcuts, F8 microphone.
Actual speech recognition is handled by offline Vosk when its model is present.
"""
import math
import os
import random
import sys

try:
    import pygame
except ImportError:
    raise SystemExit('Не установлен pygame-ce. На Windows запусти 01_SETUP.bat или pip install -r requirements.txt')

from .commands import COMMANDS
from .config import (ASSETS, BG, BORDER, CYAN, FPS, GREEN, HEIGHT, INK, MAP_X,
                     MAP_Y, MUTED, ORANGE, PANEL_X, PLAY_H, PLAY_W, PURPLE,
                     RED, SURFACE, SURFACE_2, TEXT, TILE, WIDTH)
from .storage import save_run, summary
from .voice import VoiceListener
from .world import CACHE, CORE, EXIT, GATE, LASER, LEVEL, TERMINAL, World


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption('ECHO: Последний сигнал  |  Prototype 0.1')
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = {}
        self.alive = True
        self.mode = 'menu'
        self.world = World()
        self.voice = VoiceListener()
        self.voice.state = 'F8: включить'
        self.voice_count = 0
        self.last_heard = '—'
        self.notice = ''
        self.buttons = []
        self.stats = summary()
        self.sprites = self._load_sprites()
        self.splash = pygame.image.load(str(ASSETS / 'splash.jpg')).convert()
        self.splash = pygame.transform.smoothscale(self.splash, (730, 360))
        self.stars = [(random.randint(0, WIDTH), random.randint(0, HEIGHT),
                       random.choice((1,1,1,2)), random.randint(20, 90)) for _ in range(120)]
        self.anim = 0.0
        self.saved_result = False
        self.help_origin = 'game'

    def _load_sprites(self):
        sizes = {'alex_idle':(47,60),'alex_walk':(47,60),
                 'alex_hurt':(47,60),'alex_victory':(47,60),
                 'nova':(48,38),'drone':(60,45)}
        sprites = {}
        for name, size in sizes.items():
            loaded = pygame.image.load(str(ASSETS / (name+'.png'))).convert_alpha()
            sprites[name] = pygame.transform.scale(loaded, size)
        return sprites

    def font(self, size=20, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            # Windows: Segoe UI/Arial support Cyrillic; fallback DejaVu Sans on Linux.
            for name in ('Segoe UI','Arial','DejaVu Sans'):
                path = pygame.font.match_font(name, bold=bold)
                if path:
                    self.fonts[key] = pygame.font.Font(path, size)
                    break
            else:
                self.fonts[key] = pygame.font.SysFont(None, size, bold=bold)
        return self.fonts[key]

    def text(self, text, pos, size=20, color=TEXT, bold=False, anchor='topleft', max_width=None):
        f = self.font(size, bold)
        if max_width:
            max_width = max(12, max_width)
            words = str(text).split()
            if words:
                lines = []
                line = ''
                for word in words:
                    test = (line+' '+word).strip()
                    if f.size(test)[0] > max_width and line:
                        lines.append(line)
                        line = word
                    else:
                        line = test
                if line:
                    lines.append(line)
                for i, ln in enumerate(lines):
                    self.text(ln, (pos[0],pos[1]+i*(size+5)), size, color, bold, anchor)
                return len(lines)*(size+5)
        render = f.render(str(text), True, color)
        rect = render.get_rect()
        setattr(rect, anchor, pos)
        self.screen.blit(render, rect)
        return rect.height

    def rect(self, xywh, fill, radius=0, stroke=None, width=1):
        box = pygame.Rect(*[int(v) for v in xywh])
        pygame.draw.rect(self.screen, fill, box, border_radius=radius)
        if stroke is not None:
            pygame.draw.rect(self.screen, stroke, box, width=width, border_radius=radius)
        return box

    def line(self, start, end, color, width=1):
        pygame.draw.line(self.screen, color, start, end, width)

    def glow(self, x, y, color, r=42, opacity=54):
        r = max(8, int(r))
        surface = pygame.Surface((r*2,r*2), pygame.SRCALPHA)
        for step in range(5,0,-1):
            radius = r*step//5
            alpha = max(2, int(opacity/6 + (5-step)*opacity/19))
            pygame.draw.circle(surface, (*color, alpha), (r,r), radius)
        self.screen.blit(surface, (int(x-r),int(y-r)), special_flags=pygame.BLEND_RGBA_ADD)

    def xy(self, tile_x, tile_y):
        return int(MAP_X+tile_x*TILE), int(MAP_Y+tile_y*TILE)

    def draw_background(self):
        self.screen.fill(BG)
        for x,y,size,alpha in self.stars:
            color=(12+alpha//6, 35+alpha//5, 49+alpha//3)
            pygame.draw.circle(self.screen, color, (x,y), size)
        self.line((0,72),(WIDTH,72),(26,57,75),2)
        self.text('E C H O', (32,20), 34, CYAN, True)
        self.rect((185,21,1,30), BORDER)
        self.text('ПОСЛЕДНИЙ СИГНАЛ', (202,24), 19, TEXT, True)
        self.text('ПРОТОТИП • СЕКТОР A / ЛАБОРАТОРИЯ', (WIDTH-32,29), 15,
                  MUTED, anchor='topright')

    def tile_map(self):
        # Tile-by-tile floor, industrial lighting and wall cap shading.
        self.rect((MAP_X-6,MAP_Y-6, PLAY_W+12, PLAY_H+12), SURFACE, 8,
                  stroke=(36,73,94), width=2)
        for y,row in enumerate(LEVEL):
            for x,char in enumerate(row):
                sx,sy=self.xy(x,y)
                is_wall=char=='#'
                if is_wall:
                    col=(27,48,66) if (x+y)%2==0 else (30,54,74)
                    self.rect((sx,sy,TILE,TILE),col)
                    self.line((sx+3,sy+4),(sx+TILE-4,sy+4),(54,95,117),2)
                    self.line((sx+3,sy+4),(sx+3,sy+TILE-3),(44,78,100),2)
                    self.line((sx+5,sy+TILE-4),(sx+TILE-4,sy+TILE-4),(15,32,47),3)
                    if (x+y)%4==0:
                        pygame.draw.circle(self.screen,(76,124,142),(sx+TILE-8,sy+10),2)
                else:
                    col=(15,31,45) if (x+y)%2==0 else (18,35,50)
                    self.rect((sx,sy,TILE,TILE),col)
                    pygame.draw.rect(self.screen,(26,49,65),(sx,sy,TILE,TILE),1)
                    pygame.draw.circle(self.screen,(41,66,82),(sx+7,sy+8),1)
                    pygame.draw.circle(self.screen,(40,62,80),(sx+TILE-8,sy+TILE-8),1)
        # Floor markings and direction arrows.
        for x in (2,3,4,6,10,11,14,16):
            xx,yy=self.xy(x+.5,5+.5)
            self.line((xx-7,yy),(xx+7,yy),(50,83,95),1)
            self.line((xx+3,yy-3),(xx+7,yy),(50,83,95),1)
            self.line((xx+3,yy+3),(xx+7,yy),(50,83,95),1)
        # Level landmarks.
        self._draw_terminal()
        self._draw_gate()
        self._draw_core()
        self._draw_exit()
        self._draw_cache()
        self._draw_laser()
        self._draw_entities()
        # Hot zone marks at active objects.
        for x,y,color,active in ((TERMINAL[0],TERMINAL[1],CYAN,not self.world.hacked),
                                 (GATE[0],GATE[1],GREEN,not self.world.gate_open),
                                 (CORE[0],CORE[1],RED,not self.world.core_active),
                                 (EXIT[0],EXIT[1],GREEN,self.world.core_active)):
            if active and self.world.near((x,y),1.7):
                sx,sy=self.xy(x,y)
                pygame.draw.circle(self.screen,color,(sx,sy),28,2)
                self.text('E / ГОЛОС', (sx,sy-47), 13, color,True,'center')

    def _draw_terminal(self):
        x,y=self.xy(*TERMINAL)
        self.glow(x,y,CYAN,45,35)
        self.rect((x-18,y-22,36,44),(39,83,102),5,(104,182,197),2)
        self.rect((x-13,y-17,26,28),(7,42,61),3)
        color=GREEN if self.world.hacked else (117,251,243) if self.world.revealed else CYAN
        self.rect((x-9,y-10,18,3),color,2)
        self.rect((x-9,y-3,13,2),color,1)
        self.rect((x-9,y+4,21,2),color,1)
        pygame.draw.circle(self.screen, color, (x,y+17),3)
        self.text('ТЕРМИНАЛ', (x,y+28), 11, MUTED,True,'center')

    def _draw_gate(self):
        x,y=self.xy(*GATE)
        if self.world.gate_open:
            self.rect((x-23,y-22,8,44),(28,103,91),3, GREEN,2)
            self.rect((x+15,y-22,8,44),(28,103,91),3, GREEN,2)
            self.glow(x,y,GREEN,36,35)
            self.text('ОТКРЫТО',(x,y-43),11,GREEN,True,'center')
        else:
            self.glow(x,y,ORANGE,42,28)
            self.rect((x-21,y-23,42,46),(81,52,57),4,(234,119,111),2)
            for step in (-13,-3,7):
                self.line((x-15,y+step),(x+15,y+step),(171,87,84),3)
            self.rect((x-8,y+16,16,4),RED,2)
            self.text('ШЛЮЗ', (x,y-43), 11,ORANGE,True,'center')

    def _draw_core(self):
        x,y=self.xy(*CORE)
        active=self.world.core_active
        tint=GREEN if active else RED
        self.glow(x,y,tint,62,70)
        pygame.draw.circle(self.screen,(47,72,93),(x,y),27)
        pygame.draw.circle(self.screen,tint,(x,y),23,3)
        pygame.draw.circle(self.screen,(11,33,55),(x,y),17)
        pulse=math.sin(self.anim*3)*3 if not active else 0
        pygame.draw.circle(self.screen,tint,(x,y),int(9+pulse))
        pygame.draw.circle(self.screen,(251,255,255),(x-3,y-3),3)
        self.text('ЯДРО', (x,y+34), 12, tint,True,'center')

    def _draw_exit(self):
        x,y=self.xy(*EXIT)
        col=GREEN if self.world.core_active else (101,117,129)
        self.glow(x,y,col,42,31)
        self.rect((x-20,y-24,40,48),(24,53,64),4,col,2)
        self.rect((x-14,y-17,28,32),(9,37,43))
        self.line((x-5,y),(x+8,y),col,3)
        self.line((x+3,y-5),(x+8,y),col,3)
        self.line((x+3,y+5),(x+8,y),col,3)
        self.text('ВЫХОД', (x,y+27), 12,col,True,'center')

    def _draw_cache(self):
        if self.world.cache_taken:
            return
        x,y=self.xy(*CACHE)
        self.glow(x,y,ORANGE,36,38)
        self.rect((x-13,y-13,26,26),(90,72,50),5,ORANGE,2)
        self.rect((x-5,y-8,10,16), ORANGE,2)
        self.text('ЗАРЯД', (x,y+17), 11, ORANGE,True,'center')

    def _draw_laser(self):
        x,y=self.xy(*LASER)
        is_on=self.world.laser_on
        col=RED if is_on else (81,65,83)
        self.rect((x-20,y-19,40,38),(51,36,50),3,(112,70,83),1)
        for i in range(-2,3):
            self.line((x-20,y+i*8),(x+20,y+i*8),col,3 if is_on else 1)
        if is_on:
            self.glow(x,y,RED,46,45)
        self.text('ЛАЗЕР', (x,y+24), 11,col,True,'center')

    def _draw_entities(self):
        w=self.world
        dx,dy=self.xy(w.drone_x,w.drone_y)
        self.glow(dx,dy,RED if not w.drone_stunned else CYAN,44,50)
        self.screen.blit(self.sprites['drone'], (dx-30,dy-25))
        if w.drone_stunned:
            self.text('ОГЛУШЁН', (dx,dy-37),12,CYAN,True,'center')
        nx,ny=self.xy(w.nova_x,w.nova_y + math.sin(self.anim*3)*.10)
        self.glow(nx,ny,CYAN,30,25)
        self.screen.blit(self.sprites['nova'],(nx-24,ny-25))
        self.text('НОВА',(nx,ny+21),10,CYAN,True,'center')
        px,py=self.xy(w.player.x,w.player.y)
        if w.shielded:
            self.glow(px,py,CYAN,55,40)
            pygame.draw.circle(self.screen,CYAN,(px,py),33,2)
        moving=any(pygame.key.get_pressed()[k] for k in (
            pygame.K_w,pygame.K_a,pygame.K_s,pygame.K_d,
            pygame.K_UP,pygame.K_DOWN,pygame.K_LEFT,pygame.K_RIGHT))
        if w.player.hp<100 and w.time-w.last_damage_time<.4:
            name='alex_hurt'
        elif moving and int(self.anim*8)%2:
            name='alex_walk'
        else:
            name='alex_idle'
        sprite=self.sprites[name]
        if w.player.facing=='left':
            sprite=pygame.transform.flip(sprite,True,False)
        self.screen.blit(sprite,(px-23,py-42))
        self.rect((px-24,py-47,48,5),(9,29,43),3)
        self.rect((px-24,py-47,max(1,48*w.player.hp/100),5),GREEN if w.player.hp>35 else RED,3)

    def bar(self, x,y,w,value,tint,label):
        self.text(label,(x,y),15,MUTED,True)
        self.text(f'{int(value)}%',(x+w,y),15, TEXT,True,'topright')
        self.rect((x,y+26,w,11),(39,62,77),5)
        if value>0:
            self.rect((x,y+26,max(3,w*value/100),11),tint,5)

    def draw_sidebar(self):
        w=self.world
        x=PANEL_X
        width=WIDTH-x-26
        self.rect((x,94,width,638),SURFACE,12,(43,76,94),2)
        self.text('МИССИЯ 01', (x+20,113),14,CYAN,True)
        self.text('ПОСЛЕДНИЙ СИГНАЛ', (x+20,138),19,TEXT,True)
        self.line((x+18,173),(x+width-18,173),BORDER)
        self.text('ТЕКУЩАЯ ЦЕЛЬ',(x+20,188),14,MUTED,True)
        self.text(w.objective,(x+20,212),17,TEXT,True,max_width=width-40)
        self.text(f'ПРОГРЕСС  {w.progress}/4', (x+20,282),13,MUTED,True)
        for i in range(4):
            color=GREEN if i<w.progress else (48,81,97)
            self.rect((x+20+i*78,307,67,6),color,4)
        self.bar(x+20,331,width-40,w.player.hp,GREEN if w.player.hp>35 else RED,'ЗДОРОВЬЕ')
        self.bar(x+20,387,width-40,w.player.energy,CYAN,'ЭНЕРГИЯ')
        self.line((x+18,444),(x+width-18,444),BORDER)
        self.text('РАСПОЗНАВАНИЕ РЕЧИ',(x+20,461),14,MUTED,True)
        voice_col = GREEN if self.voice.state=='СЛУШАЕТ' else ORANGE
        pygame.draw.circle(self.screen,voice_col,(x+26,497),5)
        self.text(self.voice.state,(x+41,486),17,voice_col,True)
        self.text('F8 — включить / выключить микрофон',(x+20,514),13,MUTED)
        self.line((x+18,542),(x+width-18,542),BORDER)
        self.text('ГОЛОСОВЫЕ КОМАНДЫ / 1–8',(x+20,557),14,MUTED,True)
        for i,(_name,label,key) in enumerate(COMMANDS):
            c=i%2;r=i//2
            xx=x+20+c*(width//2-2)
            yy=591+r*31
            self.rect((xx,yy,25,23),SURFACE_2,5,(55,96,114))
            self.text(key,(xx+12,yy+2),14,CYAN,True,'midtop')
            self.text(label,(xx+33,yy+3),14,TEXT)
        self.text('H — справка     P / Esc — пауза',(x+20,714),12,MUTED)

    def draw_message(self):
        x=MAP_X
        self.rect((x,684,PLAY_W,48),SURFACE,8,(48,77,95),1)
        col={'info':CYAN,'success':GREEN,'error':RED}[self.world.message_type]
        self.rect((x+13,697,4,21),col,2)
        # short message wraps at 90 chars and is always visible
        self.text(self.world.message,(x+29,694),16,TEXT,max_width=PLAY_W-54)
        if self.last_heard!='—':
            self.text('ПОСЛЕДНЯЯ ФРАЗА: '+self.last_heard[:70],(x+4,738),11,MUTED)

    def draw_play(self):
        self.draw_background()
        self.tile_map()
        self.draw_sidebar()
        self.draw_message()
        self.text(f'ВРЕМЯ  {int(self.world.time)//60:02d}:{int(self.world.time)%60:02d}',
                  (MAP_X,655),13,MUTED,True)
        self.text(f'ОЧКИ  {self.world.points}',(MAP_X+PLAY_W,655),13,GREEN,True,'topright')
        self.text('WASD / стрелки — двигаться    |    E — действие рядом',
                  (MAP_X+PLAY_W//2,655),13,MUTED,anchor='midtop')

    def button(self, label,x,y,w,h,action,primary=False):
        mouse=pygame.mouse.get_pos()
        rect=pygame.Rect(x,y,w,h)
        hover=rect.collidepoint(mouse)
        bg=CYAN if primary else SURFACE_2
        if hover:
            bg=(119,250,234) if primary else (42,77,95)
        self.rect(rect,bg,12, (112,240,236) if not primary else None)
        self.text(label,rect.center,20,INK if primary else TEXT,True,'center')
        self.buttons.append((rect,action))

    def overlay(self, alpha=220):
        veil=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
        veil.fill((5,13,25,alpha))
        self.screen.blit(veil,(0,0))

    def menu(self):
        self.draw_background()
        self.screen.blit(self.splash,(WIDTH//2-365,101))
        self.rect((WIDTH//2-383,91,766,378),(13,35,55),12,(35,99,119),2)
        self.screen.blit(self.splash,(WIDTH//2-365,101))
        self.rect((WIDTH//2-204,132,408,41),(11,26,40),9)
        self.text('2D • SCI-FI • ГОЛОСОВОЙ КВЕСТ',(WIDTH//2,141),18,CYAN,True,'midtop')
        self.text('ECHO',(WIDTH//2,483),68,TEXT,True,'midtop')
        self.text('ПОСЛЕДНИЙ СИГНАЛ',(WIDTH//2,566),22,MUTED,True,'midtop')
        self.button('НАЧАТЬ МИССИЮ',WIDTH//2-300,626,280,59,'start',True)
        self.button('СТАТИСТИКА',WIDTH//2+20,626,280,59,'stats')
        self.text('WASD — движение     •     голос / 1–8 — действия     •     F8 — микрофон',
                  (WIDTH//2,710),15,MUTED,anchor='midtop')

    def paused(self):
        self.overlay()
        self.modal_frame('ПАУЗА','Система ожидания. Твой прогресс не потерян.')
        self.button('ПРОДОЛЖИТЬ',WIDTH//2-230,439,220,55,'resume',True)
        self.button('ГЛАВНОЕ МЕНЮ',WIDTH//2+10,439,220,55,'menu')
        self.button('КОМАНДЫ И ПОМОЩЬ',WIDTH//2-163,512,326,49,'help')

    def modal_frame(self,title,subtitle):
        self.rect((WIDTH//2-320,211,640,370),(16,34,52),20,(56,116,134),2)
        self.text(title,(WIDTH//2,255),43,TEXT,True,'midtop')
        self.text(subtitle,(WIDTH//2,337),17,MUTED,anchor='midtop')

    def help_screen(self):
        self.overlay(243)
        x,y=WIDTH//2-440,117
        self.rect((x,y,880,548),SURFACE,18,(51,114,134),2)
        self.text('ИНСТРУКЦИЯ К МИССИИ',(WIDTH//2,143),30,CYAN,True,'midtop')
        self.text('WASD / стрелки — движение    •    E — контекстное действие',
                  (x+30,203),18,TEXT)
        self.text('Для голосовых команд: установи модель, затем нажми F8.',
                  (x+30,237),17,MUTED)
        self.line((x+30,276),(x+850,276),BORDER)
        for i,(_,label,key) in enumerate(COMMANDS):
            col=i//4;row=i%4
            tx=x+36+col*420
            ty=297+row*58
            self.rect((tx,ty,38,34),SURFACE_2,6,(55,103,116))
            self.text(key,(tx+19,ty+7),17,CYAN,True,'midtop')
            self.text(label,(tx+54,ty+7),19,TEXT,True)
        self.text('Порядок: СКАНИРУЙ → ВЗЛОМАЙ → ОТКРОЙ → АКТИВИРУЙ → ВЫХОД',
                  (WIDTH//2,546),15,GREEN,True,'midtop')
        self.button('ВЕРНУТЬСЯ К ИГРЕ',WIDTH//2-164,590,328,52,'resume',True)

    def result_screen(self,success=True):
        self.overlay(236)
        title='МИССИЯ ВЫПОЛНЕНА' if success else 'СИГНАЛ ПОТЕРЯН'
        color=GREEN if success else RED
        self.rect((WIDTH//2-355,179,710,430),SURFACE,20,(61,118,126),2)
        self.glow(WIDTH//2,270,color,85,53)
        self.text(title,(WIDTH//2,225),38,color,True,'midtop')
        self.text('Станция снова на связи!' if success else 'Защита станции оказалась сильнее.',
                  (WIDTH//2,297),20,MUTED,anchor='midtop')
        self.text(f'ОЧКИ    {self.world.points}      ВРЕМЯ    {int(self.world.time)//60:02d}:{int(self.world.time)%60:02d}',
                  (WIDTH//2,368),23,TEXT,True,'midtop')
        self.text(f'ГОЛОСОВЫХ КОМАНД: {self.voice_count}    ОШИБОК: {self.world.errors}',
                  (WIDTH//2,405),16,MUTED,anchor='midtop')
        self.button('ПОВТОРИТЬ',WIDTH//2-255,500,245,59,'start',True)
        self.button('В МЕНЮ',WIDTH//2+10,500,245,59,'menu')

    def statistics(self):
        self.overlay(240)
        self.rect((WIDTH//2-340,176,680,430),SURFACE,20,(58,113,132),2)
        self.text('СТАТИСТИКА МИССИЙ',(WIDTH//2,209),34,CYAN,True,'midtop')
        s=self.stats
        self.text(f'ПОПЫТОК: {s["runs"]}      ПОБЕД: {s["wins"]}      РЕКОРД: {s["best"]}',
                  (WIDTH//2,287),19,TEXT,True,'midtop')
        self.text('ПОСЛЕДНИЕ РЕЗУЛЬТАТЫ',(WIDTH//2-276,354),16,MUTED,True)
        if not s['recent']:
            self.text('Пока нет сохранённых миссий.',(WIDTH//2-276,394),18,MUTED)
        for i,(state,score,secs) in enumerate(s['recent']):
            self.text(('УСПЕХ' if state=='won' else 'ПОРАЖЕНИЕ') +
                      f'     {score} очков      {secs//60:02d}:{secs%60:02d}',
                      (WIDTH//2-276,387+i*30),16,GREEN if state=='won' else RED)
        self.button('НАЗАД',WIDTH//2-126,541,252,48,'menu',True)

    def execute(self, action):
        if action=='start':
            self.world=World()
            self.voice_count=0
            self.last_heard='—'
            self.saved_result=False
            self.mode='game'
            # Start voice only after a real language model was installed.
            if (self.voice.model_path/'am').exists():
                self.voice.start()
            else:
                self.voice.state='НЕТ МОДЕЛИ'
        elif action=='stats':
            self.stats=summary()
            self.mode='stats'
        elif action=='help':
            self.help_origin=self.mode
            self.mode='help'
        elif action=='resume':
            self.mode='menu' if self.mode=='help' and self.help_origin=='menu' else 'game'
        elif action=='menu':
            self.mode='menu'
            self.voice.stop()
        elif action=='pause':
            self.mode='pause'

    def closest_action(self):
        w=self.world
        if w.near(TERMINAL):
            return 'scan' if not w.revealed else 'hack'
        if w.near(GATE,1.9):
            return 'open'
        if w.near(CORE,2):
            return 'activate'
        if w.near(EXIT,1.9):
            return 'open'
        return 'help'

    def handle_event(self,event):
        if event.type==pygame.QUIT:
            self.alive=False
            return
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            for rect,action in self.buttons:
                if rect.collidepoint(event.pos):
                    self.execute(action)
                    break
        if event.type!=pygame.KEYDOWN:
            return
        if event.key==pygame.K_F8 and self.mode=='game':
            if self.voice.state in ('СЛУШАЕТ','ЗАПУСК...'):
                self.voice.stop()
            else:
                self.voice.start()
            return
        if self.mode=='menu':
            if event.key in (pygame.K_RETURN,pygame.K_SPACE):
                self.execute('start')
            elif event.key==pygame.K_F1:
                self.execute('help')
            return
        if self.mode=='stats':
            if event.key in (pygame.K_ESCAPE,pygame.K_RETURN):
                self.execute('menu')
            return
        if self.mode in ('win','lose'):
            if event.key in (pygame.K_RETURN,pygame.K_r):
                self.execute('start')
            elif event.key==pygame.K_ESCAPE:
                self.execute('menu')
            return
        if self.mode=='pause':
            if event.key in (pygame.K_p,pygame.K_ESCAPE,pygame.K_RETURN):
                self.execute('resume')
            elif event.key==pygame.K_h:
                self.execute('help')
            return
        if self.mode=='help':
            if event.key in (pygame.K_h,pygame.K_F1,pygame.K_ESCAPE,pygame.K_RETURN):
                self.execute('resume')
            return
        if self.mode=='game':
            if event.key in (pygame.K_ESCAPE,pygame.K_p):
                self.execute('pause')
            elif event.key in (pygame.K_h,pygame.K_F1):
                self.execute('help')
            elif event.key==pygame.K_e:
                self.world.command(self.closest_action())
            else:
                for name,label,key in COMMANDS:
                    if event.unicode == key:
                        self.world.command(name)
                        break

    def handle_voice_events(self):
        for kind,value in self.voice.poll():
            if kind=='heard':
                self.last_heard=value
            elif kind=='notice':
                self.world._record(value,'info')
            elif kind=='command' and self.mode=='game':
                self.voice_count+=1
                self.world.command(value)

    def update(self,dt):
        self.anim += dt
        self.handle_voice_events()
        if self.mode!='game':
            return
        keys=pygame.key.get_pressed()
        dx=int(keys[pygame.K_d] or keys[pygame.K_RIGHT])-int(keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy=int(keys[pygame.K_s] or keys[pygame.K_DOWN])-int(keys[pygame.K_w] or keys[pygame.K_UP])
        self.world.step(dt,dx,dy)
        if self.world.status!='playing' and not self.saved_result:
            self.saved_result=True
            self.mode='win' if self.world.status=='won' else 'lose'
            save_run(self.world.status,self.world.points,int(self.world.time),
                     self.voice_count,self.world.errors)
            self.stats=summary()
            self.voice.stop()

    def draw(self):
        self.buttons.clear()
        if self.mode=='menu':
            self.menu()
            return
        self.draw_play()
        if self.mode=='pause':
            self.paused()
        elif self.mode=='help':
            self.help_screen()
        elif self.mode=='win':
            self.result_screen(True)
        elif self.mode=='lose':
            self.result_screen(False)
        elif self.mode=='stats':
            self.statistics()

    def run(self):
        while self.alive:
            dt=self.clock.tick(FPS)/1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        self.voice.stop()
        pygame.quit()


def main():
    Game().run()
