# ARCHITECT: Desktop UI Audit
## nova_desktop.html — 6,451 lines, 67 panels

### PANEL COUNT: 67 registered in PANELS array
### API ENDPOINTS: ~160 unique across all panels
### WEBSOCKET: NONE — all HTTP polling (3-45s intervals)

### KEY FINDINGS
1. VCC tracks 13 services, UI uses 23+ — topbar "X/13" misleading
2. Version mismatch: UI says v4.0, orchestrator is v5.0.0
3. esc() function double-escapes backslashes (line 2117) — Windows paths broken
4. loadGoBoard orphaned — not in PANELS array, unreachable from UI
5. SkipTrace bypasses orchestrator (hardcoded port 9903)
6. Timer cleanup gaps — hivemind, security, system, dashboard, godmode panels
7. Zero WebSocket connections despite WS service on port 9998

### VOICE SYSTEM: Fully wired
- STT: MediaRecorder → /api/voice/transcribe
- TTS: /api/voice/speak (auto-speak on voice-initiated queries)
- Wake word: "nova" via webkitSpeechRecognition
- Voice picker: 5 tiers (Top/Premium/Standard/Intl/Offline)

### SETTINGS
- 4 themes: dev (green), creative (magenta), gaming (purple), work (grey)
- 5 DSE profiles: IDLE, DEV_MODE, AI_WORKSPACE, GAME_MODE, SAFE_MODE
- 6 AI providers: Claude, Ollama, OpenAI, DeepSeek, OpenRouter, Custom
- Emergency: Safe Mode + Panic Off killswitch

### SERVICES UI DEPENDS ON (but VCC doesn't track)
TSkipTrace(9903), TSysmon(9905), TNet(9906), TSecurity(9907),
TMedia(9908), TBuild(9909), TCron(9910), TQuery(9911),
AppControl(9887), Static(8888)
