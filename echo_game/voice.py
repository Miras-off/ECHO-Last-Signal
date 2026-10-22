"""Optional real offline speech recognition in a background thread.

Never fake recognition: without Vosk, microphone, or language model the status
shows the missing prerequisite and keyboard shortcuts remain usable.
"""
import json
import queue
import threading
from pathlib import Path

from .commands import interpret, vocabulary
from .config import MODEL_DIR


class VoiceListener:
    def __init__(self, model_path: Path = MODEL_DIR):
        self.model_path = Path(model_path)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.stop_signal = threading.Event()
        self.thread: threading.Thread | None = None
        self.state = 'ВЫКЛ'

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_signal.clear()
        self.state = 'ЗАПУСК...'
        self.thread = threading.Thread(target=self._worker, daemon=True, name='VoskMicrophone')
        self.thread.start()

    def stop(self):
        self.stop_signal.set()
        self.state = 'ВЫКЛ'
        # Never join the audio thread on the rendering thread; close via event.

    def _worker(self):
        try:
            if not self.model_path.is_dir() or not (self.model_path / 'am').exists():
                self.state = 'НЕТ МОДЕЛИ'
                self.events.put(('notice', 'Сначала запусти 03_DOWNLOAD_VOICE_MODEL.bat'))
                return
            try:
                import sounddevice as sd
                from vosk import KaldiRecognizer, Model, SetLogLevel
            except ImportError as exc:
                self.state = 'НЕТ БИБЛИОТЕК'
                self.events.put(('notice', f'Нет голосовой библиотеки: {exc.name}. Запусти 01_SETUP.bat'))
                return
            SetLogLevel(-1)
            model = Model(str(self.model_path))
            rate = int(sd.query_devices(kind='input')['default_samplerate'])
            rec = KaldiRecognizer(model, rate, json.dumps(vocabulary(), ensure_ascii=False))
            rec.SetWords(False)
            audio: queue.Queue[bytes] = queue.Queue(maxsize=30)

            def callback(indata, frames, time_info, status):
                if self.stop_signal.is_set():
                    return
                try:
                    audio.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            with sd.RawInputStream(samplerate=rate, blocksize=4096, dtype='int16',
                                   channels=1, callback=callback):
                self.state = 'СЛУШАЕТ'
                self.events.put(('notice', 'Микрофон активен. Произноси команды по-русски.'))
                while not self.stop_signal.is_set():
                    try:
                        data = audio.get(timeout=.25)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        transcript = result.get('text', '').strip()
                        if transcript:
                            self.events.put(('heard', transcript))
                            command = interpret(transcript)
                            if command:
                                self.events.put(('command', command))
            self.state = 'ВЫКЛ'
        except Exception as exc:  # audio hardware / library failures must not crash game
            self.state = 'ОШИБКА'
            self.events.put(('notice', f'Микрофон: {type(exc).__name__}: {str(exc)[:90]}'))

    def poll(self):
        while True:
            try:
                yield self.events.get_nowait()
            except queue.Empty:
                break
