"""Deterministic first-level gameplay. No dependencies on Pygame or microphones.

All coordinates in tile units. Rendering and input live in separate modules.
"""
from dataclasses import dataclass
from math import hypot, sin
from typing import Literal

LEVEL = [
    '###################',
    '#.......#.........#',
    '#..##...#.....##..#',
    '#.......#.........#',
    '#.......#.........#',
    '#.................#',
    '#.......#.........#',
    '#....#..#...##....#',
    '#.......#.........#',
    '#.......#.........#',
    '#.......#.........#',
    '###################',
]
assert len(LEVEL) == 12 and all(len(row) == 19 for row in LEVEL)

TERMINAL = (6.5, 3.5)
GATE = (8.5, 5.5)
CORE = (15.5, 3.5)
EXIT = (16.5, 9.5)
LASER = (5.5, 6.5)
CACHE = (3.5, 9.5)


@dataclass
class Player:
    x: float = 2.5
    y: float = 8.5
    hp: int = 100
    energy: float = 100.0
    facing: str = 'right'


class World:
    """Level 1: reveal the terminal, hack it, open the gate, activate the core."""

    def __init__(self):
        self.player = Player()
        self.time = 0.0
        self.points = 0
        self.errors = 0
        self.good_actions = 0
        self.revealed = False
        self.hacked = False
        self.gate_open = False
        self.core_active = False
        self.cache_taken = False
        self.status: Literal['playing', 'won', 'lost'] = 'playing'
        self.shield_until = 0.0
        self.pulse_until = 0.0
        self.last_damage_time = -10.0
        self.drone_x = 13.5
        self.drone_y = 8.5
        self.drone_dir = 1
        self.nova_x = 1.8
        self.nova_y = 8.8
        self.hint = 'Найди терминал на левой стороне станции.'
        self.message = 'НОВА: Слышишь меня? Надо восстановить связь!'
        self.message_type = 'info'
        self.messages = []
        self._record(self.message, 'info')

    def _record(self, message: str, kind: str = 'info'):
        self.message = message
        self.message_type = kind
        self.messages.append((self.time, message, kind))
        self.messages = self.messages[-8:]

    def distance(self, pos) -> float:
        return hypot(self.player.x-pos[0], self.player.y-pos[1])

    def near(self, pos, limit: float = 1.7) -> bool:
        return self.distance(pos) <= limit

    def _free(self, x: float, y: float) -> bool:
        radius = .27
        for px in (x-radius, x+radius):
            for py in (y-radius, y+radius):
                cx, cy = int(px), int(py)
                if cy < 0 or cy >= len(LEVEL) or cx < 0 or cx >= len(LEVEL[0]):
                    return False
                if LEVEL[cy][cx] == '#':
                    return False
                if not self.gate_open and (cx, cy) == (8, 5):
                    return False
        return True

    @property
    def difficulty(self) -> float:
        """Rule-based adaptive challenge (not a second neural network)."""
        if self.errors >= 4 or self.player.hp <= 35:
            return .7
        if self.good_actions >= 4 and self.errors <= 1:
            return 1.2
        return 1.0

    @property
    def laser_on(self) -> bool:
        return (self.time * self.difficulty) % 3.3 < 1.7

    @property
    def shielded(self) -> bool:
        return self.time < self.shield_until

    @property
    def drone_stunned(self) -> bool:
        return self.time < self.pulse_until

    def step(self, dt: float, dx: float = 0, dy: float = 0):
        if self.status != 'playing':
            return
        dt = max(0.0, min(float(dt), .06))
        self.time += dt
        p = self.player
        if dx or dy:
            length = hypot(dx, dy)
            dx, dy = dx/length, dy/length
            if abs(dx) > abs(dy):
                p.facing = 'right' if dx > 0 else 'left'
            else:
                p.facing = 'down' if dy > 0 else 'up'
            step = 3.55 * dt
            if self._free(p.x + dx*step, p.y):
                p.x += dx*step
            if self._free(p.x, p.y + dy*step):
                p.y += dy*step

        p.energy = min(100.0, p.energy + 2.3*dt)
        # Floating friendly companion; purely visual, never blocks the player.
        follow_x = max(1.5, p.x-.65)
        follow_y = p.y+.45
        self.nova_x += (follow_x-self.nova_x)*min(1.0, dt*2.8)
        self.nova_y += (follow_y-self.nova_y)*min(1.0, dt*2.8)

        # Drone patrol right of the security door.
        if not self.drone_stunned:
            self.drone_x += self.drone_dir * 1.15 * self.difficulty * dt
            if self.drone_x >= 16.3:
                self.drone_x, self.drone_dir = 16.3, -1
            elif self.drone_x <= 11.4:
                self.drone_x, self.drone_dir = 11.4, 1

        if self.laser_on and self.near(LASER, .55):
            self._damage(12, 'Лазерный барьер! -12 HP')
        if self.near((self.drone_x, self.drone_y), .72) and not self.drone_stunned:
            self._damage(18, 'Охранный дрон атакует! -18 HP')
        if not self.cache_taken and self.near(CACHE, .55):
            self.cache_taken = True
            p.energy = min(100, p.energy+28)
            self.points += 50
            self._record('Найдена энергокапсула. +50 очков, заряд восстановлен.', 'success')
        if self.core_active and self.near(EXIT, .61):
            self.status = 'won'
            self.points += max(0, 300-int(self.time*1.1))
            self._record('Канал открыт. Ты спас станцию! Миссия завершена.', 'success')

    def _damage(self, damage: int, text: str):
        if self.time-self.last_damage_time < 1.6:
            return
        self.last_damage_time = self.time
        if self.shielded:
            self._record('Щит поглотил урон!', 'success')
            return
        self.player.hp = max(0, self.player.hp-damage)
        self._record(text, 'error')
        if self.player.hp == 0:
            self.status = 'lost'
            self._record('Критическое состояние. Соединение потеряно.', 'error')

    def _fail(self, text: str):
        self.errors += 1
        self._record(text, 'error')
        return False

    def _success(self, text: str, score: int = 0):
        self.good_actions += 1
        self.points += score
        self._record(text, 'success')
        return True

    def command(self, name: str) -> bool:
        """Process player intention; return True if action succeeded."""
        if self.status != 'playing':
            return False
        if name == 'scan':
            if self.near(TERMINAL):
                if self.revealed:
                    self._record('НОВА: панель уже обнаружена.', 'info')
                    return True
                self.revealed = True
                return self._success('Сканирование завершено. Найдена скрытая панель!', 100)
            return self._fail('Для сканирования подойди к терминалу (голубой экран).')
        if name == 'hack':
            if not self.near(TERMINAL):
                return self._fail('Слишком далеко от терминала.')
            if not self.revealed:
                return self._fail('Сначала произнеси «Сканируй».')
            if self.hacked:
                self._record('Панель уже взломана.', 'info')
                return True
            self.hacked = True
            return self._success('Взлом успешен! Замок шлюза разблокирован.', 150)
        if name == 'open':
            if self.near(GATE, 1.9):
                if not self.hacked:
                    return self._fail('Шлюз заблокирован. Сначала взломай терминал.')
                if self.gate_open:
                    self._record('Шлюз уже открыт.', 'info')
                    return True
                self.gate_open = True
                return self._success('Шлюз открыт. Доберись до ядра станции!', 130)
            if self.near(EXIT, 1.9):
                if self.core_active:
                    return self._success('Аварийный выход разблокирован. Иди к нему!', 30)
                return self._fail('Аварийный выход заблокирован. Активируй ядро.')
            return self._fail('Рядом нет дверей, которые можно открыть.')
        if name == 'activate':
            if not self.near(CORE, 2.0):
                return self._fail('Для активации подойди к ядру в правом верхнем секторе.')
            if not self.gate_open:
                return self._fail('Доступ к ядру закрыт.')
            if self.core_active:
                self._record('Ядро уже активировано.', 'info')
                return True
            self.core_active = True
            return self._success('Резервный канал восстановлен! Иди к выходу внизу справа.', 250)
        if name == 'shield':
            if self.player.energy < 25:
                return self._fail('Недостаточно энергии для щита (нужно 25).')
            if self.shielded:
                self._record('Щит уже работает.', 'info')
                return True
            self.player.energy -= 25
            self.shield_until = self.time+4.0
            return self._success('Защитное поле включено на 4 секунды.')
        if name == 'pulse':
            if self.player.energy < 35:
                return self._fail('Недостаточно энергии для импульса (нужно 35).')
            if not self.near((self.drone_x, self.drone_y), 3.2):
                return self._fail('Рядом нет дрона для импульсного удара.')
            self.player.energy -= 35
            self.pulse_until = self.time+5.0
            return self._success('Электроимпульс! Дрон оглушён на 5 секунд.', 40)
        if name == 'status':
            self._record(f'НОВА: здоровье {self.player.hp}%, энергия {int(self.player.energy)}%, очки {self.points}.', 'info')
            return True
        if name == 'help':
            if not self.revealed:
                target = 'Ищи терминал на левой стороне. Подойди к нему и скажи «Сканируй».'
            elif not self.hacked:
                target = 'Теперь скажи «Взломай» рядом с терминалом.'
            elif not self.gate_open:
                target = 'Иди к зелёному шлюзу по центру и скажи «Открой».'
            elif not self.core_active:
                target = 'В правой части найди красное ядро и скажи «Активируй».'
            else:
                target = 'Доберись до выхода в правом нижнем углу!'
            self._record('НОВА: ' + target, 'info')
            return True
        return self._fail('Неизвестная команда. Нажми H для списка команд.')

    @property
    def objective(self) -> str:
        if not self.revealed:
            return 'Найти терминал и СКАНИРОВАТЬ'
        if not self.hacked:
            return 'ВЗЛОМАТЬ обнаруженный терминал'
        if not self.gate_open:
            return 'ОТКРЫТЬ центральный шлюз'
        if not self.core_active:
            return 'АКТИВИРОВАТЬ ядро станции'
        return 'Дойти до аварийного выхода'

    @property
    def progress(self) -> int:
        return sum((self.revealed, self.hacked, self.gate_open, self.core_active))
