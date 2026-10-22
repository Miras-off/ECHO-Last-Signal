"""Pure Python game simulation. Maps are editable with Tiled, art with Inkscape.
No imports of Pygame or microphone: physics, AI and objectives can be tested headlessly.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from collections import deque
import json, math

ROOT=Path(__file__).resolve().parents[1]
ABILITIES=('scan','hack','shield','pulse','control','memory')
COLORS={'red':'красное','yellow':'жёлтое','blue':'синее'}
SOLUTIONS={1:('red','yellow'),2:('blue','red'),3:('yellow','blue')}


def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def props(obj):return {p['name']:p['value'] for p in obj.get('properties',[])}
def clamp(x,a,b):return max(a,min(b,x))

def load_map(n):
    path=ROOT/'maps'/f'level_{n}.tmj'
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['width']>0 and data['height']>0
    layers=data['layers'];tiles=next(z['data'] for z in layers if z['type']=='tilelayer')
    objects=[]
    for source in next(z['objects'] for z in layers if z['type']=='objectgroup'):
        o={'id':source['id'],'type':source['type'],'name':source['name'],'x':source['x']/48,'y':source['y']/48,'taken':False}
        o.update(props(source)); objects.append(o)
    return data['width'],data['height'],tiles,objects

@dataclass
class Player:
    x:float=3.5
    y:float=23.5
    hp:float=100.0
    energy:float=100.0
    facing:str='down'
    walk_anim:float=0.0

@dataclass
class Drone:
    x:float
    y:float
    base_x:float
    base_y:float
    target_x:float
    target_y:float
    vision:float=6.0
    state:str='patrol'
    stunned:float=0.0
    last_seen_x:float=0.0
    last_seen_y:float=0.0
    timer:float=0.0
    attack_cooldown:float=0.0
    path_timer:float=0.0
    patrol_backward:bool=False
    path:list=field(default_factory=list)

class World:
    def __init__(self,level=1,abilities=None,stats=None,inventory=None,challenge=False):
        self.level=level;self.challenge=challenge
        try:self.story=json.loads((ROOT/'story'/'levels.json').read_text(encoding='utf-8'))[str(level)]
        except (OSError,ValueError,KeyError):self.story={}
        self.title=self.story.get('name',{1:'ПРОБУЖДЕНИЕ',2:'МЁРТВЫЙ СЕКТОР',3:'ПОСЛЕДНИЙ СИГНАЛ'}[level])
        self.width,self.height,self.tiles,self.objects=load_map(level)
        start=next(o for o in self.objects if o['type']=='spawn')
        self.player=Player(start['x'],start['y'])
        self.gate_positions={o['gate_id']:(int(o['x']),int(o['y'])) for o in self.objects if o['type']=='gate'}
        self.abilities=set(abilities or ())
        self.inventory={'medkit':1,'battery':1,'keycard':0,'lure':0}
        self.inventory.update(inventory or {})
        self.stats={'detections':0,'voice_success':0,'voice_errors':0,'errors':0,'actions_success':0,'commands':0,'items':0,'damage':0,'hints':0}
        self.stats.update(stats or {})
        self.time=0.0;self.score=0;self.alert=0.0;self.status='playing'
        self.level_end='';self.ending='';self.shield_until=0.0;self.cam_disable_until=0.0
        self.terminal_stage=0;self.core_stage=0;self.gates={'A':False,'B':False}
        self.history=[];self.log=[];self.log_counter=0;self.camera_suspicion={}
        self.combat_events=[];self.combat_event_seq=0
        self.ai_factor=1.0
        self.puzzles={p['id']:p for p in json.loads((ROOT/'story'/'puzzles.json').read_text(encoding='utf-8')).get(str(level),[])}
        self.solved_puzzles=set()
        self.last_damage=-10.0;self.last_detect=-10.0;self.last_hint=-10.0
        self.lure_pos=None;self.lure_until=0.0
        self.drones=[]
        for o in self.objects:
            if o['type']=='drone':
                self.drones.append(Drone(o['x'],o['y'],o['x'],o['y'],float(o.get('target_x',o['x'])),float(o.get('target_y',o['y'])),float(o.get('range',6))))
        self.message(self.story.get('dialog','НОВА: Я вижу маршрут к спасательной шлюпке, но часть моих модулей повреждена.'),'nova')
    def message(self,text,kind='info'):
        self.log_counter+=1
        self.log.append((self.time,text,kind));self.log=self.log[-8:]
    def combat_fx(self,kind,source,target=None,targets=None,duration=.5):
        """Record a short, renderer-agnostic combat event with fixed coordinates."""
        self.combat_event_seq+=1
        event={
            'id':self.combat_event_seq,
            'kind':str(kind),
            'start':self.time,
            'duration':max(.05,float(duration)),
            'source':[float(source[0]),float(source[1])],
        }
        if target is not None:event['target']=[float(target[0]),float(target[1])]
        if targets is not None:event['targets']=[[float(x),float(y)] for x,y in targets]
        self.combat_events.append(event);self.combat_events=self.combat_events[-24:]
        return event
    def solve_puzzle(self,puzzle_id,choice):
        p=self.puzzles.get(str(puzzle_id))
        if not p or puzzle_id in self.solved_puzzles:return False
        if choice!=p['answer']:
            self.fail('Неверное решение терминала. Система активирует тревогу.')
            return False
        self.solved_puzzles.add(puzzle_id)
        self.history.append(f"{p['title']}: {p['explain']}")
        if p.get('reward')=='medkit':self.inventory['medkit']+=1
        if p.get('reward')=='battery':self.inventory['battery']+=1
        self.success(f"Решение принято: {p['title']}. {p['explain']}",140)
        return True

    def nearby(self,typ=None,r=1.5):
        opts=[o for o in self.objects if not o['taken'] and (typ is None or o['type']==typ) and distance((self.player.x,self.player.y),(o['x'],o['y']))<=r]
        return min(opts,key=lambda z:distance((self.player.x,self.player.y),(z['x'],z['y']))) if opts else None
    def collides(self,x,y,r=.22):
        for ax in (x-r,x+r):
            for ay in (y-r,y+r):
                gx,gy=int(ax),int(ay)
                if gx<0 or gx>=self.width or gy<0 or gy>=self.height:return True
                if self.tiles[gy*self.width+gx] in (2,5):return True
                for gate,pos in self.gate_positions.items():
                    if not self.gates[gate] and (gx,gy)==pos:return True
        return False
    def is_walkable_tile(self,gx,gy):
        if gx<0 or gx>=self.width or gy<0 or gy>=self.height:return False
        if self.tiles[gy*self.width+gx] in (2,5):return False
        for gate,pos in self.gate_positions.items():
            if not self.gates[gate] and (gx,gy)==pos:return False
        return True

    def is_portal_tile(self,gx,gy):
        if not self.is_walkable_tile(gx,gy):return False
        left=not self.is_walkable_tile(gx-1,gy)
        right=not self.is_walkable_tile(gx+1,gy)
        up=not self.is_walkable_tile(gx,gy-1)
        down=not self.is_walkable_tile(gx,gy+1)
        horiz_narrow=left and right and not (up and down)
        vert_narrow=up and down and not (left and right)
        return horiz_narrow or vert_narrow

    def room_tiles(self,x=None,y=None):
        # A narrow 1-tile doorway separates rooms. While the player is exactly
        # on the threshold, keep displaying the previously entered room.
        active=x is None and y is None
        sx=int(self.player.x if x is None else x)
        sy=int(self.player.y if y is None else y)
        if not self.is_walkable_tile(sx,sy):return {(sx,sy)}
        if self.is_portal_tile(sx,sy) and active and getattr(self,'_last_room_tiles',None):
            return self._last_room_tiles | {(sx,sy)}
        start=(sx,sy);q=deque([start]);seen={start}
        while q:
            cx,cy=q.popleft()
            if (cx,cy)!=start and self.is_portal_tile(cx,cy):
                continue
            for nx,ny in ((cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)):
                if (nx,ny) not in seen and self.is_walkable_tile(nx,ny):
                    seen.add((nx,ny));q.append((nx,ny))
        if active and not self.is_portal_tile(sx,sy):
            previous=getattr(self,'_last_room_tiles',None)
            # A few maps use 1-tile L-shaped connector pockets between two
            # door thresholds. Treat these tiny components as a transition,
            # otherwise fog collapses to only 3 cells for a single step.
            if previous and len(seen)<=6:
                seen=set(previous)|seen
            self._last_room_tiles=seen
        return seen

    def room_view_tiles(self):
        # The current room is fully visible. A short flood through each open
        # doorway previews only the entrance of the next room, giving the
        # player enough information to time a safe crossing without revealing
        # the complete room.
        room=self.room_tiles()
        visible_floor=set(room)|self.room_preview_tiles(room)
        view=set(visible_floor)
        for cx,cy in visible_floor:
            for nx,ny in ((cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)):
                if 0<=nx<self.width and 0<=ny<self.height and not self.is_walkable_tile(nx,ny):
                    view.add((nx,ny))
        return view

    def room_preview_tiles(self,room=None,depth=3):
        """Return a small walkable slice beyond doorways of ``room``."""
        room=set(self.room_tiles() if room is None else room)
        seeds=[]
        for cx,cy in room:
            if not self.is_portal_tile(cx,cy):continue
            for nx,ny in ((cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)):
                if (nx,ny) not in room and self.is_walkable_tile(nx,ny):
                    seeds.append((nx,ny))
        preview=set();seen=set();queue=deque((x,y,1) for x,y in seeds)
        while queue:
            x,y,steps=queue.popleft()
            if (x,y) in seen or (x,y) in room or steps>depth:continue
            seen.add((x,y));preview.add((x,y))
            if steps==depth:continue
            for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if (nx,ny) not in seen and (nx,ny) not in room and self.is_walkable_tile(nx,ny):
                    queue.append((nx,ny,steps+1))
        return preview

    def ray_clear(self,ax,ay,bx,by):
        d=math.hypot(bx-ax,by-ay)
        steps=max(1,math.ceil(d*8))
        for i in range(1,steps):
            t=i/steps
            if self.collides(ax+(bx-ax)*t,ay+(by-ay)*t,.04):return False
        return True
    def pathfind(self,start,goal):
        sx,sy=int(start[0]),int(start[1]);gx,gy=int(goal[0]),int(goal[1]);q=deque([(sx,sy)])
        seen={(sx,sy):None}
        while q:
            x,y=q.popleft()
            if (x,y)==(gx,gy):break
            for xx,yy in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if (xx,yy) not in seen and not self.collides(xx+.5,yy+.5,.05):
                    seen[xx,yy]=(x,y);q.append((xx,yy))
        if (gx,gy) not in seen:return []
        cur=(gx,gy);result=[]
        while cur!=(sx,sy):result.append((cur[0]+.5,cur[1]+.5));cur=seen[cur]
        result.reverse();return result
    @property
    def difficulty(self):
        base=.72 if (self.stats['detections']>=4 or self.stats['damage']>=75 or self.stats['errors']>=4 or self.player.hp<35) else 1.18 if (self.time>45 and self.stats['detections']==0 and self.player.hp>75) else 1.0
        return clamp(base*self.ai_factor,.65,1.35)
    @property
    def shielded(self):return self.time<self.shield_until
    @property
    def alert_level(self):return 3 if self.alert>=80 else 2 if self.alert>=50 else 1 if self.alert>=18 else 0
    @property
    def mission(self):
        if self.terminal_stage<4:
            if sum(pid in self.solved_puzzles for pid in self.puzzles if pid.endswith(('A','B')))<2:
                return 'Найди и реши два логических терминала в первом отсеке.'
            if 'scan' not in self.abilities:return 'Найди модуль сканирования.'
            if 'hack' not in self.abilities:return 'Найди модуль взлома.'
            if self.inventory['keycard']==0:return 'Найди карту доступа.'
            return ['Подключись к главному терминалу.','Сканируй терминал.','Взломай защиту терминала.','Открой первый шлюз.'][self.terminal_stage]
        if self.core_stage<4:
            if any(pid not in self.solved_puzzles for pid in self.puzzles):
                return 'Реши все три головоломки сектора, затем настрой ядро.'
            return ['Найди энергетическое ядро в центральном секторе.','Отключи нужное ядро согласно подсказке.','Активируй нужное ядро согласно подсказке.','Открой второй шлюз.'][self.core_stage]
        return 'Доберись до спасательного перехода.' if self.level<3 else 'Доберись до шлюпки «Аврора».'
    def damage(self,value,reason):
        if self.time-self.last_damage<1.2:return
        self.last_damage=self.time
        if self.shielded:
            self.message('НОВА: маскировочный щит поглотил удар.','success');return
        value=round(value,1);self.player.hp=max(0,self.player.hp-value);self.stats['damage']+=value
        self.message(f'{reason}  −{value:g} HP','danger')
        if self.player.hp<=0:
            self.status='lost';self.message('НОВА: критический отказ биопоказателей.','danger')
    def fail(self,text):
        self.stats['errors']+=1
        if getattr(self,'_command_source','keyboard')=='voice':self.stats['voice_errors']+=1
        self.alert=min(100,self.alert+7)
        self.message('НОВА: '+text,'warning');return False
    def success(self,text,points=50):
        self.score+=points;self.stats['actions_success']+=1
        if getattr(self,'_command_source','keyboard')=='voice':self.stats['voice_success']+=1
        self.message('НОВА: '+text,'success');return True
    def command(self,cmd,source='keyboard'):
        if self.status!='playing':return False
        self.stats['commands']+=1;self._command_source=source
        if source=='voice':self.message('ГОЛОС: '+cmd,'voice')
        near_main=self.nearby('main_terminal',1.8)
        near_core=self.nearby('core',1.85)
        if cmd in ('help','nova'):
            self.stats['hints']+=1;self.message('НОВА: '+self.mission+' Рекомендация: исследуй боковые комнаты.','nova');return True
        if cmd=='shield':
            if 'shield' not in self.abilities:return self.fail('Модуль маскировки ещё не найден.')
            if self.player.energy<29:return self.fail('Недостаточно энергии для щита (29).')
            if self.shielded:return True
            self.player.energy-=29;self.shield_until=self.time+7
            return self.success('Маскировочное поле активировано на 7 секунд.',40)
        if cmd=='pulse':
            if 'pulse' not in self.abilities:return self.fail('Модуль импульса ещё не найден.')
            if self.player.energy<36:return self.fail('Недостаточно энергии для импульса (36).')
            self.player.energy-=36;affected=0;targets=[]
            for drone in self.drones:
                if distance((drone.x,drone.y),(self.player.x,self.player.y))<5.1:
                    targets.append((drone.x,drone.y))
                    drone.stunned=self.time+5;drone.state='stunned';affected+=1
            self.combat_fx('player_pulse',(self.player.x,self.player.y),targets=targets,duration=.78)
            if affected:return self.success(f'Оглушено дронов: {affected}.',80*affected)
            self.message('НОВА: Импульс активирован, поблизости нет целей.','info');return True
        if cmd=='medkit':return self.use_item('medkit')
        if cmd=='battery':return self.use_item('battery')
        if cmd=='lure':return self.use_item('lure')
        if cmd=='scan':
            if 'scan' not in self.abilities:return self.fail('Сначала найди модуль сканирования.')
            if near_main and self.terminal_stage==1:
                self.terminal_stage=2;return self.success('Уязвимость терминала обнаружена.',85)
            if near_core and self.core_stage==0:
                self.core_stage=1
                self.message('НОВА: '+self.clue,'nova');return self.success('Данные ядра изучены. Выбери два действия.',85)
            return self.success('Сканирование: '+self.mission,5)
        if cmd=='connect':
            if near_main and self.terminal_stage==0:
                self.terminal_stage=1;return self.success('Терминал подключён. Теперь сканируй.',70)
            aux=self.nearby('aux_terminal',1.7)
            if aux and 'hack' in self.abilities:
                self.cam_disable_until=self.time+26;return self.success('Камеры сектора отключены на 26 секунд.',100)
            if near_main and self.terminal_stage>0:return self.success('Соединение активно.',0)
            return self.fail('Подойди к терминалу и повтори подключение.')
        if cmd=='hack':
            if 'hack' not in self.abilities:return self.fail('Нужен модуль взлома.')
            if near_main and self.terminal_stage==2:
                self.terminal_stage=3;return self.success('Шифрование терминала снято. Открой шлюз.',110)
            if self.nearby('aux_terminal',1.7):
                self.cam_disable_until=self.time+26;return self.success('Система камер временно отключена.',80)
            return self.fail('Сначала: подключение → сканирование → взлом.')
        if cmd=='open':
            if near_main and self.terminal_stage==3:
                if any(pid.endswith(('A','B')) and pid not in self.solved_puzzles for pid in self.puzzles):
                    return self.fail('Доступ закрыт. Реши два логических терминала первого отсека.')
                if self.inventory['keycard']==0:return self.fail('Нужна карта персонала.')
                self.gates['A']=True;self.terminal_stage=4;return self.success('Шлюз A открыт! Доступ к ядру разрешён.',190)
            if near_core and self.core_stage==3:
                if any(pid not in self.solved_puzzles for pid in self.puzzles):
                    return self.fail('Не все логические задания сектора решены.')
                if self.level==3 and 'control' not in self.abilities:return self.fail('Нужен модуль управления кораблём.')
                self.gates['B']=True;self.core_stage=4;return self.success('Шлюз B открыт. Выход доступен.',210)
            if near_main or near_core:return self.fail('Сначала выполни все действия на панели.')
            return self.fail('Рядом нет готового к открытию шлюза.')
        if cmd.startswith('off_') or cmd.startswith('on_'):
            if not near_core:return self.fail('Необходимо подойти к энергетическому ядру.')
            typ,color=cmd.split('_',1);off,on=SOLUTIONS[self.level]
            if typ=='off' and self.core_stage==1:
                if color!=off:return self.fail('Неверный контур! Проверь запись у ядра.')
                self.core_stage=2;return self.success(f'{COLORS[color].capitalize()} ядро отключено.',100)
            if typ=='on' and self.core_stage==2:
                if color!=on:return self.fail('Неверный контур питания! Проверь подсказку.')
                self.core_stage=3;return self.success(f'{COLORS[color].capitalize()} ядро активировано. Открой шлюз.',100)
            return self.fail('Неверный порядок. Сначала сканируй → отключи → активируй.')
        return self.fail('Команда не распознана игровыми системами.')
    @property
    def clue(self):
        return self.story.get('clue',{1:'Красное питает турели, синее связь, жёлтое спасательные шлюзы. Отключи оборону и запитай выход.',2:'Синее создаёт помехи, красное стабилизирует вентиляцию, жёлтое резерв. Отключи помехи и запусти вентиляцию.',3:'Жёлтое удерживает ангар, синее управляет питанием, красное диагностика. Сними блокировку и запитай ангар.'}[self.level])
    def use_item(self,kind):
        if self.inventory.get(kind,0)<1:return self.fail('Такого предмета нет в инвентаре.')
        if kind=='medkit':
            if self.player.hp>=100:return False
            self.inventory[kind]-=1;self.player.hp=min(100,self.player.hp+45);return self.success('Аптечка использована. +45 HP.',30)
        if kind=='battery':
            if self.player.energy>=100:return False
            self.inventory[kind]-=1;self.player.energy=min(100,self.player.energy+60);return self.success('Энергия Новы восстановлена. +60.',30)
        if kind=='lure':
            self.inventory[kind]-=1;self.lure_pos=(self.player.x,self.player.y);self.lure_until=self.time+9
            return self.success('Отвлекающий маяк запущен. Дроны проверяют сигнал.',55)
        return False
    def interact(self):
        if self.status!='playing':return False
        self._command_source='keyboard'
        collectible_types={'module','medkit','battery','keycard','lure','note'}
        o=self.nearby(r=1.3)
        if o and o['type'] in collectible_types:
            kind=o['type'];o['taken']=True;self.stats['items']+=1
            if kind=='module':
                ability=o['ability'];self.abilities.add(ability);self.score+=100
                self.message('НОВА: МОДУЛЬ «'+{'scan':'СКАНЕР','hack':'ВЗЛОМ','shield':'МАСКИРОВКА','pulse':'ИМПУЛЬС','control':'УПРАВЛЕНИЕ','memory':'ПАМЯТЬ'}[ability]+'» УСТАНОВЛЕН.','success')
            elif kind=='note':
                self.score+=35;self.history.append(o.get('text','Архив повреждён.'));self.message('АРХИВ: '+o.get('text','Сведения недоступны.'),'nova')
            else:
                self.inventory[kind]=self.inventory.get(kind,0)+1;self.score+=30;self.message('НАЙДЕНО: '+o['name'],'success')
            return True
        obj=self.nearby(r=1.75)
        if obj:
            if obj['type']=='exit':
                if self.core_stage<4:return self.fail('Выход заблокирован. Реши головоломку ядра.')
                self.status='won';self.score+=max(100,500-int(self.time));self.level_end='escape'
                self.message('НОВА: Путь свободен. Сектор пройден!','success');return True
            if obj['type']=='main_terminal':self.message('ТЕРМИНАЛ: '+self.mission,'info');return True
            if obj['type']=='core':
                hint='ИНЖЕНЕРНАЯ СХЕМА: '+self.clue
                if hint not in self.history:self.history.append(hint)
                self.message('ПОДСКАЗКА: '+self.clue,'nova');return True
            if obj['type']=='broken_terminal':self.message('Разбитый терминал. Питание отключено. Это тупик.','warning');return True
            if obj['type']=='aux_terminal':self.message('Вспомогательная сеть камер. Команда: «Подключение».','info');return True
        self.message('НОВА: Здесь нет предметов для взаимодействия.','info');return False
    def visible_to_sensor(self,x,y,angle,vision,fov):
        if self.shielded:return False
        ax,ay=self.player.x-x,self.player.y-y
        d=math.hypot(ax,ay)
        if d>vision:return False
        direction=math.degrees(math.atan2(ay,ax))
        delta=((direction-angle+180)%360)-180
        return abs(delta)<=fov*.5 and self.ray_clear(x,y,self.player.x,self.player.y)
    def _drone_step(self,d,dt):
        if self.time<d.stunned:
            d.state='stunned';return
        if d.state=='stunned':
            d.state='search';d.timer=2.2;d.last_seen_x=d.base_x;d.last_seen_y=d.base_y
        d.attack_cooldown=max(0,d.attack_cooldown-dt)
        detected=self.visible_to_sensor(d.x,d.y,math.degrees(math.atan2(self.player.y-d.y,self.player.x-d.x)),min(d.vision,3.7),360)
        if detected:
            if d.state!='chase' and self.time-self.last_detect>2.5:
                self.stats['detections']+=1;self.last_detect=self.time;self.message('НОВА: Дрон обнаружил движение!','danger')
            d.state='chase';d.timer=4.2;d.last_seen_x=self.player.x;d.last_seen_y=self.player.y;self.alert=clamp(self.alert+24*dt,0,100)
        elif d.state in ('chase','search'):
            d.timer-=dt
            if d.timer<=0:d.state='patrol'
            else:d.state='search'
        if d.state=='patrol':
            tx,ty=(d.base_x,d.base_y) if d.patrol_backward else (d.target_x,d.target_y)
            if distance((d.x,d.y),(tx,ty))<.45:
                d.patrol_backward=not d.patrol_backward
                tx,ty=(d.base_x,d.base_y) if d.patrol_backward else (d.target_x,d.target_y)
        elif d.state in ('chase','search'):
            tx,ty=d.last_seen_x,d.last_seen_y
        else:return
        d.path_timer-=dt
        if d.path_timer<=0:
            d.path=self.pathfind((d.x,d.y),(tx,ty));d.path_timer=.65
        if d.path:
            while len(d.path)>1 and distance((d.x,d.y),d.path[0])<.3:d.path.pop(0)
            tx,ty=d.path[0]
        dx,dy=tx-d.x,ty-d.y;length=math.hypot(dx,dy)
        if length>.04:
            speed=(1.22 if d.state=='patrol' else 1.85)*self.difficulty*(1.18 if self.challenge else 1)
            nx=d.x+dx/length*min(length,dt*speed);ny=d.y+dy/length*min(length,dt*speed)
            if not self.collides(nx,d.y,.25):d.x=nx
            if not self.collides(d.x,ny,.25):d.y=ny
        if d.state=='chase' and distance((d.x,d.y),(self.player.x,self.player.y))<2.5 and d.attack_cooldown<=0:
            d.attack_cooldown=2.0/self.difficulty
            self.combat_fx('drone_attack',(d.x,d.y),(self.player.x,self.player.y),duration=.48)
            self.damage(14,'Импульс дрона')
    def step(self,dt,dx=0,dy=0,run=False):
        if self.status!='playing':return
        dt=clamp(float(dt),0,.07);self.time+=dt
        self.combat_events=[event for event in self.combat_events if self.time-event['start']<=event['duration']+.08]
        p=self.player
        if dx or dy:
            l=math.hypot(dx,dy);dx/=l;dy/=l
            speed=(4.25 if run else 2.9)*dt
            if not self.collides(p.x+dx*speed,p.y):p.x+=dx*speed
            if not self.collides(p.x,p.y+dy*speed):p.y+=dy*speed
            p.facing='right' if abs(dx)>abs(dy) and dx>0 else 'left' if abs(dx)>abs(dy) else 'down' if dy>0 else 'up'
            p.walk_anim+=dt*(9 if run else 6)
            if run and self.time-self.last_detect>2.5:
                for drone in self.drones:
                    if distance((drone.x,drone.y),(p.x,p.y))<2.8:
                        drone.state='search';drone.timer=3;drone.last_seen_x=p.x;drone.last_seen_y=p.y
        p.energy=min(100,p.energy+1.4*dt)
        self.alert=max(0,self.alert-3.1*dt)
        for o in self.objects:
            if o['type']!='camera' or self.time<self.cam_disable_until:continue
            angle=float(o.get('angle',0))+math.sin(self.time*.85+o['x'])*float(o.get('sweep',50))
            if self.visible_to_sensor(o['x'],o['y'],angle,float(o.get('range',7)),64):
                before=self.camera_suspicion.get(o['id'],0)
                self.camera_suspicion[o['id']]=min(1.5,before+dt*.82*self.difficulty)
                if before<1<=self.camera_suspicion[o['id']]:
                    self.stats['detections']+=1;self.message('ТРЕВОГА: камера навела турели!','danger')
                if self.camera_suspicion[o['id']]>=1:self.alert=min(100,self.alert+33*dt)
            else:self.camera_suspicion[o['id']]=max(0,self.camera_suspicion.get(o['id'],0)-dt*.8)
        for d in self.drones:
            if self.lure_pos is not None and self.time<self.lure_until and distance((d.x,d.y),self.lure_pos)<9 and d.state not in ('chase','stunned'):
                d.state='search';d.timer=2.8;d.last_seen_x,d.last_seen_y=self.lure_pos
            self._drone_step(d,dt)
        for o in self.objects:
            if o['type']=='turret' and self.alert>=47 and self.time-self.last_damage>1.2:
                if distance((o['x'],o['y']),(p.x,p.y))<=float(o.get('range',7)) and self.ray_clear(o['x'],o['y'],p.x,p.y):
                    self.combat_fx('turret_shot',(o['x'],o['y']),(p.x,p.y),duration=.34)
                    self.damage(12,'Выстрел турели')
        if self.challenge and self.alert<20:self.alert+=dt*.25
    def snapshot(self):
        return {'level':self.level,'abilities':sorted(self.abilities),'inventory':self.inventory,'stats':self.stats,'score':self.score,'time':round(self.time,2),'health':round(self.player.hp),'energy':round(self.player.energy),'position':[self.player.x,self.player.y], 'terminal_stage':self.terminal_stage,'core_stage':self.core_stage,'gates':self.gates,'solved_puzzles':sorted(self.solved_puzzles),'history':self.history,'taken_ids':[o['id'] for o in self.objects if o['taken']],'challenge':self.challenge}
    def restore(self,snap):
        self.player.x,self.player.y=map(float,snap.get('position',[self.player.x,self.player.y]))
        self.player.hp=float(snap.get('health',100))
        self.player.energy=float(snap.get('energy',100))
        self.terminal_stage=int(snap.get('terminal_stage',0))
        self.core_stage=int(snap.get('core_stage',0))
        self.gates.update(snap.get('gates',{}))
        self.solved_puzzles=set(snap.get('solved_puzzles',[]))
        self.history=list(snap.get('history',[]))
        self.score=int(snap.get('score',0))
        self.time=float(snap.get('time',0))
        taken=set(map(str,snap.get('taken_ids',[])))
        for obj in self.objects:obj['taken']=str(obj['id']) in taken
