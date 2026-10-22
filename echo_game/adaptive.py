"""Local tabular Q-learning director for room-by-room difficulty.

This is NOT a downloaded neural network: a small, inspectable RL agent.
No network or personal data leaves the machine. Q-table persists as JSON.
"""
from __future__ import annotations
import json
from pathlib import Path

ACTIONS = (-1, 0, 1)  # ease, hold, intensify

class AdaptiveDirector:
    def __init__(self, path: Path):
        self.path=Path(path)
        try:
            raw=json.loads(self.path.read_text(encoding='utf-8'))
            self.q={str(k):[float(x) for x in v] for k,v in raw.get('q',{}).items()}
            self.updates=int(raw.get('updates',0))
        except (OSError,ValueError,TypeError):
            self.q={};self.updates=0
        self.previous_state=None
        self.previous_action=None
        self.last_stats=None
        self.last_time=0
        self.current_action=0
        self.current_factor=1.0
        self.last_reason='Начальная сбалансированная сложность'

    @staticmethod
    def state(stats,hp):
        trouble=(hp<40 or stats.get('damage',0)>45 or stats.get('errors',0)>3 or stats.get('detections',0)>3)
        strong=(hp>80 and stats.get('damage',0)<12 and stats.get('detections',0)==0 and stats.get('errors',0)==0)
        return 'struggling' if trouble else 'confident' if strong else 'balanced'

    def _row(self,state):
        if state not in self.q:
            # Mild prior: immediately help struggling players and challenge consistent players.
            self.q[state]=[.1,.2,.1]
            if state=='struggling':self.q[state]=[.7,.2,-.2]
            if state=='confident':self.q[state]=[-.2,.2,.6]
        return self.q[state]

    def advance(self,stats,hp,elapsed):
        """Called at a new room. Update prior Q action and choose new adjustment."""
        now_state=self.state(stats,hp)
        if self.previous_state is not None and self.last_stats is not None:
            new_damage=max(0,stats.get('damage',0)-self.last_stats.get('damage',0))
            new_detect=max(0,stats.get('detections',0)-self.last_stats.get('detections',0))
            new_errors=max(0,stats.get('errors',0)-self.last_stats.get('errors',0))
            duration=max(1,elapsed-self.last_time)
            # Reward fair challenge, not instant death or zero pressure.
            pressure=new_damage/22+new_detect*.7+new_errors*.45
            reward=1.2-abs(pressure-0.65)-max(0,12-duration)/15
            if hp<20:reward-=1.5
            old=self._row(self.previous_state)
            idx=ACTIONS.index(self.previous_action)
            old[idx]+=0.28*(reward+0.78*max(self._row(now_state))-old[idx])
            self.updates+=1
        row=self._row(now_state)
        best=max(range(3),key=lambda i:(row[i],-abs(ACTIONS[i])))
        action=ACTIONS[best]
        self.current_action=action
        self.current_factor=0.86 if action<0 else 1.15 if action>0 else 1.0
        self.last_reason={'struggling':'Много ошибок или потерь: система помогает','balanced':'Стабильный прогресс: обычная сложность','confident':'Уверенное прохождение: усиление охраны'}[now_state]
        self.previous_state=now_state
        self.previous_action=action
        self.last_stats=dict(stats)
        self.last_time=elapsed
        self.save()
        return self.current_factor, self.last_reason

    def save(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            self.path.write_text(json.dumps({'algorithm':'tabular-q-learning','updates':self.updates,'q':self.q},ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError:pass
