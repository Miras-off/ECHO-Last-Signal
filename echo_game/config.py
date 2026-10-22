"""Fixed canvas and design constants for ECHO."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'assets'
MODEL_DIR = ROOT / 'models' / 'vosk-model-small-ru-0.22'
SAVE_DIR = ROOT / 'save'
WIDTH, HEIGHT = 1360, 760
FPS = 60
TILE = 48
MAP_X, MAP_Y = 30, 94
GRID_W, GRID_H = 19, 12
PLAY_W, PLAY_H = GRID_W*TILE, GRID_H*TILE
PANEL_X = MAP_X+PLAY_W+28

INK = (8, 16, 30)
BG = (8, 13, 26)
SURFACE = (16, 29, 47)
SURFACE_2 = (23, 40, 60)
BORDER = (45, 70, 91)
TEXT = (226, 244, 249)
MUTED = (137, 169, 188)
CYAN = (76, 227, 225)
GREEN = (111, 230, 154)
ORANGE = (255, 187, 91)
RED = (255, 105, 112)
PURPLE = (144, 153, 255)
