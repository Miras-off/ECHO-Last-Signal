"""Render deterministic QA frames for combat FX and doorway fog preview."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from pathlib import Path
import pygame

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from echo_game.game import Game,VW,VH
from echo_game.world import World


game=Game()
game.mode='play'


def frame(world):
    game.world=world
    game.draw()
    return game.window.subsurface(pygame.Rect(0,0,VW,VH)).copy()


panels=[]

turret_world=World(1)
turret=next(o for o in turret_world.objects if o['type']=='turret')
turret_world.player.x,turret_world.player.y=10.5,2.5
turret_world.time=10.0
event=turret_world.combat_fx('turret_shot',(turret['x'],turret['y']),(turret_world.player.x,turret_world.player.y),duration=.34)
event['start']=turret_world.time-.17
panels.append(('TURRET SHOT',frame(turret_world)))

drone_world=World(1)
drone=drone_world.drones[0]
drone_world.player.x,drone_world.player.y=8.8,12.5
drone_world.time=10.0
event=drone_world.combat_fx('drone_attack',(drone.x,drone.y),(drone_world.player.x,drone_world.player.y),duration=.48)
event['start']=drone_world.time-.29
panels.append(('DRONE ATTACK',frame(drone_world)))

pulse_world=World(2,abilities={'pulse'})
pulse_drone=pulse_world.drones[0]
pulse_world.player.x,pulse_world.player.y=8.2,13.2
pulse_world.time=10.0
pulse_drone.stunned=15.0;pulse_drone.state='stunned'
event=pulse_world.combat_fx('player_pulse',(pulse_world.player.x,pulse_world.player.y),targets=[(pulse_drone.x,pulse_drone.y)],duration=.78)
event['start']=pulse_world.time-.38
panels.append(('PLAYER EMP PULSE',frame(pulse_world)))

fog_world=World(1)
fog_world.time=1.8
panels.append(('DOORWAY THREAT PREVIEW',frame(fog_world)))

thumb=(480,344)
sheet=pygame.Surface((984,744))
sheet.fill((3,9,15))
font=pygame.font.Font(None,25)
for index,(title,panel) in enumerate(panels):
    x=8+(index%2)*488
    y=28+(index//2)*364
    image=pygame.transform.smoothscale(panel,thumb)
    sheet.blit(image,(x,y))
    pygame.draw.rect(sheet,(53,190,216),(x,y,thumb[0],thumb[1]),1)
    sheet.blit(font.render(title,True,(215,240,244)),(x+8,y-23))

target=ROOT/'docs'/'previews'/'v2_1_combat_and_fog.png'
target.parent.mkdir(parents=True,exist_ok=True)
pygame.image.save(sheet,str(target))
pygame.quit()
print(target)
