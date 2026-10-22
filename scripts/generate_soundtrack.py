"""Regenerate original ECHO sci-fi soundtrack and effects. No samples/licensed content.
Requirements: numpy, scipy, soundfile (for OGG). Not needed to PLAY the game.
  python scripts/generate_soundtrack.py
All music is generated as 16s OGG Vorbis loops; effects are editable PCM WAV.
"""
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets'/'audio'; OUT.mkdir(parents=True,exist_ok=True)
SR=24000
rng=np.random.default_rng(20261022)

def filter_noise(n,cut=700,high=False):
    white=rng.standard_normal(n).astype('float32')
    sos=butter(2,cut,fs=SR,output='sos',btype='highpass' if high else 'lowpass')
    a=sosfilt(sos,white).astype('float32')
    return a/(np.std(a)+1e-7)

def envelope(n,a=.025,r=.22):
    e=np.ones(n,dtype='float32')
    aa=min(n,int(a*SR));rr=min(n,int(r*SR))
    if aa:e[:aa]=np.sin(np.linspace(0,np.pi/2,aa))**2
    if rr:e[-rr:]=np.cos(np.linspace(0,np.pi/2,rr))**2
    return e

def phasor(freq,n):
    f=np.asarray(freq)
    if f.ndim==0:return 2*np.pi*float(f)*np.arange(n,dtype='float64')/SR
    return 2*np.pi*np.cumsum(f,dtype='float64')/SR

def tone(freq,n,texture='round'):
    p=phasor(freq,n)
    if texture=='round':return .76*np.sin(p)+.17*np.sin(2*p)+.07*np.sin(3*p)
    if texture=='metal':return .64*np.sin(p)+.22*np.sin(2.71*p)+.14*np.sin(5.1*p)
    if texture=='air':return .88*np.sin(p)+.12*np.sin(2*p)
    return np.sin(p)

def spread(x,width=.022,wet=.14):
    d=int(SR*width)
    l=x.copy();r=x.copy()
    l[d:]+=wet*x[:-d]
    r[d+97:]+=wet*x[:-(d+97)]
    return np.stack((l,r),axis=-1)

def save_effect(name,signal,base=.68,wet=.13):
    x=np.asarray(signal,dtype='float32');x=np.nan_to_num(x)
    # restrained output, preserve dynamics and avoid clipping
    peak=np.max(np.abs(x)) or 1
    x=np.tanh(x/(max(.45,peak))*1.1)*base
    a=spread(x,wet=wet)
    sf.write(OUT/(name+'.wav'),a,SR,subtype='PCM_16')

def pulse_fx(name,dur,start,end,style='round',noise=.0,base=.58,tail=.23,attack=.01):
    n=int(dur*SR);t=np.arange(n)/SR
    freq=start+(end-start)*np.minimum(1,t/max(.01,dur-tail))
    sig=tone(freq,n,style)*envelope(n,attack,tail)
    if noise:sig+=noise*filter_noise(n,1500)*envelope(n,attack,tail)
    save_effect(name,sig,base)

def multichime(name,notes,dur=.6,base=.58):
    n=int(dur*SR);t=np.arange(n)/SR
    x=np.zeros(n,dtype='float32')
    for i,frequency in enumerate(notes):
        delay=int((.065*i)*SR)
        count=n-delay
        if count<=0:continue
        tt=np.arange(count)/SR
        wave=tone(frequency,count,'metal')
        x[delay:]+=wave*np.exp(-tt*(3.5+1.1*i))*envelope(count,.007,.07)*.75
    save_effect(name,x,base,wet=.2)

