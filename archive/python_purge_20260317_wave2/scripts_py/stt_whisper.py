"""
NovaX STT Whisper Helper — GPU-accelerated local transcription
Called by nova_stt_service.nova via shell()
Uses faster-whisper (CTranslate2) for high-accuracy local STT

Usage:
  python C:\NovaX\scripts\stt_whisper.py --file <path.wav> [--language en] [--model base]
  python C:\NovaX\scripts\stt_whisper.py --mic [--duration 3]
Output: JSON to stdout
"""

import sys
import json
import time
import os

def transcribe_file(audio_path, model_size="base", language="en"):
    """Transcribe an audio file using faster-whisper."""
    t0 = time.time()
    result = {"ok": False, "text": "", "duration": 0, "engine": "faster-whisper", "trit": -1}

    if not os.path.exists(audio_path):
        result["error"] = f"File not found: {audio_path}"
        return result

    try:
        from faster_whisper import WhisperModel

        # Use GPU if available (auto-detect), fallback to CPU
        # int8 quantization for speed on both GPU and CPU
        device = "cuda"
        compute_type = "int8"
        try:
            import ctranslate2
            if not ctranslate2.get_cuda_device_count():
                device = "cpu"
        except Exception:
            device = "cpu"

        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments, info = model.transcribe(audio_path, language=language, beam_size=5)

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        text = " ".join(text_parts).strip()
        duration = round(time.time() - t0, 3)

        result["duration"] = duration
        result["language"] = info.language
        result["language_probability"] = round(info.language_probability, 3)
        result["model"] = model_size
        result["device"] = device

        if text:
            result["ok"] = True
            result["text"] = text
            # Trit scoring based on language probability
            prob = info.language_probability
            if prob >= 0.7:
                result["trit"] = 1
            elif prob >= 0.4:
                result["trit"] = 0
            else:
                result["trit"] = -1
        else:
            result["trit"] = -1

    except ImportError:
        result["error"] = "faster-whisper not installed"
    except Exception as e:
        result["error"] = str(e)
        result["trit"] = -1

    return result


def transcribe_mic(duration=3, model_size="base", language="en"):
    """Record from microphone and transcribe."""
    t0 = time.time()
    result = {"ok": False, "text": "", "duration": 0, "engine": "faster-whisper-mic", "trit": -1}

    try:
        import sounddevice as sd
        import numpy as np
        import tempfile
        import wave

        # Record audio
        samplerate = 16000
        audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
        sd.wait()

        # Save to temp WAV
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        with wave.open(tmp.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            wf.writeframes(audio.tobytes())

        # Transcribe the temp file
        result = transcribe_file(tmp.name, model_size=model_size, language=language)
        result["engine"] = "faster-whisper-mic"
        result["mic_duration"] = duration

        # Cleanup
        os.unlink(tmp.name)

    except ImportError as e:
        result["error"] = f"Missing dependency: {e}. pip install sounddevice"
    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NovaX Whisper STT")
    parser.add_argument("--file", type=str, help="Audio file path to transcribe")
    parser.add_argument("--mic", action="store_true", help="Record from microphone")
    parser.add_argument("--duration", type=int, default=3, help="Mic recording duration (seconds)")
    parser.add_argument("--language", type=str, default="en", help="Language code")
    parser.add_argument("--model", type=str, default="base", help="Whisper model: tiny/base/small/medium/large")
    args = parser.parse_args()

    if args.mic:
        result = transcribe_mic(duration=args.duration, model_size=args.model, language=args.language)
    elif args.file:
        result = transcribe_file(args.file, model_size=args.model, language=args.language)
    else:
        result = {"ok": False, "error": "Specify --file <path> or --mic", "trit": -1}

    print(json.dumps(result))
