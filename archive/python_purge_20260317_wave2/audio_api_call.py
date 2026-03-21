"""
audio_api_call.py - Python bridge for NovaX Audio Engine
Stdlib only: math, struct, wave, json, sys, os
Called by nova_audio_engine.nova via shell()
"""

import sys
import json
import os
import math


def main():
    args = sys.argv[1:]
    if "--file" in args:
        idx = args.index("--file")
        filepath = args[idx + 1]
        with open(filepath, "r") as f:
            payload = json.load(f)
    else:
        payload = json.loads(sys.stdin.read())

    tool = payload.get("tool", "")
    result = {"ok": False, "error": "unknown_tool"}

    if tool == "wave":
        result = handle_wave(payload)
    elif tool == "freq":
        result = handle_freq(payload)
    elif tool == "synth":
        result = handle_synth(payload)
    elif tool == "envelope":
        result = handle_envelope(payload)
    elif tool == "filter":
        result = handle_filter(payload)
    elif tool == "rhythm":
        result = handle_rhythm(payload)
    elif tool == "encode":
        result = handle_encode(payload)

    print(json.dumps(result))


# ------------------------------------------------------------------
# Tool 1: wave - generate waveform samples
# ------------------------------------------------------------------
def handle_wave(p):
    wtype = p.get("type", "sine")
    freq = p.get("freq", 440)
    dur = p.get("duration", 1.0)
    sr = p.get("sample_rate", 8000)
    amp = p.get("amplitude", 0.8)
    n = int(sr * dur)
    samples = []
    _random_state = [42]  # simple LCG seed for noise

    for i in range(min(n, 8000)):
        t = i / sr
        if wtype == "sine":
            s = amp * math.sin(2 * math.pi * freq * t)
        elif wtype == "square":
            s = amp if math.sin(2 * math.pi * freq * t) >= 0 else -amp
        elif wtype == "saw":
            s = amp * (2 * (t * freq % 1) - 1)
        elif wtype == "triangle":
            s = amp * (4 * abs(t * freq % 1 - 0.5) - 1)
        elif wtype == "noise":
            # Simple LCG pseudo-random (no import random needed)
            _random_state[0] = (_random_state[0] * 1103515245 + 12345) & 0x7FFFFFFF
            s = amp * (_random_state[0] / 0x7FFFFFFF * 2 - 1)
        else:
            s = 0
        samples.append(round(s, 4))

    return {
        "ok": True,
        "type": wtype,
        "freq": freq,
        "samples": samples[:200],
        "total_samples": len(samples),
        "sample_rate": sr,
        "duration": dur,
    }


