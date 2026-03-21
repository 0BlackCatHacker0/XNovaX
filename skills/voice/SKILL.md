---
name: voice
description: "Voice control - TTS synthesis, STT recognition, wake word"
tools:
  - name: speak
    description: Convert text to speech using configured TTS provider
    parameters:
      - name: text
        type: string
        required: true
      - name: voice
        type: string
        description: "Voice name (default: system default)"
        required: false
metadata:
  novax:
    risk: LOW
    driver: voice
    confidence: 0.7
---

# voice

Text-to-speech and voice control.
OpenClaw supports: ElevenLabs (primary), OpenAI (fallback), Edge TTS (default/free).
Edge TTS uses Microsoft neural voices via node-edge-tts.

## TTS Providers (from OpenClaw)
1. ElevenLabs - requires ELEVENLABS_API_KEY
2. OpenAI - requires OPENAI_API_KEY
3. Edge TTS - free, default when no API keys set
