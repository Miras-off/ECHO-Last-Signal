"""Render four phases of every combat effect and reject static output."""
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


game=Game();game.mode='play'
phases=(.14,.38,.64,.88)


def turret_scene():
    world=World(1);turret=next(o for o in world.objects if o['type']=='turret')
    world.player.x,world.player.y=10.5,2.5
    event=world.combat_fx('turret_shot',(turret['x'],turret['y']),(world.player.x,world.player.y),duration=.34)
    return world,event


def drone_scene():
    world=World(1);drone=world.drones[0]
    world.player.x,world.player.y=8.8,12.5
    event=world.combat_fx('drone_attack',(drone.x,drone.y),(world.player.x,world.player.y),duration=.48)
    return world,event


def pulse_scene():
    world=World(2,abilities={'pulse'});drone=world.drones[0]
    world.player.x,world.player.y=8.2,13.2
    drone.stunned=5;drone.state='stunned'
    event=world.combat_fx('player_pulse',(world.player.x,world.player.y),targets=[(drone.x,drone.y)],duration=.78)
    return world,event


rows=[];metrics=[]
for label,factory in (('TURRET SHOT',turret_scene),('DRONE ATTACK',drone_scene),('PLAYER EMP',pulse_scene)):
    world,event=factory();frames=[];raw=[]
    for phase in phases:
        world.time=event['start']+event['duration']*phase
        game.world=world;game.combat_layer.fill((0,0,0,0));game.draw()
        image=game.window.subsurface(pygame.Rect(0,0,VW,VH)).copy()
        frames.append(image);raw.append(pygame.image.tobytes(game.combat_layer,'RGBA'))
    changes=[sum(a!=b for a,b in zip(previous,current)) for previous,current in zip(raw,raw[1:])]
    if min(changes)<100:
        raise RuntimeError(f'{label} appears static: {changes}')
    rows.append((label,frames));metrics.append((label,changes))

thumb=(250,180);label_width=150;top=30;row_height=205
sheet=pygame.Surface((label_width+thumb[0]*4+18,top+row_height*3))
sheet.fill((3,9,15));font=pygame.font.Font(None,24);small=pygame.font.Font(None,19)
for column,phase in enumerate(phases):
    sheet.blit(small.render(f'{phase*100:.0f}%',True,(111,210,228)),(label_width+column*thumb[0]+8,7))
for row,(label,frames) in enumerate(rows):
    y=top+row*row_height
    sheet.blit(font.render(label,True,(215,240,244)),(8,y+8))
    for column,image in enumerate(frames):
        x=label_width+column*thumb[0]
        scaled=pygame.transform.smoothscale(image,thumb)
        sheet.blit(scaled,(x,y))
        pygame.draw.rect(sheet,(53,190,216),(x,y,thumb[0],thumb[1]),1)

target=ROOT/'docs'/'previews'/'v2_1_combat_animation_frames.png'
target.parent.mkdir(parents=True,exist_ok=True)
pygame.image.save(sheet,str(target))
pygame.quit()
print(target)
for label,changes in metrics:print(label,changes)
