"""Regression checks for the on-screen countdown (without requiring Pygame)."""
from pathlib import Path
import ast


def test_ui_implements_free_life_countdown_and_unlock():
    source=Path(__file__).resolve().parents[1].joinpath('echo_game','game.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Game')
    funcs={node.name:node for node in cls.body if isinstance(node,ast.FunctionDef)}
    assert {'countdown','regeneration_label','locked','store','menu','result'} <= set(funcs)
    assert 'recovery_status()' in source
    assert 'ВОССТАНОВЛЕНА' in source
    assert 'БЕСПЛАТНО +1 ЖИЗНЬ ЧЕРЕЗ' in source
    assert 'МОЖНО ПРОДОЛЖАТЬ!' in source


def test_no_old_no_free_lives_copy_remains():
    src=Path(__file__).resolve().parents[1]
    for name in ('README.md','docs/MONETIZATION_V2_1_3.md','echo_game/game.py'):
        text=(src/name).read_text(encoding='utf-8').lower()
        assert 'бесплатного восстановления нет' not in text
        assert 'восстановления по таймеру' not in text or name.endswith('.md')
