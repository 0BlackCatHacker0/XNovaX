# voice.py — Nova Voice Engine: TTS via edge-tts (Microsoft Neural voices)
# Supports async speech synthesis, voice listing, and audio byte generation.
# Orchestrator calls: speak(), speak_to_bytes(), list_voices(), get/set_active_voice()

import asyncio
import io
import threading
import subprocess
import platform
import os
import tempfile

_CONFIG = {
    "engine": "edge-tts",
    "rate": "+0%",
    "volume": "+0%",
    "voice_id": "en-US-AvaNeural",
}

_ACTIVE_VOICE = "en-US-AvaNeural"
_VOICES_CACHE = []
_CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0


def get_config():
    return {**_CONFIG, "active_voice": _ACTIVE_VOICE}


def update_config(**kwargs):
    for k, v in kwargs.items():
        if k in _CONFIG:
            _CONFIG[k] = v
    return True


def voice_status():
    return {
        "status": "active",
        "engine": "edge-tts",
        "active_voice": _ACTIVE_VOICE,
        "voices_cached": len(_VOICES_CACHE),
    }


def list_voices():
    """List available edge-tts voices (cached after first call)."""
    global _VOICES_CACHE
    if _VOICES_CACHE:
        return _VOICES_CACHE
    try:
        import edge_tts
        loop = asyncio.new_event_loop()
        voices = loop.run_until_complete(edge_tts.list_voices())
        loop.close()
        _VOICES_CACHE = [
            {
                "id": v["ShortName"],
                "name": v.get("FriendlyName", v["ShortName"]),
                "gender": v.get("Gender", "Unknown"),
                "locale": v.get("Locale", ""),
            }
            for v in voices
        ]
        return _VOICES_CACHE
    except Exception:
        # Fallback: known good voices
        return [
            {"id": "en-US-AvaNeural", "name": "Ava (Female)", "gender": "Female", "locale": "en-US"},
            {"id": "en-US-AndrewNeural", "name": "Andrew (Male)", "gender": "Male", "locale": "en-US"},
            {"id": "en-US-JennyNeural", "name": "Jenny (Female)", "gender": "Female", "locale": "en-US"},
            {"id": "en-GB-SoniaNeural", "name": "Sonia (Female)", "gender": "Female", "locale": "en-GB"},
        ]


def get_active_voice():
    return _ACTIVE_VOICE


def set_voice(voice_id=None, **kwargs):
    global _ACTIVE_VOICE
    if voice_id:
        _ACTIVE_VOICE = voice_id
    return True


def speak_to_bytes(text="", voice_id=None, rate=None, volume=None, **kwargs):
    """Synthesize speech and return MP3 bytes."""
    if not text:
        return b""
    vid = voice_id or _ACTIVE_VOICE
    r = rate or _CONFIG.get("rate", "+0%")
    v = volume or _CONFIG.get("volume", "+0%")
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, vid, rate=r, volume=v)
        loop = asyncio.new_event_loop()
        audio_data = io.BytesIO()

        async def _generate():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])

        loop.run_until_complete(_generate())
        loop.close()
        return audio_data.getvalue()
    except Exception:
        return b""


def _get_mp3_duration(filepath):
    """Get actual MP3 duration in seconds using ffprobe or file size estimate."""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=5,
            startupinfo=si, creationflags=_CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    # Fallback: estimate from file size (MP3 ~16kbps for edge-tts = 2KB/sec)
    try:
        size = os.path.getsize(filepath)
        return max(1, size / 2000)
    except Exception:
        return 5


# Track when TTS finishes so frontend can know
_SPEAK_FINISH_TIME = 0

def get_speak_finish_time():
    return _SPEAK_FINISH_TIME


def speak(text="", blocking=False, voice_id=None, **kwargs):
    """
    Speak text using edge-tts. Non-blocking by default (fires in background thread).
    Returns immediately with status dict including estimated duration.
    """
    global _SPEAK_FINISH_TIME
    if not text:
        return {"status": "no_text", "spoken": False}

    import time as _time

    # Pre-estimate duration and set immediately so polling works right away
    word_count = len(text[:1000].split())
    est_duration = max(2, min(30, int(word_count / 2.5) + 1))
    # Set estimated finish time NOW so frontend knows we're speaking
    _SPEAK_FINISH_TIME = _time.time() + est_duration + 2

    def _speak_thread():
        global _SPEAK_FINISH_TIME
        try:
            vid = voice_id or _ACTIVE_VOICE
            tmp = os.path.join(tempfile.gettempdir(), "nova_speak.mp3")
            import edge_tts
            communicate = edge_tts.Communicate(text[:1000], vid,
                                                rate=_CONFIG.get("rate", "+0%"),
                                                volume=_CONFIG.get("volume", "+0%"))
            loop = asyncio.new_event_loop()
            loop.run_until_complete(communicate.save(tmp))
            loop.close()

            # Get REAL duration from the generated MP3
            real_dur = _get_mp3_duration(tmp)
            # Add 1s safety buffer
            sleep_dur = int(real_dur) + 2
            _SPEAK_FINISH_TIME = _time.time() + real_dur + 1

            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                ps_cmd = (
                    "Add-Type -AssemblyName presentationCore; "
                    "$mp = New-Object System.Windows.Media.MediaPlayer; "
                    f"$mp.Open([uri]'{tmp}'); "
                    "$mp.Play(); "
                    f"Start-Sleep -Seconds {sleep_dur}; "
                    "$mp.Stop(); $mp.Close()"
                )
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    startupinfo=si,
                    creationflags=_CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass

    if blocking:
        _speak_thread()
    else:
        t = threading.Thread(target=_speak_thread, daemon=True)
        t.start()

    return {"status": "speaking", "spoken": True, "voice": voice_id or _ACTIVE_VOICE, "est_duration": est_duration}
