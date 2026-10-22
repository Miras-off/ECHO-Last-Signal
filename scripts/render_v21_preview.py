"""Render a deterministic gameplay frame for visual QA without opening a window."""
import os
import sys
import time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from pathlib import Path
import pygame

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from echo_game.game import Game
game=Game()
game.draw()
menu_target=ROOT/"docs"/"previews"/"v2_1_menu.png"
menu_target.parent.mkdir(parents=True,exist_ok=True)
pygame.image.save(game.window,str(menu_target))
game.start()
game.world.player.x,game.world.player.y=7.5,14.5
game.world.abilities.update(("scan","hack"))
game.world.inventory.update({"keycard":1,"lure":1})
game.world.alert=36
game.world.time=18.0
started=time.perf_counter()
for _ in range(60):
    game.world.time+=1/60
    game.draw()
elapsed=time.perf_counter()-started
target=ROOT/"docs"/"previews"/"v2_1_gameplay.png"
target.parent.mkdir(parents=True,exist_ok=True)
pygame.image.save(game.window,str(target))
pygame.quit()
print(target)
print(menu_target)
print(f"Headless render: {60/elapsed:.1f} FPS")
