from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
DEFAULT={
 'screen_width':1320,'screen_height':790,'fps':60,'tile_pixels':48,
 'palette':{'background':'#091523','panel':'#101f30','panel_alt':'#172b40','border':'#355366','text':'#e8f8fd','muted':'#96b4c2','accent':'#69e4dd','good':'#87e6b0','bad':'#f27885','gold':'#f6cd83'},
 'sound_enabled':True
}
def read_settings():
    path=ROOT/'assets'/'ui'/'theme.json'
    if not path.exists():path.write_text(json.dumps(DEFAULT,ensure_ascii=False,indent=2),encoding='utf-8')
    try: data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):data=DEFAULT
    return data
