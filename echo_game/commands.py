"""Small, auditable command interpreter shared by speech and keyboard controls.

Speech-to-text is performed by the real Vosk model in voice.py. This module
only converts its Russian text output into a finite set of game intentions.
"""
import re

COMMANDS = (
    ('scan', 'Сканируй', '1'),
    ('hack', 'Взломай', '2'),
    ('open', 'Открой', '3'),
    ('shield', 'Щит', '4'),
    ('activate', 'Активируй', '5'),
    ('help', 'Помощь', '6'),
    ('status', 'Статус', '7'),
    ('pulse', 'Импульс', '8'),
)

PHRASES = {
    'scan': ('сканируй', 'сканировать', 'просканируй', 'сканирование', 'осмотри', 'найди панель'),
    'hack': ('взломай', 'взломать', 'взлом', 'хакни'),
    'open': ('открой', 'открыть', 'открывай', 'открой дверь'),
    'shield': ('щит', 'защита', 'защити', 'включи защиту'),
    'activate': ('активируй', 'активация', 'активировать', 'запусти ядро'),
    'help': ('помощь', 'помоги', 'подсказка', 'что делать'),
    'status': ('статус', 'состояние', 'отчет', 'отчёт'),
    'pulse': ('импульс', 'оглуши', 'электроимпульс'),
}


def clean_text(text: str) -> str:
    text = str(text).lower().replace('ё', 'е')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-zа-я\s]', ' ', text)).strip()


def interpret(text: str) -> str | None:
    """Find known commands inside natural phrases. None means unrecognised."""
    cleaned = f' {clean_text(text)} '
    if not cleaned.strip():
        return None
    # Longer phrases first so short words cannot incorrectly pre-empt a phrase.
    possibilities = sorted(
        ((clean_text(phrase), command) for command, aliases in PHRASES.items() for phrase in aliases),
        key=lambda item: -len(item[0]),
    )
    for phrase, command in possibilities:
        if f' {phrase} ' in cleaned:
            return command
    return None


def vocabulary() -> list[str]:
    """Restricted Vosk grammar reduces irrelevant transcripts/noise."""
    phrases = [phrase for aliases in PHRASES.values() for phrase in aliases]
    return sorted(set(phrases)) + ['[unk]']