# Discrete effects with recognizable personalities; not repeated generic beeps.
pulse_fx('ui_click',.095,620,410,'air',base=.30,tail=.075,attack=.001)
pulse_fx('ui_back',.125,510,260,'air',base=.29,tail=.09,attack=.001)
pulse_fx('ui_hover',.082,400,495,'air',base=.18,tail=.07,attack=.001)
multichime('pickup',[830,1244],.32,.48)
multichime('keycard',[690,920,1390],.5,.50)
multichime('module',[260,392,523,784],1.0,.53)
pulse_fx('scan',.80,180,960,'air',noise=.07,base=.51,tail=.28)
pulse_fx('hack',.53,440,1580,'metal',noise=.025,base=.54,tail=.17)
multichime('puzzle_ok',[392,523,659,880],1.12,.52)
pulse_fx('puzzle_error',.58,310,145,'metal',noise=.16,base=.53,tail=.31)
pulse_fx('terminal_open',.42,180,540,'air',noise=.05,base=.47,tail=.18)
pulse_fx('camera_warning',.44,1240,660,'metal',noise=.045,base=.61,tail=.18)
pulse_fx('camera_lock',.95,540,1120,'metal',noise=.13,base=.75,tail=.38)
pulse_fx('drone_alert',.91,230,680,'metal',noise=.14,base=.74,tail=.36)
pulse_fx('drone_search',.33,650,460,'air',noise=.08,base=.46,tail=.16)
pulse_fx('security_alarm',1.05,420,380,'metal',noise=.03,base=.68,tail=.34)
pulse_fx('turret_target',.29,230,710,'metal',noise=.08,base=.49,tail=.13)
pulse_fx('turret_fire',.52,210,55,'metal',noise=.68,base=.85,tail=.39,attack=.001)
pulse_fx('drone_attack',.53,680,190,'metal',noise=.46,base=.81,tail=.37,attack=.003)
pulse_fx('player_hit',.69,210,78,'metal',noise=.43,base=.71,tail=.42,attack=.005)
pulse_fx('shield_on',.85,250,690,'round',noise=.09,base=.53,tail=.41)
pulse_fx('pulse_blast',.81,930,84,'metal',noise=.28,base=.74,tail=.56,attack=.004)
pulse_fx('power_down',.82,510,92,'metal',noise=.12,base=.59,tail=.40)
pulse_fx('power_up',.78,120,690,'air',noise=.09,base=.56,tail=.28)
pulse_fx('battery',.53,200,470,'air',noise=.06,base=.45,tail=.22)
pulse_fx('medkit',.57,390,810,'air',noise=.035,base=.45,tail=.27)
pulse_fx('lure',.63,340,710,'metal',noise=.06,base=.52,tail=.29)
pulse_fx('door',1.75,120,52,'metal',noise=.80,base=.67,tail=.65,attack=.025)
pulse_fx('fail',1.45,260,90,'metal',noise=.14,base=.57,tail=.84)
multichime('victory',[261.63,329.63,392,523.25,659.25],2.8,.61)
# Old names kept as compatibility with any scripts or legacy calls.
for name,canonical in {'click':'ui_click','damage':'player_hit','alarm':'security_alarm','drone':'drone_alert','pulse':'pulse_blast'}.items():
    (OUT/(name+'.wav')).write_bytes((OUT/(canonical+'.wav')).read_bytes())

# Looped soundscape: three level themes, menu, suspense, chase and ventilation.
SECONDS=16.0;N=int(SR*SECONDS);time=np.arange(N)/SR

def midi(n):return 440*2**((n-69)/12)

def add_note(arr,midi_note,begin,length,volume=.1,texture='air'):
    s=int(begin*SR);count=min(int(length*SR),N-s)
    if count<=0:return
    tt=np.arange(count)/SR
    # organic, soft synth/strings, gentle wandering pitch
    freq=midi(midi_note)*(1+.0017*np.sin(2*np.pi*(.65*tt + begin*.12)))
    sig=tone(freq,count,texture)*envelope(count,min(.14,length*.18),min(.6,length*.32))
    sig*=volume*(.75+.25*np.sin(2*np.pi*(.15*tt+begin*.13)))
    arr[s:s+count]+=sig

def make_music(name,chords,seed,variation='level'):
    local=np.random.default_rng(seed)
    left=np.zeros(N,dtype='float32');right=np.zeros(N,dtype='float32')
    # 4 slow-moving harmonies: one chord each 4 seconds; low dark pad carries each scene.
    for step,notes in enumerate(chords):
        start=step*4
        for k,note in enumerate(notes):
            add_note(left,note,start,3.97,.064 if k else .075,'air')
            add_note(right,note,start+.07,3.9,.051 if k else .064,'round')
        add_note(left,notes[0]-12,start+.12,3.6,.050,'round')
        add_note(right,notes[0]-12,start+.18,3.6,.047,'round')
        if variation=='menu':
            events=[(0.6,2),(2.1,1),(3.05,2)]
        else:
            events=[(.7,1),(2.10,2),(3.34,1)]
        for index,(offset,tone_index) in enumerate(events):
            n=notes[tone_index]+(12 if index==2 else 0)
            add_note(left if index%2 else right,n,start+offset,.72,.055 if variation!='menu' else .044,'metal')
    # A little filtered 'air' makes the scene breathe, not a pure synthetic drone.
    field=filter_noise(N,160).astype('float32')
    envelope_noise=.6+.24*np.sin(2*np.pi*(time/16))+.08*np.sin(2*np.pi*(time/4))
    left+=.009*field*envelope_noise;right+=.008*np.roll(field,int(SR*.03))*envelope_noise
    if variation=='level':
        taps=[2.4,6.2,10.8,14.4]
        for i,at in enumerate(taps):
            pos=int(at*SR);count=int(.42*SR)
            tap=filter_noise(count,800,high=False)*np.exp(-np.arange(count)/(SR*.07))*.009
            (left if i%2 else right)[pos:pos+count]+=tap
    return left,right

