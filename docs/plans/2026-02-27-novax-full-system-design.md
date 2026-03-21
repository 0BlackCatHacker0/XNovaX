# NovaX Full System Design

**Date:** 2026-02-27
**Approach:** A+C Hybrid (Bottom-Up Foundation + Vertical Slice Proof)
**Status:** Approved

---

## What NovaX Is

NovaX is a personal AI operating layer that sits above all applications and coordinates intelligence + actions. AI uses stable software to do things — NovaX IS the software, AI is the decision maker.

Two versions unified into one:
1. **NovaX Server** — all tools/features/sections working, able to control/modify/create on the system
2. **NovaX OS** — same features but as an operating system shell overlaying Windows

---

## Build Approach: A+C Hybrid

**Phase 1:** Core Engine (orchestrator, drivers, state, memory)
**Phase 2:** Services (Brain, Relay, WebSocket, all services started + VCC verified)
**Phase 3:** Vertical Slice Proof (one complete flow: prompt → plan → execute → skill learned → green VCC)
**Phase 4:** Intelligence Layers (skills, routing, workflows, temporal memory)
**Phase 5:** Hivemind Terminal (all 6 tabs wired to real data)
**Phase 6:** Nova Desktop (full OS shell with all panels)
**Phase 7:** Advanced Layers (profiles, context watcher, DSE, NCP, God Mode)
**Phase 8:** Extended (XRPL, voice, creative tools, modules)
**Phase 9:** OS Installation (Windows overlay mode)

---

## Section 1: Core Engine (Port 9999)

