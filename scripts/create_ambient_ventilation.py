"""Create quiet non-tonal engine-room ambience from deterministic filtered noise."""
from pathlib import Path
import numpy as np
import wave
SAMPLE_RATE=22050
SECONDS=12
rng=np.random.default_rng(1909)
n=SAMPLE_RATE*SECONDS
white=rng.normal(size=n)
def smooth(a,size):
    s=np.cumsum(np.pad(a,(size,0),mode='wrap'))
    return (s[size:]-s[:-size])/size
low=smooth(white,130)
mid=smooth(white,8)-smooth(white,80)
# No steady sinusoidal generators: air movement with gentle slow variations.
time=np.arange(n)/SAMPLE_RATE
wind=0.70*low/(np.std(low)+1e-8)+0.30*mid/(np.std(mid)+1e-8)
level=(0.70+0.10*np.sin(2*np.pi*time/13)+0.05*np.sin(2*np.pi*time/6.5))
signal=wind*level
fade=int(SAMPLE_RATE*.25)
signal[:fade]*=np.linspace(0,1,fade)
signal[-fade:]*=np.linspace(1,0,fade)
signal=signal/(np.max(np.abs(signal))+1e-8)*.09
path=Path(__file__).resolve().parents[1]/'assets'/'audio'/'ambient.wav'
with wave.open(str(path),'wb') as out:
    out.setnchannels(1);out.setsampwidth(2);out.setframerate(SAMPLE_RATE)
    out.writeframes((signal*32767).astype('<i2').tobytes())
print('wrote',path)
