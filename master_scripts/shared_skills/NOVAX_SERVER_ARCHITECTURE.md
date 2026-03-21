# NovaX Server Architecture — After Strengthening
## Port Map (Complete)

### Core Servers (Existing)
| Port  | Server         | Status  | Role                        |
|-------|---------------|---------|------------------------------|
| 9999  | Nova Bridge    | ✅ UP   | Bootstrap + static files     |
| 9990  | Nova Brain     | ✅ UP   | Primary AI processing        |
| 9877  | Nova Relay     | ✅ UP   | File/exec API (9 endpoints)  |
| 11434 | Ollama         | ✅ UP   | 16 LLM models               |
| 9998  | WebSocket      | ❌ DOWN | Real-time comms              |
| 9997  | Nova UI        | ❌ DOWN | Secondary processing         |
| 9876  | Whisper STT    | ❌ DOWN | Speech-to-text               |

### New Servers (Just Installed)
| Port  | Server         | Role                           |
|-------|---------------|--------------------------------|
| 6379  | Redis          | Cache, sessions, pub/sub       |
| 7700  | Meilisearch    | Full-text search across files  |
| 8080  | Caddy          | Unified reverse proxy          |

## Start Order
1. Existing: `python C:\NovaX\novax\main.py` (boots Brain, WS, Bridge)
2. Relay: `node C:\NovaX\nova_relay.js`
3. New: `C:\NovaX\servers\START_SERVERS.bat` (Redis → Meili → Caddy)

## Caddy Unified Routes (port 8080)
- `/static/*`  → Bridge :9999
- `/brain/*`   → Brain :9990
- `/relay/*`   → Relay :9877
- `/ollama/*`  → Ollama :11434
- `/search/*`  → Meilisearch :7700
- `/*`         → Bridge :9999 (default)

## Directory Structure
```
C:\NovaX\servers\
├── redis\              # Redis cache server
│   └── redis-server.exe
├── caddy\              # Reverse proxy
│   ├── caddy.exe
│   └── Caddyfile
├── meilisearch\        # Search engine
│   └── meilisearch.exe
├── START_SERVERS.bat   # Launch all
└── STOP_SERVERS.bat    # Kill all
```
