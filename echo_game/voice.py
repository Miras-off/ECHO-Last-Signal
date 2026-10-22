"""Optional real Vosk microphone recognizer in worker thread. No fake speech recognition."""
import json, queue, threading
from pathlib import Path
from .commands import interpret, vocabulary
BASE=Path(__file__).resolve().parents[1]
MODEL=BASE/'models'/'vosk-model-small-ru-0.22'
class VoiceListener:
    def __init__(self):
        self.events=queue.Queue();self.stop_signal=threading.Event();self.thread=None;self.state='ВЫКЛ'
    def start(self):
        if self.thread is not None and self.thread.is_alive():return
        self.stop_signal.clear();self.state='ЗАПУСК...'
        self.thread=threading.Thread(target=self.worker,daemon=True,name='Vosk-ECHO')
        self.thread.start()
    def stop(self):self.stop_signal.set();self.state='ВЫКЛ'
    def worker(self):
        if not (MODEL/'am').exists():
            self.state='НЕТ МОДЕЛИ';self.events.put(('notice','Скачай модель: 03_DOWNLOAD_VOICE_MODEL.bat'));return
        try:
            import sounddevice as sd
            from vosk import Model,KaldiRecognizer,SetLogLevel
            SetLogLevel(-1);model=Model(str(MODEL))
            sample_rate=int(sd.query_devices(kind='input')['default_samplerate'])
            rec=KaldiRecognizer(model,sample_rate,json.dumps(vocabulary(),ensure_ascii=False))
            audio=queue.Queue(maxsize=35)
            def callback(indata,frames,time_info,status):
                if not self.stop_signal.is_set():
                    try:audio.put_nowait(bytes(indata))
                    except queue.Full:pass
            with sd.RawInputStream(samplerate=sample_rate,blocksize=4096,dtype='int16',channels=1,callback=callback):
                self.state='СЛУШАЕТ';self.events.put(('notice','Микрофон включён. Говори команды по-русски.'))
                while not self.stop_signal.is_set():
                    try:buf=audio.get(timeout=.2)
                    except queue.Empty:continue
                    if rec.AcceptWaveform(buf):
                        heard=json.loads(rec.Result()).get('text','').strip()
                        if heard:
                            self.events.put(('heard',heard))
                            command=interpret(heard)
                            if command:self.events.put(('command',command))
                            else:self.events.put(('notice','Не удалось определить команду: '+heard))
            self.state='ВЫКЛ'
        except Exception as exc:
            self.state='ОШИБКА';self.events.put(('notice',f'Ошибка микрофона: {type(exc).__name__}: {str(exc)[:75]}'))
    def poll(self):
        while True:
            try:yield self.events.get_nowait()
            except queue.Empty:return
