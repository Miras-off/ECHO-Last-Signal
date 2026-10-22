"""Download and safely unpack the official small Russian Vosk model.

Run after setup: python download_voice_model.py
"""
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile
import shutil
import sys

BASE = Path(__file__).resolve().parent
NAME = 'vosk-model-small-ru-0.22'
URL = 'https://alphacephei.com/vosk/models/' + NAME + '.zip'
DEST = BASE / 'models' / NAME
ZIPFILE = BASE / 'models' / (NAME + '.zip')


def progress(blocks, block_size, total):
    if total > 0:
        percent = min(100, int(blocks * block_size / total * 100))
        print(f'\rЗагрузка русской модели Vosk: {percent:3d}%', end='', flush=True)


def main():
    if (DEST / 'am').exists() and (DEST / 'conf').exists():
        print('Модель уже установлена:', DEST)
        return
    DEST.parent.mkdir(exist_ok=True, parents=True)
    print('Источник:', URL)
    print('Объём архива около 45 МБ. Требуется доступ к интернету.\n')
    try:
        urlretrieve(URL, ZIPFILE, progress)
        print('\nРаспаковка...')
        with ZipFile(ZIPFILE) as archive:
            for info in archive.infolist():
                target = (DEST.parent / info.filename).resolve()
                if not target.is_relative_to(DEST.parent.resolve()):
                    raise RuntimeError('Некорректный путь внутри архива модели')
            archive.extractall(DEST.parent)
        if not (DEST / 'am').exists():
            raise RuntimeError('В скачанной модели отсутствует папка am')
        print('ГОТОВО! Можно запускать игру и нажать F8 для микрофона.')
    except Exception as exc:
        print('\nОшибка загрузки:', exc)
        print('Скачай архив вручную по URL выше и распакуй в папку models/')
        raise SystemExit(1)
    finally:
        ZIPFILE.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
