"""Regenerate PNG assets from edited SVG files without overwriting editable Tiled maps."""
from pathlib import Path
import cairosvg
ROOT=Path(__file__).resolve().parents[1]
for src in (ROOT/'assets/source_svg').glob('*.svg'):
    if src.stem in ('tileset',):dest=ROOT/'assets/tiles'/(src.stem+'.png')
    elif src.stem in ('logo','cover'):dest=ROOT/'assets/ui'/(src.stem+'.png')
    else:dest=ROOT/'assets/sprites'/(src.stem+'.png')
    cairosvg.svg2png(url=str(src),write_to=str(dest))
    print(src.name,'→',dest.relative_to(ROOT))
