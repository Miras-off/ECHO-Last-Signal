"""Render PNG previews from editable .tmj without pygame. Maps are the source of truth."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'assets/sprites';OUT=ROOT/'docs/previews';OUT.mkdir(parents=True,exist_ok=True)
atlas=Image.open(ROOT/'assets/tiles/tileset.png').convert('RGBA')
for n in (1,2,3):
    data=json.loads((ROOT/'maps'/f'level_{n}.tmj').read_text(encoding='utf-8'))
    scale=32;width=data['width'];height=data['height'];result=Image.new('RGBA',(width*scale,height*scale),(5,12,23))
    tiles=data['layers'][0]['data']
    for y in range(height):
        for x in range(width):
            gid=tiles[y*width+x];tile=atlas.crop(((gid-1)*48,0,gid*48,48)).resize((scale,scale))
            result.alpha_composite(tile,(x*scale,y*scale))
    dr=ImageDraw.Draw(result,'RGBA')
    pics={'main_terminal':'terminal','aux_terminal':'terminal','broken_terminal':'terminal','core':'core','exit':'exit','module':'module','medkit':'medkit','keycard':'keycard','battery':'battery','drone':'drone','camera':'camera','turret':'turret','note':'note','gate':'gate','lure':'lure','spawn':'alex_idle'}
    for obj in data['layers'][1]['objects']:
        asset=pics.get(obj['type'])
        if not asset:continue
        icon=Image.open(SRC/(asset+'.png')).convert('RGBA');icon.thumbnail((29,29))
        px=int(obj['x']/48*scale-icon.width/2);py=int(obj['y']/48*scale-icon.height/2)
        result.alpha_composite(icon,(px,py))
    outfile=OUT/f'level_{n}_overview.png';result.convert('RGB').save(outfile,quality=94)
    print(outfile)
