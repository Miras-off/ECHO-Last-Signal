"""Restricted Russian speech vocabulary -> game intentions. Vosk is real ML in voice.py."""
import re
ACTIONS=[
 ('scan','Сканируй','1'),('connect','Подключение','2'),('hack','Взломай','3'),('open','Открой','4'),
 ('shield','Щит','5'),('pulse','Импульс','6'),('help','Нова / помощь','7'),
 ('off_red','Отключи красное','8'),('on_yellow','Активируй жёлтое','9'),
 ('off_blue','Отключи синее','0'),('on_red','Активируй красное','-'),
 ('off_yellow','Отключи жёлтое','='),('on_blue','Активируй синее','Backspace')]
ALIASES={
 'scan':['сканируй','сканирование','просканируй','сканировать'],
 'connect':['подключение','подключись','подключи терминал','соединись'],
 'hack':['взломай','взлом','взломать'],
 'open':['открой','открыть шлюз','открой дверь','открой шлюз'],
 'shield':['щит','маскировка','активируй щит','скрой меня'],
 'pulse':['импульс','оглуши дрона','электромагнитный импульс'],
 'help':['нова','помощь','подскажи','что делать'],
 'medkit':['аптечка','используй аптечку'],
 'battery':['батарея','восстанови энергию'],
 'lure':['маяк','отвлеки дрона'],
}
for color,adjs in {'red':['красное','красный'],'blue':['синее','синий'],'yellow':['желтое','желтый','жёлтое','жёлтый']}.items():
    for action,verbs in {'off':['отключи','выключи','деактивируй'],'on':['активируй','включи','запусти']}.items():
        ALIASES[f'{action}_{color}']=[f'{v} {a}' for v in verbs for a in adjs]

def clean(text):
    return re.sub(r'\s+',' ',re.sub(r'[^a-zа-я\s]',' ',str(text).lower().replace('ё','е'))).strip()

def interpret(text):
    text=' '+clean(text)+' '
    if not text.strip():return None
    possibilities=sorted(((clean(p),name) for name,phrases in ALIASES.items() for p in phrases),key=lambda item:-len(item[0]))
    for phrase,name in possibilities:
        if ' '+phrase+' ' in text:return name
    return None

def vocabulary():
    return sorted(set(p for phrases in ALIASES.values() for p in phrases))+['[unk]']
