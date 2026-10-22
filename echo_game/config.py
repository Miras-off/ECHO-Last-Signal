from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
DEFAULT={
 'screen_width':1366,'screen_height':768,'fps':60,'tile_pixels':64,
 'fullscreen':True,
 'ambient_enabled':False,
 'fog_enabled':True,
 'master_volume':70,
 'music_enabled':True,
 'music_volume':50,
 'sfx_volume':72,
 'voice_volume':70,
 'ui_scale':100,
 'palette':{
  'background':'#030910',
  'panel':'#07131f',
  'panel_alt':'#0a1b29',
  'panel_soft':'#10283a',
  'border':'#1e4962',
  'text':'#e8f7fb',
  'muted':'#789aac',
  'accent':'#45dff4',
  'good':'#68e5bd',
  'bad':'#ff5268',
  'gold':'#e9b95f'
 },
 'sound_enabled':True
}

def _path():
    return ROOT/'assets'/'ui'/'theme.json'

def read_settings():
    path=_path()
    if not path.exists():
        path.write_text(json.dumps(DEFAULT,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        data=DEFAULT.copy()
    merged=json.loads(json.dumps(DEFAULT,ensure_ascii=False))
    for k,v in data.items():
        if isinstance(v,dict) and isinstance(merged.get(k),dict):
            merged[k].update(v)
        else:
            merged[k]=v
    return merged

def save_settings(data):
    path=_path()
    merged=read_settings()
    for k,v in data.items():
        if isinstance(v,dict) and isinstance(merged.get(k),dict):
            merged[k].update(v)
        else:
            merged[k]=v
    path.write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
    return merged
