"""Create royalty-free ORIGINAL procedural WAV effects. Editable in Audacity."""
from pathlib import Path
import wave, math, random, struct
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/audio';OUT.mkdir(parents=True,exist_ok=True)
RATE=22050
rng=random.Random(901)

def tone(t,f,shape='sin'):
    a=2*math.pi*f*t
    return math.sin(a) if shape=='sin' else (2*((t*f)%1)-1) if shape=='saw' else math.sin(a)*math.sin(a*.32)

def save(name,seconds,func,volume=.4):
    frames=[]
    for i in range(int(RATE*seconds)):
        t=i/RATE; v=func(t,seconds);v=max(-1,min(1,v*volume))
        frames.append(struct.pack('<h',int(32767*v)))
    with wave.open(str(OUT/(name+'.wav')),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE);w.writeframes(b''.join(frames))

def env(t,d,attack=.02,release=.14):return min(1,t/attack,(d-t)/release) if 0<=t<=d else 0
save('pickup',.26,lambda t,d: env(t,d)*(tone(t,700+1400*t/d)+.45*tone(t,1040+1100*t/d)),.22)
save('module',.72,lambda t,d: env(t,d,.07,.24)*(tone(t,392)+tone(t,523)+tone(t,784)+.5*tone(t,1047)),.16)
save('scan',.64,lambda t,d:env(t,d,.01,.3)*(tone(t,300+1250*t/d,'saw')*.38+tone(t,940)),.21)
save('hack',.40,lambda t,d:env(t,d,.01,.15)*(.6*tone(t,280+1300*t/d,'saw')+.4*tone(t,800+120*t)),.21)
save('door',.85,lambda t,d:env(t,d,.04,.2)*(tone(t,110-25*t/d,'saw')*.6+tone(t,180-40*t/d)),.23)
save('alarm',1.4,lambda t,d:env(t,d,.01,.1)*tone(t,530 if int(t*3)%2 else 710,'saw'),.17)
save('pulse',.60,lambda t,d:env(t,d,.008,.44)*(tone(t,150+2200*(1-t/d),'saw')*.5+tone(t,80+60*t/d)),.24)
save('damage',.43,lambda t,d:env(t,d,.01,.3)*(tone(t,95+240*t,'saw')+.3*(rng.random()*2-1)),.18)
save('click',.14,lambda t,d:env(t,d,.005,.08)*tone(t,820),.22)
save('victory',1.65,lambda t,d:env(t,d,.07,.45)*sum(tone(t,f) for f in [392,523,659,784])/4,.28)
save('drone',.42,lambda t,d:env(t,d,.01,.1)*(tone(t,250+95*math.sin(t*16),'saw')*.35+tone(t,490)),.14)
save('ambient',8.0,lambda t,d:env(t,d,1,1)*(tone(t,60+1.5*math.sin(t), 'saw')*.16+tone(t,119)*.11+tone(t,180)*.055),.30)
print('Original sound effects generated:',len(list(OUT.glob('*.wav'))))