Single always-running Flask + SocketIO orchestrator. All UIs talk to this.

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/think` | POST | Phase 1: Classify → Route → Return plan with Option A/B |
| `/execute` | POST | Phase 2: Run approved actions through drivers |
| `/repair` | POST | Diagnose failed step → propose fix plan |
| `/step` | POST | Run one task graph step |
| `/run` | POST | Run N steps (default 5, max 20) |
| `/task/active` | GET | Current task state |
| `/task/pause` | POST | Pause active task |
| `/task/history` | GET | Completed tasks |
| `/workflow/save` | POST | Save named workflow |
| `/workflow/list` | GET | All saved workflows |
| `/profile/switch` | POST | Switch personality profile |
| `/profile/save` | POST | Save current profile |
| `/profile/export` | GET | Download .novaxprofile |
| `/profile/import` | POST | Upload .novaxprofile |
| `/project/suggest` | POST | Propose project workspace |
| `/project/save` | POST | Save project environment |
| `/api/skills` | GET | All loaded skills |
| `/api/vcc` | GET | Service verification states |
| `/api/status` | GET | Full system status |
| `/api/metrics` | GET | Uptime, tasks, success rate |
| `/control/observed` | GET | Current system state |
| `/control/desired` | GET | Desired state |
| `/control/diff` | GET | State difference |
| `/control/request` | POST | Enqueue state change request |
| `/control/profile/apply` | POST | Apply profile by name |
| `/control/profile/list` | GET | Available profiles |
| `/control/service/restart` | POST | Restart service |
| `/control/model/set` | POST | Set active model |
| `/control/mode/admin` | POST | Toggle admin mode |
| `/control/mode/god` | POST | Toggle god mode |
| `/control/killswitch/safe` | POST | SAFE_MODE |
| `/control/killswitch/panic` | POST | PANIC_OFF |
| `/health` | GET | Server health |
| `/ws` | WebSocket | Real-time events |

### /think Flow
```
Input → task_classifier (8 types) → ai_router (picks model) → skills_engine (Option A from memory) → AI model (Option B fresh plan) → Both returned with risk levels
```

### /execute Flow
```
User clicks Execute → actions dispatched to drivers → success: skill confidence +0.10 → failure: stops, repair proposed → result pushed via WebSocket
```

---

## Section 2: Services & VCC

### Services

| Service | Port | Module | Purpose |
|---------|------|--------|---------|
| Orchestrator | 9999 | core/orchestrator.py | Main API |
| Brain | 9990 | core/brain_server.py | Local AI via Ollama |
| WebSocket | 9998 | Built into orchestrator | Real-time push |
| Relay | 9877 | nova_relay.py | Hivemind command relay |
| Nexus | 9882 | nova_nexus.py | 124-model hub |
| Sentinel | 9883 | nova_sentinel.py | Auto-recovery watchdog |
| Hivemind Server | 9881 | nova_hivemind.py | Distributed dispatch |
| Cloud Router | 9878 | nova_cloud_router.py | Cloud/local hybrid |
| OpenClaw | 18789 | External | Tool routing gateway |
| Ollama | 11434 | External | Local AI models |
| Redis | 6379 | External | Cache/sessions |
| PostgreSQL | 5432 | External | Data persistence |
| NATS | 4222 | External | Message bus |
| Node-RED | 1880 | External | Visual automation |
| Meilisearch | 7700 | External | Fast search |
| MinIO | 9000 | External | Object storage |
| Gitea | 3001 | External | Source control |
| Prometheus | 9090 | External | Metrics |
| Grafana | 3000 | External | Dashboards |
| Caddy | 8080 | External | Reverse proxy |

### VCC Lifecycle
```
DETECTED → READ → SCANNED → WRITE_REQUESTED → MODIFIED → COMPLETE → VERIFIED → TRUSTED
```
- Token: `NOVAX::<component_id>::<nonce>::READ>SCAN>WRITE>MODIFY>COMPLETE`
- No state skippable
- Trust = port open + response valid + modification verified
- Visual: green/red per service
- Health checks every 30s via Sentinel
- Stored: `memory/vcc_registry.json`

---

## Section 3: Two-Phase Intent System

- Phase 1 THINK: classify intent (CHAT/SIMPLE/COMPLEX)
- Phase 2 PLAN+EXECUTE: Option A (learned skill) + Option B (fresh AI plan)
- Risk colors: Low=gray/green, Medium=yellow, High=red
- Four buttons: Execute A / Execute B / Edit / Cancel
- Nothing executes without user click
- Self-healing: fail → stop → diagnose → repair proposal → user approves

---

## Section 4: Action Bus & Permanent Drivers

| Driver | Capabilities |
|--------|-------------|
| system_driver | Open apps, keyboard/mouse, process management |
| file_driver | Read/write/move/copy/delete files |
| terminal_driver | Shell commands, PowerShell, batch scripts |
| code_driver | Generate code, run scripts, debug |
| ai_driver | Talk to any AI model |
| vision_driver | Screen reading, OCR, UI understanding |

AI never creates new drivers. Only sends JSON instructions to these fixed drivers.

---

## Section 5: Multi-AI Routing

### Models
- Cloud: Claude Sonnet/Opus, GPT-4o, Gemini 1.5 Pro
- Local: Llama3 8B/70B, Mixtral 8x7B, Mistral 7B, Phi-3, Nous Hermes
- Code: DeepSeek-Coder, CodeLlama, WizardCoder, StarCoder2
- Fast: Phi-3 mini, TinyLlama, Gemma 2B
- Vision: GPT-4o, Claude Vision, LLaVA 1.6, BakLLaVA
- Creative: Claude, Nous Hermes, MythoMax, Dolphin Mixtral

### 3-Layer Routing
1. Hard rules: system commands → executor, no AI
2. Capability classification: 7 categories → best model
3. Learned optimization: success/failure/speed tracking

### Overrides
- `@claude`, `@code`, `@local`, `@fast`, `@vision`, `@system`
- UI dropdown: Auto / Claude / Local
- Badge: `[model | task | mode]` on every response

---

## Section 6: Skill Memory

- `memory/skills.jsonl`
- Triggers, action sequence, confidence score, risk profile, stats
- Scoring: A no-edit +0.10, A with-edit +0.03, Cancel -0.10, Error -0.15
- Thresholds: 0.60 aggressive suggest, 0.80 pre-select A, 0.90 auto-merge
- Categories: knowledge, development, system, creative

---

## Section 7: Conversation Memory

- Last 12 exchanges in `memory/history.json`
- Fed into every AI prompt
- Enables pronouns: "it", "that", "again"
- Never executes, only improves planning

---

## Section 8: System State Awareness

- `core/state.py` reads (read-only):
  - Running processes, disk space, home folder, CPU/RAM, OS version, tool availability
- Injected into every AI prompt

---

## Section 9: Persistent Task Graph

- `memory/tasks.json`
- States: queued/running/done/error/paused
- AI handoff: planner → coder → terminal → repair
- On open: "Pending Task → Continue or Pause?"
- Speeds: Step (1) / Run 5 / Run 20
- Auto-stop on failure/limit/close

---

## Section 10: Workflow Memory

- Named macros in `memory/workflows.json`
- Explicit: "save this as dev setup"
- Auto-detect: 3+ repeats → "name this?"
- Pattern hashing for structural matching

---

## Section 11: Time-Aware Memory

- "yesterday's setup", "the python project", "that big install"
- Tags: time, description, keywords, size, apps
- `memory/history_index.json`

---

## Section 12: Visual Automation & UI Memory

- Screen reading via LLaVA/Claude Vision
- Records clicks, form fills, button sequences
- "I know this installer. Use it?" after 3+ uses
- `memory/ui_routines.json`
- Privacy-first: structured state, not raw pixels

---

## Section 13: Personality Profiles

| Profile | Behavior |
|---------|----------|
| Dev | Fast, terminal-heavy, DeepSeek preferred |
| Work | Careful, documentation first |
| Creative | Multi-AI brainstorming, Claude/MythoMax |
| Gaming | Minimal interruptions, performance |

- Separate memory per profile: `profiles/work/`, `dev/`, `creative/`, `gaming/`
- Switching = swapping entire memory
- Export/import as `.novaxprofile`

---

## Section 14: Context Detection

- Monitors foreground window every 2 seconds
- Rules: Code.exe→Dev, WINWORD→Work, Blender→Creative, Steam→Gaming
- First time: asks confirmation. After: auto-switches
- Separate background process

---

## Section 15: Environment Bootstrapping

- Profile switch → workspace prep proposal
- Dev: open VS Code + Docker + Ollama + project folder
- `memory/environments.json`
- Always needs approval

---

## Section 16: Project Detection & Learning

- Watches working directories for known projects
- Per-project workspace prep (not generic per mode)
- Session learning: 4+ actions → "Save as project?"
- `memory/projects.json`, `memory/session_capture.json`

---

## Section 17: Adaptive AI Routing

- Tracks: task type + model + success/fail + time
- Score: success rate 70% + speed 30%
- `memory/ai_routing.json`
- Day 1: guesses. Day 7: routes accurately

---

## Section 18: Desired-State Engine (DSE)

- Master Supervisor: Observed → Desired state reconciliation
- Profiles: IDLE, AI_WORKSPACE_ON, GAME_MODE_ON, MODELING_3D_ON, DEV_MODE_ON, SAFE_MODE, PANIC_OFF
- Ownership Lock, Button Proof Contracts
- Killswitch: SAFE_MODE (soft), PANIC_OFF (hard)
- Endpoints on orchestrator under `/control/*`

---

## Section 19: Router, Arbiter & Event Bus

- Router: normalize prompt packets, route to models, create task graphs
- Arbiter: ONLY authority for mutations (execute, restart, write)
- Event Bus: SUGGESTION, BLOCKER, PATCH, DECISION, RISK, STATUS
- Worker Roles: Architect, Builder, Debugger, Tester, Integrator
- Proof: file_exists, file_contains, port_open, http_ok, process_running, ws_connected

---

## Section 20: God Mode Orchestration

- Project sessions: shared memory, filesystem, task map
- Role assignment to models
- All models propose → NovaX executes
- Session-based admin privileges

---

## Section 21: NCP Control Plane CLI

- Commands: bootstrap, set-desired, diff, plan, apply, status, rebuild, orchestrate
- State files: system_state.json, desired_state.json, last_plan.json, apply_log.jsonl
- Guarantees: deterministic, idempotent, resume-safe, disk-truth

---

## Section 22: Reset-Proof Memory

- Disk-first at `/NovaMemory/`
- Dirs: architecture/, manifests/, system/, ai_sessions/, build_logs/, recovery/
- Rehydration at every session start
- Context injected into every prompt

---

## Section 23: NovaCore Module System

- Nova-Dev (languages, compilers, VS Code, Git)
- Nova-AI (PyTorch, TF, HuggingFace, Jupyter)
- Nova-AI-Extended (Bio/Chem/Physics/Finance)
- Nova-Game (Unity, Unreal, Godot)
- Nova-Creative (Blender, GIMP, Krita, Kdenlive, Audacity, LMMS, OBS)
- Nova-VR (Meta Quest SDK, Horizon Worlds)
- Nova-Blockchain (xrpl-py, xrpl.js, wallet)
- Nova-Emulation (RetroArch, Dolphin, PCSX2, etc.)
- Nova-Research (LaTeX, Pandoc, scientific)
- Nova-UX (themes, splash, audio, widgets)

Install/remove independently. Pre-snapshot on install.

---

## Section 24: XRPL & Blockchain

- Native XRPL wallet, XRP/token transfers, NFT minting
- NovaCoin for premium tools/AI compute
- Decentralized identity via XRPL metadata
- IPFS + XRPL hash verification
- dApp launcher, token browser, exchange
- Recovery via profile + XRPL key

---

## Section 25: Voice Layer

- Wake word: "Nova"
- Voice-to-action through Two-Phase Intent
- Espeak for voice cues
- Failsafe: 3-min timeout, emergency lockdown

---

## Section 26: Game Dev & Creative Tools

- Unity, Unreal, Godot, Blender, GIMP, Krita, Inkscape
- Kdenlive, OpenShot, Audacity, LMMS, OBS
- LibreOffice, Pandoc, LaTeX, Trelby, Ghostwriter
- Stable Diffusion, AI art generation
- All emulators (RetroArch, Dolphin, PCSX2, RPCS3, MAME, etc.)
- Meta Quest SDK, Horizon Worlds
- AI world generation: describe → terrain/NPCs/weather → export

---

## Section 27: Hivemind Terminal

6 tabs:
1. Terminal — commands, @claude, !cmd shell, /commands, history
2. Tasks — live queue with status badges
3. Archive — 200 recent completions with model/duration/timestamp
4. Metrics — uptime, tasks, model, success rate, skills, version
5. VCC — service grid with green/red per service
6. Skills — clickable skill grid

Features: action plan modal, matrix rain, color-coded logs, model badge

---

## Section 28: Nova Desktop (OS Shell)

### Core
- Bottom-center glass prompt bar (Spotlight-style, AI-powered)
- Plan drawer: Option A/B with risk colors
- Service status dots in header
- Profile selector, Model override dropdown

### Desktop Tools

| Tool | Purpose |
|------|---------|
| Code Editor | Syntax highlighting, tabs, AI-assisted editing |
| Terminal | Embedded shell, command history |
| File Manager | Browse/create/move/delete — file_driver connected |
| Universal Debugger | Debug processes, breakpoints, variable inspection |
| Package Manager | apt/pip/npm/choco unified |
| Network Monitor | Connections, ports, bandwidth, health |
| Process Manager | Running processes, kill/restart, resources |
| System Monitor | CPU/RAM/Disk/GPU real-time |
| Settings | Config, API keys, profiles |
| dApp Launcher | XRPL apps, tokens, exchange |
| AI Playground | Direct model chat, multi-model comparison |
| Workflow Designer | Visual workflow builder |
| Skill Browser | Browse/test/edit skills |
| Log Viewer | Real-time logs from all services |

### Theme
- Glassmorphism + neon cyber
- Dev=green matrix, Creative=magenta vaporwave, Gaming=purple flare, Work=clean

---

## Section 29: Security

- Sentinel watchdog, immutable logging
- Arbiter controls all mutations
- XRPL identity, encrypted telemetry
- dApp sandboxing, wake phrase + failsafe
- SAFE_MODE / PANIC_OFF killswitch
- Privacy-first: no desktop streaming

---

## Section 30: Branding

- Nova Cyan #00ffff, Ether Purple #ab00ff, Stellar Black #111111
- Nova glyph: circular with nested orbit lines
- Matrix background (Japanese + binary)
- Boot: "Welcome to NovaX. System is initializing."
- Sounds: synth chord boot, pulse echo alert, reversed bell shutdown

---

## Section 31: Portable Memory

- Export as `.novaxprofile`: skills, prefs, workflows, UI routines, history, tasks
- Import on any machine → same assistant
- Excludes: personal files, passwords

---

## Section 32: OS Installation

- Windows overlay — keeps username, password, credentials, drivers
- Custom shell replacement (Nova Desktop replaces Explorer)
- Services as Windows services (auto-start)
- Toggle back to standard Windows shell
- Enterprise installer with bundled dependencies

---

## File Structure

```
C:\NovaX\
  core\
    orchestrator.py, drivers.py, brain_router.py, brain_server.py,
    skills.py, skills_engine.py, memory.py, session_memory.py,
    state.py, tasks.py, roles.py, preferences.py, workflows.py,
    pattern_watch.py, time_index.py, ui_memory.py, profile_manager.py,
    context_watcher.py, environment_manager.py, project_detector.py,
    project_learner.py, ai_router.py, ai_router_memory.py,
    task_classifier.py, claude_connector.py, vcc.py, repair_engine.py,
    capability_registry.py, tool_inventory.py, workspace_manager.py,
    mode_system.py, nova_personality.py, config.py,
    dse.py, arbiter.py, event_bus.py, router.py, ncp.py
  memory\
    skills.jsonl, history.json, tasks.json, model_prefs.json,
    workflows.json, history_index.json, ui_routines.json,
    environments.json, projects.json, patterns.json,
    session_capture.json, ai_routing.json, vcc_registry.json
  profiles\
    work\  dev\  creative\  gaming\
  web\
    hivemind.html, nova_desktop.html
  ui\
    index.html, servers.html, devtools.html
  config\
    anthropic.key, novax.config, services.json
  docs\plans\
    (this file)
```
