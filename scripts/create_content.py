"""Regenerate editable Tiled maps, sprites (SVG/PNG), interface art and tileset."""
from pathlib import Path
import json, math, random
import cairosvg
from PIL import Image, ImageDraw, ImageFont
import io
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'assets/source_svg'; SPR=ROOT/'assets/sprites'; TILES=ROOT/'assets/tiles'; UI=ROOT/'assets/ui'; MAPS=ROOT/'maps'
for p in (SRC,SPR,TILES,UI,MAPS):p.mkdir(parents=True,exist_ok=True)


def svg(name,w,h,body,out=None):
    st=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs>
    <linearGradient id="steel" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#a4d6df"/><stop offset=".45" stop-color="#435f78"/><stop offset="1" stop-color="#13283f"/></linearGradient>
    <linearGradient id="floor" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#243a50"/><stop offset="1" stop-color="#111f31"/></linearGradient>
    <linearGradient id="wall" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#658097"/><stop offset=".28" stop-color="#293e54"/><stop offset="1" stop-color="#101c2f"/></linearGradient>
    <radialGradient id="glow"><stop stop-color="#a8ffff" stop-opacity=".9"/><stop offset="1" stop-color="#28a8d0" stop-opacity="0"/></radialGradient>
    </defs>{body}</svg>'''
    source=SRC/f'{name}.svg';source.write_text(st,encoding='utf-8')
    if out:
        cairosvg.svg2png(bytestring=st.encode(),write_to=str(out),output_width=w,output_height=h)
    return st

def alex(state):
    off={'idle':0,'walk':-3,'hurt':4,'victory':-6}[state]
    arms = ('<path d="M19 34l-10 11M45 34l9 10" stroke="#6f91ad" stroke-width="10" stroke-linecap="round"/>' if state!='victory' else '<path d="M19 34L7 12M45 34L56 10" stroke="#6f91ad" stroke-width="10" stroke-linecap="round"/>')
    body=f'''<ellipse cx="32" cy="62" rx="19" ry="6" fill="#000" opacity=".30"/>
    <path d="M22 46L19 {60+off} L29 62 L33 48M42 46L47 {60-off} L37 62 L32 48" fill="#244158" stroke="#a1cbd4" stroke-width="2"/>
    {arms}<path d="M20 28Q32 23 44 28L47 49Q32 55 17 49Z" fill="url(#steel)" stroke="#102338" stroke-width="3"/>
    <rect x="24" y="32" width="16" height="12" rx="3" fill="#1a3549" stroke="#7bd9d5" stroke-width="1.5"/>
    <path d="M24 39h16" stroke="#42ece3" stroke-width="3"/>
    <rect x="22" y="7" width="20" height="20" rx="8" fill="url(#steel)" stroke="#13273d" stroke-width="3"/>
    <path d="M23 14Q32 9 41 14V22Q32 25 23 22Z" fill="{'#c85966' if state=='hurt' else '#11263b'}" stroke="#6ed3e7" stroke-width="1.6"/>
    <path d="M26 18h12" stroke="{'#ffa0a0' if state=='hurt' else '#4ff1ef'}" stroke-width="2.5"/>
    <path d="M16 40h5M43 40h5" stroke="#ffbe73" stroke-width="3"/>'''
    if state=='victory':body+='<path d="M48 8l2-4 2 4 4 2-4 2-2 4-2-4-4-2Z" fill="#fce4a0"/>'
    if state=='hurt':body+='<path d="M6 21l8-5M51 52l7-4" stroke="#ed6675" stroke-width="3"/>'
    return svg('alex_'+state,64,68,body,SPR/f'alex_{state}.png')
for s in ('idle','walk','hurt','victory'):alex(s)
svg('nova',64,64,'''<circle cx="32" cy="32" r="24" fill="url(#glow)"/><path d="M16 25L32 15L49 25V42L32 51L16 42Z" fill="#1b4360" stroke="#72edff" stroke-width="3"/><path d="M24 31L30 36L41 27" fill="none" stroke="#baffff" stroke-width="3"/><circle cx="22" cy="21" r="3" fill="#a3e6ff"/><circle cx="44" cy="41" r="2.5" fill="#a3e6ff"/>''',SPR/'nova.png')
svg('drone',64,64,'''<ellipse cx="32" cy="53" rx="24" ry="7" fill="#000" opacity=".28"/><path d="M8 27L25 18L39 18L56 27L48 43L16 43Z" fill="url(#steel)" stroke="#16354c" stroke-width="3"/><path d="M13 33h10M41 33h10" stroke="#4cdef1" stroke-width="4"/><ellipse cx="32" cy="30" rx="12" ry="11" fill="#122c42" stroke="#74cbd9" stroke-width="2"/><ellipse cx="32" cy="30" rx="6" ry="5" fill="#ff7180"/><path d="M6 42h14M44 42h14" stroke="#5fe4f1" stroke-width="2"/>''',SPR/'drone.png')
svg('turret',64,64,'''<ellipse cx="32" cy="52" rx="24" ry="6" opacity=".2"/><rect x="8" y="13" width="48" height="40" rx="9" fill="url(#wall)" stroke="#a5bdcb" stroke-width="3"/><circle cx="32" cy="32" r="15" fill="#16283b" stroke="#a6cbd5" stroke-width="3"/><circle cx="32" cy="32" r="8" fill="#d46470"/><path d="M30 8h5V21h-5z" fill="#7b96a9"/><path d="M26 5h13v10H26z" fill="#486b82" stroke="#b2dde5"/>''',SPR/'turret.png')
svg('camera',64,64,'''<path d="M26 13L31 25" stroke="#8cacc3" stroke-width="7"/><rect x="12" y="19" width="42" height="25" rx="6" fill="url(#steel)" stroke="#a1c6d0" stroke-width="3"/><rect x="36" y="24" width="14" height="15" rx="4" fill="#1b2b43" stroke="#f57c83" stroke-width="2"/><circle cx="43" cy="31" r="4" fill="#f46a70"/><path d="M11 46h46" stroke="#426479" stroke-width="4"/>''',SPR/'camera.png')
svg('terminal',64,64,'''<rect x="12" y="8" width="40" height="50" rx="4" fill="url(#wall)" stroke="#87baca" stroke-width="3"/><rect x="17" y="13" width="30" height="26" rx="2" fill="#091f35" stroke="#61e5db" stroke-width="2"/><path d="M22 21h16M22 26h11M22 31h18" stroke="#66d6d7" stroke-width="2"/><circle cx="31" cy="49" r="4" fill="#83ffdf"/>''',SPR/'terminal.png')
svg('core',64,64,'''<rect x="8" y="8" width="48" height="48" rx="9" fill="url(#steel)" stroke="#81a6bd" stroke-width="3"/><circle cx="32" cy="32" r="19" fill="#14273e" stroke="#65eae7" stroke-width="2"/><circle cx="32" cy="32" r="10" fill="#408caa" stroke="#cbffff" stroke-width="2"/><path d="M13 32h38M32 13v38" stroke="#8be4f8" stroke-width="1.4" opacity=".7"/>''',SPR/'core.png')
svg('gate',48,48,'''<rect x="2" y="2" width="44" height="44" rx="2" fill="url(#steel)" stroke="#c0d4d9" stroke-width="2"/><path d="M13 3v42M24 3v42M35 3v42" stroke="#14283d" stroke-width="5"/><rect x="1" y="19" width="46" height="10" fill="#222f44" stroke="#ee7382" stroke-width="2"/><path d="M4 24h40" stroke="#ff8091" stroke-width="2" strokeDasharray="5 3"/>''',SPR/'gate.png')
svg('medkit',48,48,'''<rect x="6" y="12" width="36" height="29" rx="6" fill="#a1c9d1" stroke="#294b63" stroke-width="4"/><path d="M17 12v-5h14v5" fill="none" stroke="#a1c9d1" stroke-width="4"/><path d="M24 20v14M17 27h14" stroke="#e76e79" stroke-width="5"/>''',SPR/'medkit.png')
svg('battery',48,48,'''<rect x="12" y="10" width="24" height="31" rx="4" fill="#2a445b" stroke="#afc9cd" stroke-width="3"/><rect x="19" y="6" width="10" height="6" fill="#a3c8d2"/><path d="M26 17L19 28H26L22 36L32 24H25Z" fill="#7bf5c6"/>''',SPR/'battery.png')
svg('keycard',48,48,'''<rect x="6" y="12" width="36" height="26" rx="4" fill="#335a6b" stroke="#b2d5d8" stroke-width="3"/><path d="M10 29h28" stroke="#8becff" stroke-width="3"/><rect x="11" y="17" width="13" height="7" rx="2" fill="#d0ab65"/>''',SPR/'keycard.png')
svg('module',48,48,'''<rect x="9" y="9" width="30" height="30" rx="5" fill="url(#steel)" stroke="#80e7ef" stroke-width="3"/><path d="M18 4v7M30 4v7M18 37v7M30 37v7M4 18h7M4 30h7M37 18h7M37 30h7" stroke="#8bddeb" stroke-width="3"/><circle cx="24" cy="24" r="8" fill="#183650" stroke="#9ef7eb" stroke-width="2"/><circle cx="24" cy="24" r="3" fill="#acfff7"/>''',SPR/'module.png')
svg('note',48,48,'''<path d="M12 5h17l8 8v30H12Z" fill="#bad0d8" stroke="#3d697c" stroke-width="3"/><path d="M29 5v9h8M17 22h16M17 28h15M17 34h11" stroke="#47788d" stroke-width="2"/>''',SPR/'note.png')
svg('lure',48,48,'''<rect x="16" y="10" width="17" height="29" rx="6" fill="url(#steel)" stroke="#7adad8" stroke-width="3"/><circle cx="24" cy="21" r="6" fill="#f8ba73"/><path d="M24 5v6M12 12l5 4M35 12l-5 4" stroke="#f1bf81" stroke-width="3"/>''',SPR/'lure.png')
svg('exit',64,64,'''<rect x="6" y="4" width="52" height="56" rx="15" fill="url(#steel)" stroke="#83d9db" stroke-width="3"/><rect x="13" y="11" width="38" height="42" rx="9" fill="#12273b" stroke="#b2f1e5" stroke-width="2"/><path d="M17 31h29M32 20l13 11-13 11" fill="none" stroke="#6effc5" stroke-width="5"/>''',SPR/'exit.png')
# tile atlas 8x 48px
T=48
pieces=[
'<rect width="48" height="48" fill="url(#floor)"/><path d="M1 1h46v46H1z" fill="none" stroke="#2e465a" stroke-width="1"/><path d="M24 2v44M2 24h44" stroke="#31495b" opacity=".35"/>',
'<rect width="48" height="48" fill="url(#wall)"/><rect x="4" y="3" width="40" height="42" rx="3" fill="#273d53" stroke="#7c9aab" stroke-width="2"/><path d="M5 12h38M5 35h38" stroke="#132638" stroke-width="5"/><path d="M9 12h30" stroke="#668399" stroke-width="1"/>',
'<rect width="48" height="48" fill="#1e3042"/><path d="M3 23h42" stroke="#508da0" stroke-width="5"/><path d="M5 6v36M43 6v36" stroke="#334e63" stroke-width="2"/>',
'<rect width="48" height="48" fill="url(#floor)"/><rect x="9" y="9" width="30" height="30" fill="#162737" stroke="#536d7c" stroke-width="2"/><path d="M12 14h24M12 21h24M12 28h24M12 35h24" stroke="#5a7988" stroke-width="2"/>',
'<rect width="48" height="48" fill="url(#wall)"/><path d="M4 4L44 44M44 4L4 44" stroke="#354c60" stroke-width="8"/><circle cx="24" cy="24" r="7" fill="#536d7e" stroke="#9bb5c1"/>',
'<rect width="48" height="48" fill="#131f2f"/><path d="M4 4h40v40H4z" fill="none" stroke="#3f5a6f" stroke-width="1.5"/><circle cx="24" cy="24" r="11" fill="#1d3246" stroke="#4d738a"/>',
'<rect width="48" height="48" fill="url(#floor)"/><path d="M9 10h30M9 38h30" stroke="#b79a57" stroke-width="3" stroke-dasharray="8 5"/><path d="M22 14v20" stroke="#596f75" stroke-width="2"/>',
'<rect width="48" height="48" fill="url(#floor)"/><path d="M24 6L40 24L24 42L8 24Z" fill="none" stroke="#417283" stroke-width="2"/><path d="M16 24h16" stroke="#4be5d6" stroke-width="3"/>',
]
svg('tileset',384,48,''.join(f'<g transform="translate({i*48},0)">{part}</g>' for i,part in enumerate(pieces)),TILES/'tileset.png')
# Tiled sources: .tsx tileset and .tmj maps. TMJ is Tiled JSON readable without conversion.
(TILES/'tileset.tsx').write_text('''<?xml version="1.0" encoding="UTF-8"?>\n<tileset version="1.10" tiledversion="1.11.0" name="echo_station" tilewidth="48" tileheight="48" tilecount="8" columns="8">\n <image source="tileset.png" width="384" height="48"/>\n <tile id="1"><properties><property name="solid" type="bool" value="true"/></properties></tile>\n <tile id="4"><properties><property name="solid" type="bool" value="true"/></properties></tile>\n</tileset>\n''',encoding='utf-8')
# editable UI, logo and splash vectors
svg('logo',700,190,'''<rect width="700" height="190" rx="16" fill="#0b1627"/><path d="M15 8h670v174H15z" fill="none" stroke="#305567" stroke-width="2"/><text x="350" y="104" text-anchor="middle" font-family="DejaVu Sans,sans-serif" font-size="104" font-weight="bold" fill="#e3faff" letter-spacing="19">ECHO</text><path d="M45 123h610" stroke="#44d1ce" stroke-width="4"/><text x="350" y="159" text-anchor="middle" font-family="DejaVu Sans,sans-serif" font-size="27" fill="#8dd0d6" letter-spacing="8">ПОСЛЕДНИЙ СИГНАЛ</text>''',UI/'logo.png')
svg('cover',1200,650,'''<rect width="1200" height="650" fill="#081426"/><path d="M0 500L450 205H750L1200 500V650H0Z" fill="#162d43" stroke="#4b8291" stroke-width="10"/><path d="M450 205L300 0M750 205L900 0M0 500L260 0M1200 500L940 0" stroke="#3c5a72" stroke-width="15"/><path d="M0 510h1200M140 650l305-445M1060 650L755 205" stroke="#5c8a9b" stroke-width="8"/><path d="M450 205h300v185H450Z" fill="#0a1b2c" stroke="#58b7c3" stroke-width="8"/><circle cx="600" cy="300" r="61" fill="url(#glow)"/><circle cx="600" cy="300" r="29" fill="#2d96a2" stroke="#b1ffff" stroke-width="5"/><path d="M260 485v-125h135v125M805 485V360h135v125" fill="#172d40" stroke="#42798e" stroke-width="6"/><circle cx="385" cy="420" r="19" fill="#f26978"/><circle cx="815" cy="420" r="19" fill="#f26978"/><path d="M0 545h1200" stroke="#d56565" stroke-width="4" stroke-dasharray="22 25"/><text x="600" y="98" font-family="DejaVu Sans,sans-serif" font-size="90" font-weight="bold" letter-spacing="18" fill="#efffff" text-anchor="middle">ECHO</text><text x="600" y="146" font-family="DejaVu Sans,sans-serif" font-size="27" letter-spacing="7" fill="#78dcd9" text-anchor="middle">ПОСЛЕДНИЙ СИГНАЛ</text><text x="600" y="602" font-family="DejaVu Sans,sans-serif" font-size="25" fill="#afc8d9" text-anchor="middle">АТЛАС-9 • ЭВАКУАЦИЯ • ПРОТОКОЛ 09</text>''',UI/'cover.png')

W,H=40,27
# Level maps with intentional corridors; 3 vertical sectors, each with 3 connected rooms and several dead-end bays.
def make_layout(level):
    g=[['#' if x in(0,W-1) or y in(0,H-1) else '.' for x in range(W)] for y in range(H)]
    for x in (13,26):
        for y in range(1,H-1):g[y][x]='#'
    # secured sector gates: sole passages through the two vertical bulkheads
    for x in (13,26):g[13][x]='.'
    for y in (9,18):
        for x in range(1,W-1):
            if x not in (13,26): g[y][x]='#'
        for x in (7,20,33):g[y][x]='.'
    # Additional partial bulkheads create side chambers and false routes.
    # Escalate maze complexity after the training deck. All gaps remain traversable.
    if level >= 2:
        for base in (1,14,27):
            for yy in (2,3,4,5,6,7,8):
                if yy != 6:g[yy][base+5]='#'
            for xx in range(base+2,base+10):
                if xx != base+5:g[14][xx]='#'
            for yy in (20,21,22,23,24):
                if yy != 22:g[yy][base+6]='#'
    if level == 3:
        for xx in range(30,37):
            if xx!=34:g[22][xx]='#'
    # create interior obstacles + optional subrooms: deliberately don't block chokepoints
    furniture={
      1:[(4,5,3,1),(9,6,2,2),(16,3,2,2),(22,6,2,2),(30,4,3,1),(35,6,2,2),(3,12,2,2),(9,15,2,1),(17,12,2,1),(22,16,2,1),(29,11,3,1),(36,15,2,2),(4,21,3,1),(10,23,2,2),(16,21,3,1),(23,23,2,1),(29,22,2,2)],
      2:[(3,3,3,1),(9,5,2,2),(16,5,2,1),(21,3,3,1),(30,3,2,2),(35,6,2,1),(4,12,2,1),(10,15,2,2),(17,15,3,1),(22,11,2,2),(29,16,3,1),(35,12,2,2),(5,23,2,1),(9,20,3,1),(17,22,2,2),(23,20,2,1),(31,23,2,1)],
      3:[(4,4,3,1),(9,3,2,1),(16,6,2,1),(21,4,3,1),(31,5,2,2),(35,3,2,1),(3,13,2,2),(9,11,2,1),(17,12,2,2),(22,15,2,1),(29,12,3,1),(36,15,2,2),(5,22,2,1),(10,20,2,1),(17,23,2,1),(23,22,2,2),(31,21,2,1)],
    }[level]
    for x,y,w,h in furniture:
        for yy in range(y,y+h):
            for xx in range(x,x+w):g[yy][xx]='#'
    # gates and essential object approaches verified in test suite
    # mix panels grates and floor patterns deterministically
    r=random.Random(level*700)
    data=[]
    for y in range(H):
        for x in range(W):
            if g[y][x]=='#': t=2 if r.random()<.89 else 5
            else: t=r.choices([1,3,4,6,7,8],[72,8,9,4,4,3])[0]
            data.append(t)
    return data,g

def create_obj(name,typ,x,y,props=None):
    return {'id':create_obj.i,'name':name,'type':typ,'x':round(x*48,1),'y':round(y*48,1),'width':0,'height':0,'rotation':0,'visible':True,'point':True,'properties':[{'name':k,'type':'bool' if isinstance(v,bool) else 'int' if isinstance(v,int) else 'string','value':v} for k,v in (props or {}).items()]}
create_obj.i=1

LEVELS={
1:{'name':'ПРОБУЖДЕНИЕ','subtitle':'Медицинский сектор • Палуба C','start':(3.5,23.5),'goal':'Найти способ покинуть медицинский отсек.', 'core_off':'red','core_on':'yellow','clue':'Красное ядро питает турели. Жёлтое — спасательные шлюзы. Синее — связь.', 'dialog':'НОВА: Я обнаружила спасательную шлюпку. Но доступ к ней полностью заблокирован.'},
2:{'name':'МЁРТВЫЙ СЕКТОР','subtitle':'Лаборатории • Палуба B','start':(3.5,23.5),'goal':'Добраться до командного центра и восстановить шлюз.', 'core_off':'blue','core_on':'red','clue':'Синее ядро создаёт помехи. Красное стабилизирует вентиляцию. Жёлтое — резерв.', 'dialog':'НОВА: Память систем безопасности фрагментирована. Я всё ещё не могу восстановить весь протокол.'},
3:{'name':'ПОСЛЕДНИЙ СИГНАЛ','subtitle':'Командный центр • Палуба A','start':(3.5,23.5),'goal':'Изолировать Цербера и добраться до спасательной шлюпки.', 'core_off':'yellow','core_on':'blue','clue':'Жёлтый контур удерживает ангар. Синий управляет его питанием. Красный — диагностика.', 'dialog':'НОВА: Архив подтверждает: ты добровольно изолировал свою память, чтобы Цербер не получил коды доступа.'}
}
for level in (1,2,3):
    cfg=LEVELS[level];data,g=make_layout(level)
    # mandatory coords ensure not on walls
    objects=[]
    def add(name,typ,x,y,props=None):
        if typ not in ('gate','camera','turret') and g[int(y)][int(x)] == '#':
            choices=[(x+dx,y+dy) for dx,dy in ((0,-1),(0,1),(-1,0),(1,0),(-2,0),(2,0)) if 0<=int(x+dx)<W and 0<=int(y+dy)<H and g[int(y+dy)][int(x+dx)]!='#']
            if not choices: raise ValueError(f'blocked object {name} {x},{y}')
            x,y=choices[0]
        create_obj.i+=1; o=create_obj(name,typ,x,y,props);objects.append(o)
    add('Алекс — старт','spawn',*cfg['start'])
    add('Секторальный шлюз A','gate',13.5,13.5,{'gate_id':'A'})
    add('Секторальный шлюз B','gate',26.5,13.5,{'gate_id':'B'})
    add('Главный терминал','main_terminal',7.5,5.5)
    add('Энергетическое ядро','core',20.5,5.5)
    add('Спасательный переход' if level<3 else 'Спасательная шлюпка','exit',35.5,23.5)
    # modules across levels, placed in rooms
    if level==1:
        add('Модуль сканирования','module',7.5,22.5,{'ability':'scan'})
        add('Модуль взлома','module',7.5,14.5,{'ability':'hack'})
        add('Карта персонала','keycard',9.5,21.5)
    if level==2:
        add('Модуль маскировки','module',7.5,22.5,{'ability':'shield'})
        add('Модуль импульса','module',18.5,14.5,{'ability':'pulse'})
        add('Карта доступа B','keycard',9.5,21.5)
    if level==3:
        add('Модуль управления','module',7.5,22.5,{'ability':'control'})
        add('Модуль памяти','module',18.5,6.5,{'ability':'memory'})
        add('Карта доступа A','keycard',9.5,21.5)
    for x,y in [(4.5,6.5),(10.5,24.5),(31.5,14.5)]:add('Аптечка','medkit',x,y)
    for x,y in [(9.5,4.5),(17.5,24.5),(33.5,4.5)]:add('Батарея','battery',x,y)
    add('Отвлекающий маяк','lure',11.5,16.5)
    # notes and decoy objects
    add('Журнал аварии','note',4.5,14.5,{'text':'Журнал: аварийная блокировка выполнена вручную. Персонал эвакуирован не полностью.'})
    add('Запись о ядрах','note',19.5,7.5,{'text':cfg['clue']})
    add('Секретный архив','note',34.5,5.5,{'text':'АРХИВ: ЦЕРБЕР отключил аварийные каналы связи. НОВА имеет автономную копию ключей.'})
    add('Дополнительный терминал','aux_terminal',33.5,15.5)
    add('Ложный терминал','broken_terminal',31.5,21.5)
    for x,y,angle,sweep in [(5.5,11.5,30,50),(17.5,11.5,150,65),(30.5,8.5,70,60),(33.5,20.5,200,85)]:
        add('Камера наблюдения','camera',x,y,{'angle':angle,'sweep':sweep,'range':7+level,'id':f'C{level}-{x}'})
    for x,y in [(11.5,7.5),(23.5,16.5),(37.5,13.5)]:add('Автоматическая турель','turret',x,y,{'range':7})
    patrols=[(6.5,12.5,9.5,12.5),(19.5,14.5,22.5,14.5),(32.5,14.5,35.5,14.5)]
    for i,(x,y,px,py) in enumerate(patrols[:2+ (level>1)]):add('Патрульный дрон','drone',x,y,{'target_x':int(px),'target_y':int(py),'range':5+level,'id':f'D{level}-{i}'})
    tiled={'compressionlevel':-1,'height':H,'width':W,'infinite':False,'tileheight':48,'tilewidth':48,'nextlayerid':3,'nextobjectid':create_obj.i+1,'orientation':'orthogonal','renderorder':'right-down','tiledversion':'1.11.0','type':'map','version':'1.10',
    'layers':[{'id':1,'name':'Пол и стены','type':'tilelayer','width':W,'height':H,'x':0,'y':0,'opacity':1,'visible':True,'data':data}, {'id':2,'name':'Объекты — меняйте позиции мышкой','type':'objectgroup','x':0,'y':0,'opacity':1,'visible':True,'draworder':'topdown','objects':objects}],
    'tilesets':[{'firstgid':1,'source':'../assets/tiles/tileset.tsx'}], 'properties':[{'name':k,'type':'string','value':str(v)} for k,v in cfg.items() if k not in ('start',)]}
    (MAPS/f'level_{level}.tmj').write_text(json.dumps(tiled,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'story'/'levels.json').write_text(json.dumps(LEVELS,ensure_ascii=False,indent=2),encoding='utf-8')
print('Generated editable game art, tileset, TMJ maps and story. Levels: 3.')
