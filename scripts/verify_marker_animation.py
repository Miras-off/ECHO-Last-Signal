"""Capture spaced gameplay frames and verify that marker rings visibly animate."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from pathlib import Path
import pygame

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from echo_game.game import Game


game=Game()
game.start()
game.world.player.x,game.world.player.y=7.5,14.5
game.world.abilities.update(("scan","hack"))
game.world.inventory.update({"keycard":1,"lure":1})
game.world.alert=36
game.world.time=18.0

sample=pygame.Rect(245,115,625,435)
frames=[]
raw_frames=[]
for frame_index in range(4):
    game.draw()
    frame=game.window.subsurface(sample).copy()
    frames.append(frame)
    raw_frames.append(pygame.image.tobytes(frame,"RGB"))
    if frame_index<3:
        pygame.time.wait(340)

changed=[]
for previous,current in zip(raw_frames,raw_frames[1:]):
    changed.append(sum(a!=b for a,b in zip(previous,current)))
if min(changed)<80:
    raise RuntimeError(f"Marker animation was not visible enough between frames: {changed}")

thumb_size=(438,305)
sheet=pygame.Surface((900,650))
sheet.fill((3,9,15))
font=pygame.font.Font(None,24)
for index,frame in enumerate(frames):
    thumb=pygame.transform.smoothscale(frame,thumb_size)
    x=8+(index%2)*446
    y=28+(index//2)*313
    sheet.blit(thumb,(x,y))
    pygame.draw.rect(sheet,(54,185,215),(x,y,thumb_size[0],thumb_size[1]),1)
    label=font.render(f"FRAME {index+1}  +{index*0.34:.2f}s",True,(208,236,242))
    sheet.blit(label,(x+8,y-23))

target=ROOT/"docs"/"previews"/"v2_1_marker_animation_frames.png"
target.parent.mkdir(parents=True,exist_ok=True)
pygame.image.save(sheet,str(target))
pygame.quit()

print(target)
print("Changed RGB bytes between frames:",changed)