def make_overlay(kind):
    l=np.zeros(N,dtype='float32');r=np.zeros(N,dtype='float32')
    base=44 if kind=='tension' else 41
    for cycle in range(4):
        for note in ([base,base+7,base+12] if kind=='tension' else [base,base+12,base+5]):
            add_note(l,note,cycle*4,3.95,.037 if kind=='tension' else .040,'round')
            add_note(r,note,cycle*4+.06,3.90,.037,'air')
    # Percussion pace: faint sonar heartbeat on suspicion, active percussive chase.
    beats=range(0,32) if kind=='chase' else range(0,16)
    beat_length=.5 if kind=='chase' else 1.0
    for idx in beats:
        at=idx*beat_length
        p=int(at*SR);count=min(int(.24*SR),N-p)
        if count<=0:continue
        tt=np.arange(count)/SR
        low=(np.sin(2*np.pi*(62*np.exp(-tt*6)+54)*tt)*np.exp(-tt*22))
        tap=filter_noise(count,1400,high=True)*np.exp(-tt*35)
        amp=.031 if kind=='chase' else .014
        l[p:p+count]+=(amp*low+.014*tap).astype('float32')
        r[p:p+count]+=(amp*low+.011*tap).astype('float32')
        if kind=='chase' and idx%2:
            add_note(r,68+((idx//2)%3)*2,at+.20,.22,.035,'metal')
    return l,r

def to_ogg(name,left,right,peak=.84):
    # smooth 0.2s loop crossblend avoids audible clicks at boundary
    x=np.column_stack((left,right)).astype('float32')
    fade=int(SR*.22)
    # fade to silence at boundary, masking seam at very low volume
    ramp=np.sin(np.linspace(0,np.pi/2,fade))**2
    x[:fade]*=ramp[:,None];x[-fade:]*=ramp[::-1,None]
    x=np.tanh(x*2.0)
    maxabs=np.max(np.abs(x)) or 1
    x=x/max(1,maxabs/peak)
    sf.write(OUT/(name+'.ogg'),x,SR,format='OGG',subtype='VORBIS')

SETS={
 'music_menu':([[45,52,57],[43,50,57],[40,47,55],[43,50,59]],11,'menu'),
 'music_level_1':([[45,52,57],[41,48,57],[43,50,59],[40,47,55]],26,'level'),
 'music_level_2':([[41,48,56],[38,45,53],[40,47,55],[43,50,58]],33,'level'),
 'music_level_3':([[40,47,55],[36,43,52],[41,48,56],[38,45,53]],47,'level'),
}
for name,(chord,seed,kind) in SETS.items():
    to_ogg(name,*make_music(name,chord,seed,kind))
for kind in ('tension','chase'):
    to_ogg('music_'+kind,*make_overlay(kind))
# Air/noise only, no repeating sustained pitch or piercing synthesizer hum.
base=filter_noise(N,270)
breath=.72+.18*np.sin(2*np.pi*time/16)**2+.09*np.sin(2*np.pi*time/4)
vent=base*breath*.030
vent+=filter_noise(N,2100,high=True)*.0028
vent=vent.astype('float32')
to_ogg('ambience_ship',vent,np.roll(vent,int(SR*.07))*.93)
# Restore old filename for scripts that reference it, but new game does not loop it.
sf.write(OUT/'ambient.wav',np.column_stack((vent,vent*.92)),SR,subtype='PCM_16')
print('Generated',len(list(OUT.glob('*.wav'))),'WAV and',len(list(OUT.glob('*.ogg'))),'OGG originals in',OUT)
