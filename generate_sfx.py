import json
import math
import random
import struct
import wave
from pathlib import Path

SFX_DIR = Path(__file__).resolve().parent / 'data' / 'sfx'
SFX_DIR.mkdir(parents=True, exist_ok=True)

def write_wav(path, samples, rate=48000):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        raw = bytearray()
        for s in samples:
            val = round(max(-1.0, min(1.0, s)) * 32767)
            raw += struct.pack('<h', val)
        wav.writeframes(raw)

def gen_pop(path):
    # Bubble pop: pitch sweeps rapidly from 900Hz down to 250Hz with exponential decay
    rate = 48000
    duration = 0.12
    samples = []
    num_samples = int(rate * duration)
    for i in range(num_samples):
        t = i / rate
        progress = t / duration
        freq = 900 * math.exp(-15 * progress) + 200
        env = math.exp(-25 * progress) * min(1.0, t / 0.003)
        sample = math.sin(2 * math.pi * freq * t) * env * 0.8
        samples.append(sample)
    write_wav(path, samples, rate)

def gen_click(path):
    # Crisp snappy UI click
    rate = 48000
    duration = 0.04
    samples = []
    num_samples = int(rate * duration)
    for i in range(num_samples):
        t = i / rate
        progress = t / duration
        env = math.exp(-60 * progress) * min(1.0, t / 0.001)
        sample = (math.sin(2 * math.pi * 2400 * t) + 0.4 * (random.random() * 2 - 1)) * env * 0.7
        samples.append(sample)
    write_wav(path, samples, rate)

def gen_whoosh(path):
    rate = 48000
    duration = 0.35
    samples = []
    num_samples = int(rate * duration)
    rng = random.Random(42)
    for i in range(num_samples):
        t = i / rate
        phase = t / duration
        noise = rng.uniform(-1, 1) * (math.sin(math.pi * phase) ** 2) * 0.75
        # Low-pass blend
        sample = noise * math.sin(2 * math.pi * (200 + 400 * phase) * t) * 0.7
        samples.append(sample)
    write_wav(path, samples, rate)

def gen_impact(path):
    rate = 48000
    duration = 0.45
    samples = []
    num_samples = int(rate * duration)
    for i in range(num_samples):
        t = i / rate
        phase = t / duration
        sub = math.sin(2 * math.pi * (85 * t + 30 * t * t))
        decay = math.exp(-8 * phase) * min(1.0, t / 0.005)
        samples.append(sub * decay * 0.85)
    write_wav(path, samples, rate)

def gen_chime(path):
    rate = 48000
    duration = 0.6
    samples = []
    num_samples = int(rate * duration)
    for i in range(num_samples):
        t = i / rate
        phase = t / duration
        h1 = math.sin(2 * math.pi * 880 * t)
        h2 = 0.5 * math.sin(2 * math.pi * 1320 * t)
        h3 = 0.25 * math.sin(2 * math.pi * 1760 * t)
        decay = math.exp(-4.5 * phase) * min(1.0, t / 0.005)
        samples.append((h1 + h2 + h3) * decay * 0.6)
    write_wav(path, samples, rate)

def main():
    gen_pop(SFX_DIR / 'pop.wav')
    gen_click(SFX_DIR / 'click.wav')
    gen_whoosh(SFX_DIR / 'whoosh.wav')
    gen_impact(SFX_DIR / 'impact.wav')
    gen_chime(SFX_DIR / 'chime.wav')

    metadata = {
        'pop': {'file': 'pop.wav', 'duration': 0.12, 'use': 'badge_pop_in', 'description': 'Nhẹ nhàng khi huy hiệu hoặc thẻ phụ xuất hiện'},
        'click': {'file': 'click.wav', 'duration': 0.04, 'use': 'list_item_tick', 'description': 'Tiếng click thanh gọn cho danh sách bước'},
        'whoosh': {'file': 'whoosh.wav', 'duration': 0.35, 'use': 'scene_transition', 'description': 'Gió lướt khi chuyển giữa cảnh nói và đồ họa'},
        'impact': {'file': 'impact.wav', 'duration': 0.45, 'use': 'statistic_warning', 'description': 'Âm trầm nhấn mạnh số liệu lớn hoặc cảnh báo đỏ'},
        'chime': {'file': 'chime.wav', 'duration': 0.60, 'use': 'insight_cta', 'description': 'Chuông sáng tích cực cho điểm nhấn hoặc lời kêu gọi CTA'}
    }
    (SFX_DIR / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Generated SFX library with metadata successfully.')

if __name__ == '__main__':
    main()