# ------------------------------------------------------------------
# Tool 2: freq - DFT frequency analysis
# ------------------------------------------------------------------
def handle_freq(p):
    samples = p.get("samples", [])
    sr = p.get("sample_rate", 8000)
    n = len(samples)
    if n == 0:
        return {"ok": False, "error": "no_samples"}

    max_bins = min(n // 2, 100)
    spectrum = []
    for k in range(max_bins):
        real = sum(
            samples[i] * math.cos(2 * math.pi * k * i / n) for i in range(n)
        )
        imag = sum(
            samples[i] * math.sin(2 * math.pi * k * i / n) for i in range(n)
        )
        mag = math.sqrt(real ** 2 + imag ** 2) / n
        freq = k * sr / n
        spectrum.append({"freq": round(freq, 2), "magnitude": round(mag, 4)})

    return {"ok": True, "spectrum": spectrum, "bins": len(spectrum), "sample_rate": sr}


# ------------------------------------------------------------------
# Tool 3: synth - additive synthesis
# ------------------------------------------------------------------
def handle_synth(p):
    harmonics = p.get("harmonics", [])
    dur = p.get("duration", 1.0)
    sr = p.get("sample_rate", 8000)
    n = int(sr * dur)
    cap = min(n, 8000)
    samples = [0.0] * cap

    for h in harmonics:
        freq = h.get("freq", 440)
        amp = h.get("amp", 1.0)
        for i in range(cap):
            t = i / sr
            samples[i] += amp * math.sin(2 * math.pi * freq * t)

    # Normalize
    peak = max((abs(s) for s in samples), default=1)
    if peak > 0:
        samples = [round(s / peak, 4) for s in samples]

    return {
        "ok": True,
        "samples": samples[:200],
        "total_samples": len(samples),
        "harmonics_count": len(harmonics),
        "sample_rate": sr,
    }


# ------------------------------------------------------------------
# Tool 4: envelope - ADSR envelope generator
# ------------------------------------------------------------------
def handle_envelope(p):
    a = p.get("attack", 0.1)
    d = p.get("decay", 0.1)
    sus = p.get("sustain", 0.7)
    r = p.get("release", 0.2)
    dur = p.get("duration", 1.0)
    sr = p.get("sample_rate", 8000)
    n = int(sr * dur)
    env = []

    for i in range(min(n, 8000)):
        t = i / sr
        if t < a:
            val = t / a if a > 0 else 1.0
        elif t < a + d:
            val = 1.0 - (1.0 - sus) * ((t - a) / d) if d > 0 else sus
        elif t < dur - r:
            val = sus
        else:
            val = sus * (1.0 - (t - (dur - r)) / r) if r > 0 else 0
        env.append(round(max(0, min(1, val)), 4))

    return {
        "ok": True,
        "envelope": env[:200],
        "total_samples": len(env),
        "adsr": {"attack": a, "decay": d, "sustain": sus, "release": r},
    }


# ------------------------------------------------------------------
# Tool 5: filter - lowpass / highpass / bandpass
# ------------------------------------------------------------------
def handle_filter(p):
    ftype = p.get("type", "lowpass")
    samples = p.get("samples", [])
    cutoff = p.get("cutoff", 1000)
    sr = p.get("sample_rate", 8000)
    bw = p.get("bandwidth", 200)

    if not samples:
        return {"ok": False, "error": "no_samples"}

    window = max(1, int(sr / (2 * cutoff))) if cutoff > 0 else 1
    filtered = []

    for i in range(len(samples)):
        if ftype == "lowpass":
            start = max(0, i - window)
            chunk = samples[start : i + 1]
            val = sum(chunk) / len(chunk)
        elif ftype == "highpass":
            start = max(0, i - window)
            chunk = samples[start : i + 1]
            avg = sum(chunk) / len(chunk)
            val = samples[i] - avg
        elif ftype == "bandpass":
            low_w = max(1, int(sr / (2 * (cutoff + bw / 2))))
            high_w = max(1, int(sr / (2 * max(1, cutoff - bw / 2))))
            start_l = max(0, i - low_w)
            chunk_l = samples[start_l : i + 1]
            low_val = sum(chunk_l) / len(chunk_l)
            start_h = max(0, i - high_w)
            chunk_h = samples[start_h : i + 1]
            high_val = sum(chunk_h) / len(chunk_h)
            val = low_val - high_val + samples[i] * 0.5
        else:
            val = samples[i]
        filtered.append(round(val, 4))

    return {
        "ok": True,
        "type": ftype,
        "samples": filtered[:200],
        "total_samples": len(filtered),
        "cutoff": cutoff,
    }


# ------------------------------------------------------------------
# Tool 6: rhythm - ternary rhythm pattern generator
# ------------------------------------------------------------------
def handle_rhythm(p):
    pattern = p.get("pattern", "x.x.x.x.")
    bpm = p.get("bpm", 120)
    subdivisions = p.get("subdivisions", 8)
    time_sig = p.get("time_sig", [4, 4])

    beat_dur = 60.0 / bpm
    sub_dur = beat_dur / (subdivisions / time_sig[1])

    beats = []
    for i, ch in enumerate(pattern):
        t = i * sub_dur
        if ch == "x" or ch == "X":
            trit = 1
        elif ch == "o" or ch == "O":
            trit = 0
        else:
            trit = -1
        beats.append(
            {
                "index": i,
                "time": round(t, 4),
                "hit": ch != ".",
                "trit": trit,
                "char": ch,
            }
        )

    return {
        "ok": True,
        "pattern": pattern,
        "beats": beats,
        "bpm": bpm,
        "time_sig": time_sig,
        "total_duration": round(len(pattern) * sub_dur, 4),
    }


# ------------------------------------------------------------------
# Tool 7: encode - ternary audio encoding / decoding / stats
# ------------------------------------------------------------------
def handle_encode(p):
    op = p.get("op", "to_trit")
    samples = p.get("samples", [])
    depth = p.get("depth", 3)

    if op == "to_trit":
        max_val = 3 ** depth
        trits = []
        for s in samples[:500]:
            q = int(round(s * (max_val - 1)))
            q = max(-max_val + 1, min(max_val - 1, q))
            trits.append(q)
        return {
            "ok": True,
            "op": "to_trit",
            "trits": trits[:200],
            "total": len(trits),
            "depth": depth,
            "range": [-max_val + 1, max_val - 1],
        }

    elif op == "from_trit":
        trits = p.get("trits", samples)
        max_val = 3 ** depth
        decoded = [
            round(t / (max_val - 1), 4) if max_val > 1 else 0
            for t in trits[:500]
        ]
        return {
            "ok": True,
            "op": "from_trit",
            "samples": decoded[:200],
            "total": len(decoded),
        }

    elif op == "stats":
        if not samples:
            return {"ok": True, "stats": {"count": 0}}
        peak = max(abs(s) for s in samples)
        rms = math.sqrt(sum(s ** 2 for s in samples) / len(samples))
        pos = sum(1 for s in samples if s > 0)
        neg = sum(1 for s in samples if s < 0)
        zero = sum(1 for s in samples if s == 0)
        return {
            "ok": True,
            "stats": {
                "count": len(samples),
                "peak": round(peak, 4),
                "rms": round(rms, 4),
                "positive": pos,
                "negative": neg,
                "zero": zero,
                "trit_balance": {"plus": pos, "zero": zero, "minus": neg},
            },
        }

    return {"ok": False, "error": "unknown_op"}


if __name__ == "__main__":
    main()
