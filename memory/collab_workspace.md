# NovaX 75-Tool Collaborative Design Workspace
# Agents: WRITE YOUR SECTION, READ OTHERS' SECTIONS, BUILD ON THEM

## AUDIT RESULTS (Foundation — all agents start here)

### Current State: 31 services, 20 UP, 4 DOWN, 1 ERROR
| # | Service | Port | Status | Domain |
|---|---------|------|--------|--------|
| 1 | Orchestrator | 9999 | UP v5.0 | CORE |
| 2 | Hivemind | 9881 | UP v2.0 | INTELLIGENCE |
| 3 | Cloud Router | 9878 | UP v1.0 | INTELLIGENCE |
| 4 | Sentinel | 9884 | UP v1.1 | INFRASTRUCTURE |
| 5 | Nexus | 9882 | UP v1.0 | INTELLIGENCE |
| 6 | VPN Core | 9880 | UP v2.0 | INFRASTRUCTURE |
| 7 | Ternary Server | 9885 | UP v1.0 | INTELLIGENCE |
| 8 | TBuffer | 9886 | DOWN | INFRASTRUCTURE |
| 9 | CLI Server | 9887 | UP v1.0 | CREATION |
| 10 | Closed Loop | 9888 | UP v1.0 | INTELLIGENCE |
| 11 | MaxPatch | 9889 | UP v1.0 | INTELLIGENCE |
| 12 | TShell/NovaCore | 9890 | UP v2.0 | INFRASTRUCTURE |
| 13 | Tools | 9891 | UP v2.0 | CREATION |
| 14 | Vault | 9892 | UP v2.0 | INFRASTRUCTURE |
| 15 | DeepStorage | 9893 | UP v2.0 | INFRASTRUCTURE |
| 16 | Ternary Tools | 9894 | UP v2.0 | CREATION |
| 17 | TSpeak | 9895 | UP v2.0 | INTELLIGENCE |
| 18 | Cortex | 9896 | UP v2.0 | INTELLIGENCE |
| 19 | TFetch | 9897 | UP v2.0 | INFRASTRUCTURE |
| 20 | TFetch Proxy | 9898 | ERROR | INFRASTRUCTURE |
| 21 | TKill | 9899 | UP v3.0 | INFRASTRUCTURE |
| 22 | NovaLang | 9900 | DOWN | CREATION |
| 23 | TCache | 9901 | DOWN | INFRASTRUCTURE |
| 24 | TBuffer | 9902 | DOWN | INFRASTRUCTURE |
| 25 | SkipTrace | 9903 | UP v1.0 | INTELLIGENCE |
| 26 | TSysMon | 9905 | UP v1.0 | INFRASTRUCTURE |
| 27 | TNet | 9906 | UP v1.0 | INFRASTRUCTURE |
| 28 | TSecurity | 9907 | UP v1.0 | INFRASTRUCTURE |
| 29 | TMedia | 9908 | UP v1.0 | CREATION |
| 30 | TBuild | 9909 | UP v1.0 | CREATION |
| 31 | TCron | 9910 | UP v1.0 | CREATION |
| 32 | TQuery | 9911 | UP v1.0 | CREATION |
| 33 | TRecover | 9912 | UP v1.0 | INFRASTRUCTURE |
| 34 | STT | 9875 | UP v1.0 | INTELLIGENCE |
| 35 | TLight | N/A | LIB | CORE (imported by all) |

### Harmonic Constants: 3-5-7-13
### Architecture: Every tool returns trit (+1/0/-1), tracks Reynolds, has /health

### GAPS IDENTIFIED:
- No dedicated testing/validation micro-tool
- No profiling/performance micro-tool
- No data pipeline/ETL micro-tool
- No template/scaffolding micro-tool
- No documentation generator
- No inter-service message bus (only HTTP)
- No log aggregator
- No metrics dashboard backend
- No A/B testing framework
- No schema validation tool
- TBuffer and TCache DOWN — caching layer broken
- NovaLang interpreter DOWN
- TFetch Proxy misconfigured

### DESIGN GOAL: 75 microtools, 3 stacks of 25
- Stack 1: INTELLIGENCE (AI, Language, Analysis, Reasoning)
- Stack 2: INFRASTRUCTURE (System, Network, Storage, Security, Recovery)
- Stack 3: CREATION (Build, Media, Automation, Dev Tools, Testing)

---

## STACK 1: INTELLIGENCE (25 Microtools)

### Philosophy
The Intelligence stack is the **mind** of NovaX — where data becomes understanding. AI routing,
reasoning, language processing, knowledge management, and pattern recognition all live here. Every
tool returns ternary trits (+1/0/-1), tracks Reynolds flow, and follows 3-5-7-13 harmonics.
Port range for new services: 9920-9944. Existing services keep their ports.

### 25 INTELLIGENCE MICROTOOLS

#### EXISTING SERVICES (10 tools — already built)

| # | Name | Port | Status | Description | Key Endpoints | Role |
|---|------|------|--------|-------------|---------------|------|
| I1 | **Hivemind** | 9881 | UP v2.0 | 100-model swarm with N-S flow routing across 10 channels | `/hive/query`, `/hive/models`, `/hive/health` | CORE AI |
| I2 | **Cloud Router** | 9878 | UP v1.0 | 10 cloud AI providers (OpenAI, Anthropic, Google, Mistral, etc.) | `/cloud/query`, `/cloud/providers`, `/cloud/health` | CORE AI |
| I3 | **Nexus** | 9882 | UP v1.0 | Central AI bridge: 124 models + archive + scripts portal | `/nexus/models`, `/nexus/archive`, `/nexus/health` | BRIDGE |
| I4 | **Ternary Server** | 9885 | UP v1.0 | Ternary engine + modulation + NovaLang REPL + Reynolds classifier | `/ternary/engine`, `/ternary/modulate`, `/ternary/novalang` | RUNTIME |
| I5 | **TSpeak** | 9895 | UP v2.0 | Inter-model protocol: +1/0/-1 tokens, N-S deliberation, 61x compression | `/tspeak/encode`, `/tspeak/deliberate`, `/tspeak/merge` | PROTOCOL |
| I6 | **Cortex** | 9896 | UP v2.0 | Desktop AI bridge: Claude Desktop + ChatGPT via UI automation | `/cortex/claude`, `/cortex/gpt`, `/cortex/both` | BRIDGE |
| I7 | **Closed Loop** | 9888 | UP v1.0 | Autonomous brain: 6 daemons, self-healing, task trading | `/loop/status`, `/loop/deliberate`, `/loop/health` | AUTONOMY |
| I8 | **MaxPatch** | 9889 | UP v1.0 | Model fingerprinting (10-trit, 10 channels) + N-S introspection | `/super/probe`, `/super/fingerprint`, `/super/health` | ANALYSIS |
| I9 | **SkipTrace** | 9903 | UP v1.0 | Bible Code ELS search + 11 harmonic skip distances | `/skip/search`, `/skip/correlate`, `/skip/health` | PATTERN |
| I10 | **STT** | 9875 | UP v1.0 | Speech-to-text via faster-whisper (base.en, CPU) | `/transcribe`, `/health` | VOICE |

#### NEW SERVICES (15 tools — ports 9920-9934)

| # | Name | Port | Description | Key Endpoints | Fills Gap |
|---|------|------|-------------|---------------|-----------|
| I11 | **TSummarize** | 9920 | Text summarizer — extractive + abstractive via Hivemind, ternary quality scoring | `POST /tsum/extract` (key sentences), `POST /tsum/abstract` (AI rewrite), `POST /tsum/compare` (diff two summaries) | TDoc needs this |
| I12 | **TClassify** | 9921 | Intent/topic classifier — ternary categories, confidence trits, multi-label | `POST /tclass/intent` (classify user intent), `POST /tclass/topic` (categorize text), `POST /tclass/sentiment` (positive/neutral/negative as +1/0/-1) | Sentiment gap |
| I13 | **TReason** | 9922 | Reasoning engine — chain-of-thought, ternary logic trees, proof verification | `POST /treason/solve` (multi-step reasoning), `POST /treason/verify` (check proof chain), `POST /treason/debate` (adversarial reasoning between 2 models) | Reasoning gap |
| I14 | **TMemory** | 9923 | Knowledge memory manager — episodic + semantic store, ternary relevance scoring | `POST /tmem/store` (save knowledge with context), `POST /tmem/recall` (retrieve by similarity), `POST /tmem/forget` (decay irrelevant entries) | Memory gap |
| I15 | **TEmbed** | 9924 | Embedding service — vector encode text/code, cosine similarity, nearest-neighbor search | `POST /tembed/encode` (text → 384-dim vector), `POST /tembed/similar` (find N most similar), `POST /tembed/cluster` (group by similarity) | Embedding gap |
| I16 | **TAnomaly** | 9925 | Anomaly detector — statistical + ML-based outlier detection on time-series and service metrics | `POST /tanom/detect` (scan data for anomalies), `POST /tanom/baseline` (learn normal patterns), `POST /tanom/alert` (trigger on threshold breach) | TProfile needs this |
| I17 | **TPrompt** | 9926 | Prompt optimizer — template management, variable injection, A/B testing prompt variants | `POST /tprompt/optimize` (refine prompt for model), `POST /tprompt/template` (store/retrieve prompt templates), `POST /tprompt/ab` (test 2 prompts, return winner trit) | A/B testing gap |
| I18 | **TEval** | 9927 | Model evaluator — benchmark models on tasks, compare quality/speed/cost trits | `POST /teval/run` (evaluate model on task set), `POST /teval/compare` (side-by-side model comparison), `POST /teval/leaderboard` (ranked model scores) | Model eval gap |
| I19 | **TKnow** | 9928 | Knowledge graph — entity/relation store, graph queries, ternary edge weights | `POST /tknow/add` (add entity/relation), `POST /tknow/query` (graph traversal), `POST /tknow/path` (shortest path between entities) | Knowledge gap |
| I20 | **TTranslate** | 9929 | Language translator — multi-language via Cloud Router, ternary confidence per token | `POST /ttrans/translate` (text + source + target lang), `POST /ttrans/detect` (detect language), `POST /ttrans/batch` (translate array of strings) | Language gap |
| I21 | **TAgent** | 9930 | Agent orchestrator — spawn/manage autonomous sub-agents with ternary task status | `POST /tagent/spawn` (create agent with goal), `POST /tagent/status` (check all agents), `POST /tagent/merge` (combine agent outputs with tmerge) | Agent gap |
| I22 | **TContext** | 9931 | Context window manager — compress/expand/rotate context for long conversations | `POST /tctx/compress` (ternary context compression), `POST /tctx/expand` (restore from compressed), `POST /tctx/window` (sliding window with priority) | Context gap |
| I23 | **TFilter** | 9932 | Content filter — safety/toxicity/PII detection with ternary severity (+1 clean, 0 warning, -1 block) | `POST /tfilter/scan` (check text for issues), `POST /tfilter/redact` (mask PII), `POST /tfilter/rules` (manage filter rules) | Safety gap |
| I24 | **TVision** | 9933 | Image understanding — describe images, extract text (OCR), classify visual content | `POST /tvision/describe` (image → text), `POST /tvision/ocr` (extract text from image), `POST /tvision/classify` (categorize image content) | Multimodal gap |
| I25 | **TLearn** | 9934 | Online learning — fine-tune embeddings, adapt models from feedback, ternary reward signals | `POST /tlearn/feedback` (+1 good / 0 neutral / -1 bad reward), `POST /tlearn/adapt` (update model weights), `POST /tlearn/export` (save learned parameters) | Learning gap |

### PORT MAP SUMMARY

```
EXISTING:  9875 (STT) | 9878 (Cloud) | 9881 (Hive) | 9882 (Nexus) | 9885 (Ternary)
           9888 (Loop) | 9889 (MaxPatch) | 9895 (TSpeak) | 9896 (Cortex) | 9903 (Skip)

NEW:       9920 (TSummarize) | 9921 (TClassify) | 9922 (TReason)  | 9923 (TMemory)
           9924 (TEmbed)     | 9925 (TAnomaly)  | 9926 (TPrompt)  | 9927 (TEval)
           9928 (TKnow)      | 9929 (TTranslate) | 9930 (TAgent)  | 9931 (TContext)
           9932 (TFilter)    | 9933 (TVision)   | 9934 (TLearn)
```

### DEPENDENCY GRAPH (Intelligence-internal)

```
Hivemind (9881) ─── routes to ──> Cloud Router (9878) ── providers
       │                                    │
       ├── TPrompt (9926) optimizes ────────┘
       ├── TEval (9927) benchmarks models
       ├── TAgent (9930) spawns sub-agents
       └── TContext (9931) manages windows

TEmbed (9924) ─── encodes for ──> TMemory (9923) ── stores
       │                                 │
       └── TKnow (9928) ── graph ────────┘

TSummarize (9920) ─── feeds ──> TClassify (9921) ── categorizes
TReason (9922) ─── verifies ──> TFilter (9932) ── safety checks

STT (9875) ── transcribes ──> TClassify (9921) ── intent
TVision (9933) ── describes ──> TSummarize (9920) ── condenses
TLearn (9934) ── adapts ──> TEmbed (9924) ── re-encodes

TAnomaly (9925) ─── detects ──> from TProfile (9977, Creation stack)
TSummarize (9920) ─── provides ──> to TDoc (9972, Creation stack)
TClassify (9921) ─── sentiment ──> to TReport (9985, Creation stack)
```

### CROSS-REFERENCES TO OTHER STACKS

#### Intelligence <-> Creation (Stack 3)
- **TSummarize (9920)** is consumed by TDoc (9972) for auto-generating readable documentation
- **TClassify (9921)** sentiment analysis feeds into TReport (9985) for quality metrics
- **TAnomaly (9925)** receives performance data from TProfile (9977) for auto-alerting
- **TPrompt (9926)** optimizes prompts used by TGen (9974) for AI code generation
- **TEval (9927)** benchmarks models that TGen uses for code quality selection
- **TFilter (9932)** scans TGen output for safety before code is committed

#### Intelligence <-> Infrastructure (Stack 2)
- **TMemory (9923)** stores knowledge in DeepStorage (9893) for quantized persistence
- **TEmbed (9924)** vectors cached in TBuffer/TCache when they come back online
- **TAnomaly (9925)** monitors TSysMon (9905) metrics for system anomalies
- **TAgent (9930)** uses Sentinel (9884) for agent health monitoring
- **TFilter (9932)** integrates with TSecurity (9907) for threat detection
- **TContext (9931)** uses DeepStorage (9893) for compressed context archives

---

## STACK 2: INFRASTRUCTURE (25 Microtools)

### Philosophy
The Infrastructure stack is the **skeleton** of NovaX — everything that keeps services alive,
connected, secure, and recoverable. System monitoring, networking, storage, security, messaging,
metrics, and service lifecycle management. Port range for new services: 9945-9969.

### 25 INFRASTRUCTURE MICROTOOLS

#### EXISTING SERVICES (11 tools — already built)

| # | Name | Port | Status | Description | Key Endpoints | Role |
|---|------|------|--------|-------------|---------------|------|
| F1 | **Sentinel** | 9884 | UP v1.1 | Auto-recovery watchdog: monitors all services, auto-restarts on failure | `/sentinel/health`, `/sentinel/status`, `/sentinel/restart` | WATCHDOG |
| F2 | **VPN Core** | 9880 | UP v2.0 | 5-layer encryption + Tor + WiFi bonding (needs crypto audit) | `/vpn/encrypt`, `/vpn/tor`, `/vpn/health` | SECURITY |
| F3 | **TShell/NovaCore** | 9890 | UP v2.0 | OS integration + filesystem index + N-S Reynolds prompt routing | `/tshell/scan`, `/tshell/index`, `/tshell/health` | OS |
| F4 | **Vault** | 9892 | UP v2.0 | AES-256-GCM encryption + TZip compression per file | `/vault/lock`, `/vault/unlock`, `/vault/shred` | CRYPTO |
| F5 | **DeepStorage** | 9893 | UP v2.0 | Quantized drive: TZip + dedup + N-S tiering → Desktop folder | `/deep/quantize`, `/deep/restore`, `/deep/scan` | STORAGE |
| F6 | **TFetch** | 9897 | UP v2.0 | 7-segment parallel downloads + proxy cache + auto-quantize | `/tfetch/download`, `/tfetch/git`, `/tfetch/proxy` | NETWORK |
| F7 | **TKill** | 9899 | UP v3.0 | Process management + Universal Debugger (LIUD) | `/tkill/flush`, `/liud/step`, `/liud/watch` | PROCESS |
| F8 | **TSysMon** | 9905 | UP v1.0 | System monitor: CPU/RAM/disk/processes with ternary health trits | `/sysmon/procs`, `/sysmon/resources`, `/sysmon/health` | MONITOR |
| F9 | **TNet** | 9906 | UP v1.0 | Network toolkit: probe/scan/trace/DNS with ternary latency scoring | `/tnet/probe`, `/tnet/scan`, `/tnet/health` | NETWORK |
| F10 | **TSecurity** | 9907 | UP v1.0 | 7-tool security scanner: file threats, ACLs, entropy, ports, audit | `/tsec/scan-file`, `/tsec/audit`, `/tsec/health` | SECURITY |
| F11 | **TRecover** | 9912 | UP v1.0 | Session crash recovery: JSONL parse, context extraction, recovery manifest | `/trecover/recover`, `/trecover/health` | RECOVERY |

#### MERGED/FIXED SERVICES (3 tools — existing but need repair)

| # | Name | Port | Status | Fix | New Role |
|---|------|------|--------|-----|----------|
| F12 | **TBuffer** | 9886 | DOWN → FIX | Merge 9886+9902 into single TBuffer, fix startup crash | CACHE layer 1 (exact match SHA-256) |
| F13 | **TCache** | 9901 | DOWN → FIX | Merge into TBuffer as semantic cache layer | CACHE layer 2 (13-dim semantic) |
| F14 | **TFetch Proxy** | 9898 | ERROR → FIX | Fix HTTPS CONNECT handler, bind 127.0.0.1 | PROXY (part of TFetch) |

#### NEW SERVICES (11 tools — ports 9945-9955)

| # | Name | Port | Description | Key Endpoints | Fills Gap |
|---|------|------|-------------|---------------|-----------|
| F15 | **TBus** | 9945 | Message bus — pub/sub event system, topic channels, ternary priority routing | `POST /tbus/publish` (emit event to topic), `POST /tbus/subscribe` (register listener), `GET /tbus/stream` (SSE event stream) | "no message bus" gap |
| F16 | **TLog** | 9946 | Log aggregator — structured logging from all 75 services, ternary severity, searchable | `POST /tlog/ingest` (receive log entry), `POST /tlog/search` (query logs by service/level/time), `GET /tlog/tail` (live log stream) | "no log aggregator" gap |
| F17 | **TMetrics** | 9947 | Metrics backend — collect counters/gauges/histograms, ternary health dashboards | `POST /tmetrics/record` (push metric), `POST /tmetrics/query` (time-series query), `GET /tmetrics/dashboard` (aggregated health view) | "no metrics dashboard" gap |
| F18 | **TCircuit** | 9948 | Circuit breaker — track service failures, open/half-open/closed states as +1/0/-1 | `POST /tcircuit/check` (should I call this service?), `POST /tcircuit/report` (report success/failure), `GET /tcircuit/states` (all circuit states) | Error recovery gap |
| F19 | **TRate** | 9949 | Rate limiter — per-service/per-endpoint token bucket, ternary allow/throttle/deny | `POST /trate/check` (check if allowed), `POST /trate/config` (set limits), `GET /trate/stats` (current utilization) | No rate limiting |
| F20 | **TFirewall** | 9950 | Software firewall — IP allowlist/blocklist, port rules, SSRF protection (uses tlight) | `POST /twall/check` (is this request allowed?), `POST /twall/rule` (add/remove rule), `GET /twall/log` (blocked request log) | Firewall gap |
| F21 | **TConfig** | 9951 | Config manager — centralized config for all services, hot-reload, ternary validation | `POST /tconfig/get` (read config key), `POST /tconfig/set` (write config key), `POST /tconfig/reload` (hot-reload service config) | No config manager |
| F22 | **TRegistry** | 9952 | Service registry — auto-discovery, health aggregation, dependency graph | `POST /treg/register` (register service), `POST /treg/discover` (find services by capability), `GET /treg/graph` (full dependency graph) | No service registry |
| F23 | **TBackup** | 9953 | Backup scheduler — automated backups to DeepStorage, rotation, ternary integrity verify | `POST /tbackup/now` (backup service state), `POST /tbackup/schedule` (set auto-backup interval), `POST /tbackup/verify` (integrity check on backup) | No backup scheduler |
| F24 | **TShutdown** | 9954 | Graceful shutdown coordinator — ordered stop, drain connections, save state | `POST /tshut/drain` (stop accepting, finish in-flight), `POST /tshut/stop` (graceful ordered shutdown), `POST /tshut/status` (shutdown progress) | CRITICAL: orchestrator has ZERO shutdown handling |
| F25 | **TDNS** | 9955 | DNS resolver + cache — local DNS with ternary trust scoring, poisoning detection | `POST /tdns/resolve` (resolve hostname), `POST /tdns/cache` (manage DNS cache), `POST /tdns/trust` (check domain trust score) | DNS gap |

### PORT MAP SUMMARY

```
EXISTING:  9880 (VPN) | 9884 (Sentinel) | 9886 (TBuffer-FIX) | 9890 (TShell)
           9892 (Vault) | 9893 (DeepStorage) | 9897 (TFetch) | 9898 (Proxy-FIX)
           9899 (TKill) | 9901 (TCache-MERGE) | 9905 (TSysMon) | 9906 (TNet)
           9907 (TSecurity) | 9912 (TRecover)

NEW:       9945 (TBus)      | 9946 (TLog)       | 9947 (TMetrics)  | 9948 (TCircuit)
           9949 (TRate)     | 9950 (TFirewall)  | 9951 (TConfig)   | 9952 (TRegistry)
           9953 (TBackup)   | 9954 (TShutdown)  | 9955 (TDNS)
```

### DEPENDENCY GRAPH (Infrastructure-internal)

```
Sentinel (9884) ─── monitors ──> TRegistry (9952) ── discovers services
       │                                │
       ├── TCircuit (9948) ── breaker ──┘
       ├── TShutdown (9954) ── ordered stop
       └── TBackup (9953) ── auto-backup

TBus (9945) ─── events ──> TLog (9946) ── aggregates ──> TMetrics (9947)
                                                              │
TRate (9949) ── throttles ──> TFirewall (9950) ── blocks     │
                                    │                         │
                              TSecurity (9907) ── scans ──────┘

DeepStorage (9893) ─── stores ──> TBackup (9953) ── schedules
Vault (9892) ─── encrypts ──> TBackup archives
TFetch (9897) ─── downloads ──> TBuffer (9886-FIXED) ── caches
TDNS (9955) ─── resolves for ──> TNet (9906) + TFetch (9897)

TConfig (9951) ─── configures ──> ALL 75 services (centralized)
TRecover (9912) ─── restores ──> from TBackup (9953) + TSnap (9982, Creation)
```

### CROSS-REFERENCES TO OTHER STACKS

#### Infrastructure <-> Intelligence (Stack 1)
- **TBus (9945)** carries TSpeak (9895) inter-model messages as pub/sub events
- **TLog (9946)** aggregates logs from all 25 Intelligence services
- **TMetrics (9947)** tracks AI query latency, model utilization, swarm efficiency
- **TCircuit (9948)** protects against cascading failures when AI providers go down
- **TFirewall (9950)** uses TFilter (9932) for content-based request blocking
- **TConfig (9951)** manages AI model configs, API keys, routing preferences
- **TBuffer (9886-FIXED)** caches TEmbed (9924) vectors and TMemory (9923) recalls

#### Infrastructure <-> Creation (Stack 3)
- **TBus (9945)** carries TWatch (9981) file change events system-wide
- **TLog (9946)** receives structured logs from all 25 Creation tools
- **TMetrics (9947)** feeds TProfile (9977) with system-level performance data
- **TBackup (9953)** stores TSnap (9982) snapshots in DeepStorage
- **TShutdown (9954)** coordinates with TRelease (9986) for rolling deploys
- **TRegistry (9952)** enables TPackage (9978) service discovery
- **TConfig (9951)** stores TBuild (9909) build configs and TCron (9910) schedules

---

## STACK 3: CREATION (Agent 3 — Creation Stack Architect)
<!-- AGENT 3: Design 25 creation microtools. Read gaps + Agent 1+2 output. Fill remaining gaps. -->

### Philosophy
The Creation stack is the **forge** of NovaX — where code is generated, built, tested, validated,
documented, and deployed. Every tool follows the 3-5-7-13 harmonic pattern: each service exposes
7 sub-tools (H7), returns ternary trits (+1/0/-1), tracks Reynolds flow rate, and communicates
via the standard `http.server` pattern with `/health` endpoints. Port range for new services:
9970-9994. Existing services keep their assigned ports.

### 25 CREATION MICROTOOLS

#### EXISTING SERVICES (8 tools — already built, keep their ports)

| # | Name | Port | Status | Description | Key Endpoints | Extends |
|---|------|------|--------|-------------|---------------|---------|
| C1 | **Tools** | 9891 | UP v2.0 | Core file I/O toolkit: read/write/grep/glob/run/edit/pipe + TMulti composition modes | `POST /tools/read`, `POST /tools/write`, `POST /multi` | FOUNDATION |
| C2 | **Ternary Tools** | 9894 | UP v2.0 | TDiff/TCache/TSync/TIndex/TMesh/TStream/TForge — ternary data pipeline toolkit | `POST /ttools/diff`, `POST /ttools/forge`, `POST /ttools/sync` | FOUNDATION |
| C3 | **CLI Server** | 9887 | UP v1.0 | Interactive NovaLang REPL terminal with syntax highlighting and tab completion | `POST /cli/exec`, `POST /cli/complete`, `GET /cli/history` | FOUNDATION |
| C4 | **NovaLang** | 9900 | DOWN | Ternary language interpreter/compiler — .nova files, 23 builtins, if3/match3/try3/while3 | `POST /novalang/run`, `POST /novalang/compile`, `POST /novalang/parse` | FOUNDATION |
| C5 | **TMedia** | 9908 | UP v1.0 | Media processor: file info, format convert, thumbnails, audio analysis, doc-gen, manifests | `POST /tmedia/info`, `POST /tmedia/convert`, `POST /tmedia/doc-gen` | FOUNDATION |
| C6 | **TBuild** | 9909 | UP v1.0 | Build system: dependency analysis, topo-sort build order, diff, lint, VCS, compile checks | `POST /tbuild/deps`, `POST /tbuild/lint`, `POST /tbuild/compile` | FOUNDATION |
| C7 | **TCron** | 9910 | UP v1.0 | Automation engine: scheduling, directory watchers, task CRUD, chained command execution | `POST /tcron/schedule`, `POST /tcron/watch`, `POST /tcron/chain` | FOUNDATION |
| C8 | **TQuery** | 9911 | UP v1.0 | Query & analytics: SQLite, KV store, aggregation, statistics, CSV, JSON query, pivot tables | `POST /tquery/sql`, `POST /tquery/kv`, `POST /tquery/analyze` | FOUNDATION |

#### NEW SERVICES (17 tools — ports 9970-9994)

| # | Name | Port | Description | Key Endpoints | Extends |
|---|------|------|-------------|---------------|---------|
| C9 | **TTest** | 9970 | Test runner and assertion engine — discovers tests, runs suites, reports pass/fail/skip as +1/0/-1 trits | `POST /ttest/run` (run test file/dir), `POST /ttest/assert` (ternary assertions: eq/neq/gt/lt/contains/type), `GET /ttest/results` (last run report with trit summary) | NEW — fills "no testing tool" gap |
| C10 | **TScaffold** | 9971 | Template engine and project scaffolder — generates microservice boilerplate, .nova files, endpoints from specs | `POST /tscaffold/service` (generate full 3-5-7-13 microservice from name+port+tools), `POST /tscaffold/endpoint` (generate handler code from method+path+schema), `POST /tscaffold/nova` (generate .nova source from template name) | NEW — fills "no template/scaffolding" gap |
| C11 | **TDoc** | 9972 | Documentation generator — parses docstrings/comments, builds API docs, generates endpoint inventories | `POST /tdoc/generate` (scan .py file, extract docstrings, emit markdown), `POST /tdoc/api` (generate OpenAPI-style endpoint catalog from running service), `POST /tdoc/inventory` (full NovaX service documentation index) | NEW — fills "no documentation generator" gap |
| C12 | **TSchema** | 9973 | Schema validator — validates JSON/YAML against schemas, validates endpoint request/response shapes | `POST /tschema/validate` (validate data against JSON schema, trit: +1 valid, 0 partial, -1 invalid), `POST /tschema/infer` (infer schema from sample data), `POST /tschema/diff` (compare two schemas, report drift) | NEW — fills "no schema validation" gap |
| C13 | **TGen** | 9974 | AI-assisted code generator — uses Hivemind/Cloud Router to generate code from natural language specs | `POST /tgen/code` (generate code from prompt + language + context), `POST /tgen/refactor` (AI-powered refactor with before/after diff), `POST /tgen/explain` (generate explanation of code block) | NEW — leverages INTELLIGENCE stack |
| C14 | **TPipe** | 9975 | Data pipeline / ETL engine — extract, transform, load with ternary flow control between sources | `POST /tpipe/extract` (read from file/URL/service endpoint), `POST /tpipe/transform` (apply map/filter/reduce/sort/dedupe chain), `POST /tpipe/load` (write to file/KV/SQL destination) | NEW — fills "no ETL pipeline" gap |
| C15 | **TMigrate** | 9976 | Migration tool — schema migrations for TQuery SQLite, config version upgrades, data format migrations | `POST /tmigrate/create` (create numbered migration script), `POST /tmigrate/run` (execute pending migrations up/down), `POST /tmigrate/status` (show applied vs pending migrations) | NEW — extends TQuery (9911) |
| C16 | **TProfile** | 9977 | Performance profiler — measures endpoint latency, memory usage, CPU time; generates flame-graph data | `POST /tprofile/bench` (benchmark an endpoint N times, report p50/p95/p99), `POST /tprofile/trace` (trace a request through service chain with timing), `POST /tprofile/snapshot` (memory + thread snapshot of a running service) | NEW — fills "no profiling tool" gap |
| C17 | **TPackage** | 9978 | Package manager for NovaX services — register, version, install, update, dependency resolve | `POST /tpackage/register` (register service with version + deps), `POST /tpackage/resolve` (resolve dependency tree, detect conflicts), `POST /tpackage/install` (install/update a service from registry) | NEW — fills package management gap |
| C18 | **TDiffView** | 9979 | Visual diff viewer backend — side-by-side file comparison, directory diff, merge conflict resolution | `POST /tdiffview/files` (diff two files with unified/side-by-side output), `POST /tdiffview/dirs` (diff two directory trees), `POST /tdiffview/merge` (3-way merge with ternary conflict markers: +1 ours, 0 both, -1 theirs) | NEW — extends TBuild diff |
| C19 | **TLint** | 9980 | Advanced code quality — style checking, complexity scoring, dead code detection, naming conventions | `POST /tlint/check` (lint file with configurable rules, return trit per rule), `POST /tlint/complexity` (cyclomatic + Reynolds complexity scores), `POST /tlint/dead` (detect unreachable/unused code paths) | NEW — extends TBuild lint |
| C20 | **TWatch** | 9981 | Live reload and hot-swap engine — watches source files, auto-restarts services on change, WebSocket notify | `POST /twatch/start` (watch a service's source files for changes), `POST /twatch/stop` (stop watching), `GET /twatch/events` (SSE stream of file change events + restart status) | NEW — extends TCron watch |
| C21 | **TSnap** | 9982 | Snapshot and rollback — captures full service state (config + data + code hash), restores on demand | `POST /tsnap/capture` (snapshot a service's state to timestamped archive), `POST /tsnap/restore` (rollback service to a prior snapshot), `POST /tsnap/list` (list available snapshots with trit health status) | NEW — bridges to INFRASTRUCTURE (DeepStorage 9893) |
| C22 | **TContract** | 9983 | API contract testing — record expected request/response pairs, replay and verify against live services | `POST /tcontract/record` (capture req/res pair as contract), `POST /tcontract/verify` (replay contracts against live endpoint, report +1 pass / 0 drift / -1 break), `POST /tcontract/list` (list all contracts per service) | NEW — extends TTest |
| C23 | **TMock** | 9984 | Mock server and fixture engine — spin up fake endpoints for testing, generate fixture data from schemas | `POST /tmock/create` (define mock endpoint with path + response + status), `POST /tmock/fixture` (generate N records from TSchema definition), `POST /tmock/replay` (replay recorded HTTP exchanges from TContract) | NEW — extends TTest + TSchema |
| C24 | **TReport** | 9985 | Report generator — aggregates test results, build status, lint scores into formatted reports (HTML/JSON/MD) | `POST /treport/generate` (compile report from sources: ttest + tlint + tbuild + tprofile), `POST /treport/publish` (write report to memory/ directory with timestamp), `GET /treport/latest` (fetch most recent report) | NEW — aggregates from multiple Creation tools |
| C25 | **TRelease** | 9986 | Release manager — version bumping, changelog generation, build artifact packaging, deploy coordination | `POST /trelease/bump` (bump version in service file: major/minor/patch following 3-5-7-13 versioning), `POST /trelease/changelog` (generate changelog from TBuild VCS commits), `POST /trelease/package` (bundle service + deps into deployable archive) | NEW — extends TBuild + TPackage |

### PORT MAP SUMMARY

```
EXISTING:  9887 (CLI) | 9891 (Tools) | 9894 (TernaryTools) | 9900 (NovaLang)
           9908 (TMedia) | 9909 (TBuild) | 9910 (TCron) | 9911 (TQuery)

NEW:       9970 (TTest)     | 9971 (TScaffold) | 9972 (TDoc)      | 9973 (TSchema)
           9974 (TGen)      | 9975 (TPipe)      | 9976 (TMigrate)  | 9977 (TProfile)
           9978 (TPackage)  | 9979 (TDiffView)  | 9980 (TLint)     | 9981 (TWatch)
           9982 (TSnap)     | 9983 (TContract)  | 9984 (TMock)     | 9985 (TReport)
           9986 (TRelease)
```

### DEPENDENCY GRAPH (Creation-internal)

```
TTest (9970) ─────────────────┐
TContract (9983) ─── verifies ─┤
TMock (9984) ──── fixtures ────┤──> TReport (9985) ──> TRelease (9986)
TLint (9980) ──── quality ─────┤
TProfile (9977) ── perf data ──┘

TScaffold (9971) ── generates code ──> TBuild (9909) ── builds ──> TPackage (9978)
TGen (9974) ──── AI code gen ─────────┘

TSchema (9973) ── validates ──> TMock (9984) ── generates fixtures
                               TMigrate (9976) ── migrates ──> TQuery (9911)

TWatch (9981) ── monitors ──> TCron (9910) ── schedules
TSnap (9982) ── snapshots ──> TDiffView (9979) ── compares

TDoc (9972) ── documents ──> all services via /health introspection
TPipe (9975) ── ETL ──> TQuery (9911) for storage
```

### TERNARY FLOW PATTERN (applied to all 25 tools)

Every Creation tool follows this ternary contract:
- **+1 (TRUE)**: Operation succeeded with meaningful output (test passed, build succeeded, doc generated)
- **0 (MAYBE)**: Operation completed but result is partial/ambiguous (some tests skipped, lint warnings, partial match)
- **-1 (FALSE)**: Operation failed (test failed, build error, validation rejected, generation error)

Reynolds classification for Creation tools:
- **Laminar (Re < 27)**: Simple operations — single file lint, one test case, read one doc
- **Transitional (27 <= Re < 125)**: Moderate — full test suite, multi-file build, directory scaffold
- **Turbulent (125 <= Re < 343)**: Heavy — cross-service contract testing, full report generation, release packaging
- **Chaotic (Re >= 343)**: Swarm — parallel test + lint + build + profile across entire codebase

### CROSS-REFERENCES TO OTHER STACKS

#### Creation <-> Intelligence (Stack 1)
- **TGen (9974)** is the primary bridge: it calls Hivemind (9881) and Cloud Router (9878) to generate code from natural language. When Agent 1 designs AI routing tools, TGen should be listed as a consumer of those routes.
- **TDoc (9972)** can leverage Intelligence NLP tools (if any text summarizer exists) to generate human-readable documentation from code comments.
- **TReport (9985)** can feed into any Intelligence dashboard/analysis tool for trend detection across build health over time.
- **TLint (9980)** complexity scoring maps to the same Reynolds flow model used by Ternary Server (9885) for AI prompt routing — shared math.
- **NovaLang (9900)** is both a Creation tool (the compiler) and an Intelligence tool (the language runtime that AI agents execute). Its REPL (CLI Server 9887) serves as the primary interface for AI-generated code execution.

#### Creation <-> Infrastructure (Stack 2)
- **TSnap (9982)** writes snapshots to DeepStorage (9893) and can use Vault (9892) for encrypted snapshot archives.
- **TWatch (9981)** relies on filesystem events, which TSysMon (9905) also monitors — they should share the watcher substrate to avoid duplicate inotify/ReadDirectoryChanges handles.
- **TPackage (9978)** stores its registry in the same pattern as TQuery (9911) SQLite databases, and package artifacts go to DeepStorage (9893).
- **TPipe (9975)** can extract data from TFetch (9897) for HTTP sources and load into TCache (9901) or TBuffer (9886/9902) for caching layers — critical dependency on those services being UP.
- **TProfile (9977)** needs TSysMon (9905) for system-level metrics (CPU/memory) and TNet (9906) for network latency measurements.
- **TRelease (9986)** deploy coordination should integrate with whatever service orchestration Agent 2 designs — boot order, health checks, rolling restarts.
- **TTest (9970)** and **TContract (9983)** need network access via TNet (9906) for integration testing against live endpoints.
- **TMigrate (9976)** should coordinate with TRecover (9912) — a failed migration needs rollback, which is a recovery operation.

#### Pending Coordination (Agents 1 & 2 not yet written)
When Agents 1 and 2 complete their sections, the following integration points should be verified:
1. Does Intelligence stack have a text summarizer? If so, TDoc should consume it.
2. Does Infrastructure stack have a message bus? If so, TWatch events should publish there instead of SSE-only.
3. Does Infrastructure stack have a log aggregator? If so, all 25 Creation tools should emit structured logs to it.
4. Does Intelligence stack have an anomaly detector? If so, TProfile data should feed into it for auto-alerting on performance regressions.

---

## BENCHMARK SPECS — 75 TOOL PERFORMANCE TARGETS

### Benchmark Philosophy
Every tool is measured on 3 axes (ternary!):
- **SPEED**: Response time in ms (target: laminar < 27ms, transitional < 125ms, turbulent < 343ms)
- **ACCURACY**: Trit correctness (+1 when it should be +1, etc.)
- **THROUGHPUT**: Operations per second under load

### STACK 1: INTELLIGENCE BENCHMARKS

| Tool | Speed Target | Accuracy Target | Throughput Target | Benchmark Test |
|------|-------------|-----------------|-------------------|----------------|
| Hivemind | <343ms p95 | >90% trit quality | 50 queries/min | Route 100 diverse prompts across 10 channels |
| Cloud Router | <500ms p95 | >95% provider selection | 30 queries/min | Fan-out same prompt to 5 providers, compare |
| Nexus | <100ms p95 | 100% model catalog accuracy | 200 req/s | List/search 124 models |
| Ternary Server | <27ms p95 | 100% trit math | 1000 req/s | Modulate 10K ternary values |
| TSpeak | <50ms encode | >95% reconstruction | 500 msg/s | Encode/decode 1000 model messages |
| Cortex | <5000ms p95 | >80% response capture | 5 queries/min | Query Claude + GPT desktops |
| Closed Loop | <1000ms cycle | >85% self-heal | 1 cycle/min | Run 10 deliberation cycles |
| MaxPatch | <200ms probe | >90% fingerprint stability | 20 probes/min | Fingerprint 10 models twice, compare |
| SkipTrace | <500ms search | >70% correlation hit | 10 searches/min | Search 5 patterns in 100KB text |
| STT | <3000ms/clip | >90% WER accuracy | 5 clips/min | Transcribe 10 5-second clips |
| TSummarize | <2000ms p95 | >85% key info retention | 10 docs/min | Summarize 10 articles, human eval |
| TClassify | <100ms p95 | >90% category accuracy | 100 texts/min | Classify 500 texts across 10 categories |
| TReason | <5000ms p95 | >80% proof validity | 5 proofs/min | Solve 20 multi-step logic problems |
| TMemory | <50ms recall | >85% relevance | 200 recalls/s | Store 1000, recall 100 by similarity |
| TEmbed | <30ms encode | >95% cosine consistency | 500 encodes/s | Encode 1000 texts, verify nearest-neighbor |
| TAnomaly | <100ms detect | >90% anomaly precision | 100 checks/s | Inject 50 anomalies in 1000 normal readings |
| TPrompt | <200ms optimize | >80% improvement rate | 20 optimizations/min | Optimize 50 prompts, A/B test each |
| TEval | <10000ms eval | >90% ranking consistency | 3 evals/min | Evaluate 5 models on 10 tasks |
| TKnow | <30ms query | >95% traversal accuracy | 300 queries/s | Build 1000-node graph, 500 path queries |
| TTranslate | <1000ms p95 | >90% BLEU score | 20 translations/min | Translate 100 sentences across 5 languages |
| TAgent | <500ms spawn | >85% task completion | 10 agents/min | Spawn 20 agents with simple tasks |
| TContext | <20ms compress | >99% lossless restore | 1000 ops/s | Compress/expand 100 context windows |
| TFilter | <10ms scan | >95% detection rate | 2000 scans/s | Scan 1000 texts with 50 known violations |
| TVision | <3000ms p95 | >85% description quality | 5 images/min | Describe 20 diverse images |
| TLearn | <100ms feedback | >80% adaptation quality | 50 feedbacks/s | 500 feedback signals, measure model drift |

### STACK 2: INFRASTRUCTURE BENCHMARKS

| Tool | Speed Target | Accuracy Target | Throughput Target | Benchmark Test |
|------|-------------|-----------------|-------------------|----------------|
| Sentinel | <5000ms detect | >99% failure detection | continuous | Kill 5 random services, measure recovery time |
| VPN Core | <50ms encrypt | N/A (crypto correctness) | 100 MB/s encrypt | Encrypt/decrypt 100MB payload |
| TShell | <100ms scan | >95% file index accuracy | 200 ops/s | Index 10K files, query 500 |
| Vault | <200ms lock | 100% crypto integrity | 50 MB/s lock | Lock/unlock 100 files, verify hashes |
| DeepStorage | <10s/MB quantize | >99.99% restore accuracy | 10 MB/s quantize | Quantize 100MB, restore, byte-compare |
| TFetch | <1s first byte | >95% download completion | 50 MB/s sustained | Download 10 files (1-50MB each) |
| TKill | <100ms kill | 100% process termination | 50 kills/s | Kill/restart 20 test processes |
| TSysMon | <50ms snapshot | >99% metric accuracy | 100 snapshots/s | 1000 system snapshots, compare to OS APIs |
| TNet | <200ms probe | >95% reachability accuracy | 50 probes/s | Probe 100 hosts, verify results |
| TSecurity | <500ms scan | >90% threat detection | 20 scans/min | Scan 100 files with 10 known threats |
| TRecover | <2000ms recover | >90% context restoration | 5 recoveries/min | Corrupt 10 sessions, recover each |
| TBuffer (FIX) | <5ms lookup | >99% cache hit accuracy | 5000 lookups/s | Store 10K entries, query 50K times |
| TCache (MERGE) | <20ms semantic | >85% semantic relevance | 1000 lookups/s | Store 1K, query 5K similar texts |
| TFetch Proxy (FIX) | <50ms overhead | >99% pass-through | 100 req/s | Proxy 1000 requests, measure overhead |
| TBus | <5ms publish | >99.9% delivery guarantee | 10K events/s | Publish 100K events, verify all delivered |
| TLog | <10ms ingest | 100% log preservation | 5K logs/s | Ingest 100K log entries, search 1K queries |
| TMetrics | <10ms record | >99% metric accuracy | 10K metrics/s | Record 1M data points, query 100 aggregations |
| TCircuit | <1ms check | >99% state accuracy | 50K checks/s | Simulate 1000 failures, verify state transitions |
| TRate | <1ms check | >99% rate accuracy | 100K checks/s | 1M requests against 10 rate limits |
| TFirewall | <2ms check | >99% rule accuracy | 50K checks/s | 100K requests against 50 firewall rules |
| TConfig | <5ms get | 100% config accuracy | 10K reads/s | Store 500 configs, read 50K times |
| TRegistry | <10ms discover | >99% service accuracy | 1K discoveries/s | Register 75 services, discover 1000 times |
| TBackup | <30s full backup | >99.99% integrity | 5 backups/hour | Full system backup + restore + verify |
| TShutdown | <10s full drain | 100% clean shutdown | 1 shutdown/test | Graceful shutdown all 75 services in order |
| TDNS | <5ms resolve | >99% resolution accuracy | 5K resolves/s | Resolve 10K domains, verify against system DNS |

### STACK 3: CREATION BENCHMARKS

| Tool | Speed Target | Accuracy Target | Throughput Target | Benchmark Test |
|------|-------------|-----------------|-------------------|----------------|
| Tools | <20ms file op | 100% file integrity | 500 ops/s | Read/write/grep 1000 files |
| Ternary Tools | <50ms op | >99% data integrity | 200 ops/s | TDiff 100 pairs, TSync 50 dirs |
| CLI Server | <100ms exec | 100% parse accuracy | 50 commands/s | Execute 500 NovaLang expressions |
| NovaLang (FIX) | <200ms run | >99% interpreter accuracy | 30 programs/s | Run 100 .nova programs, verify outputs |
| TMedia | <1000ms convert | >95% format accuracy | 10 converts/min | Convert 50 files across 10 formats |
| TBuild | <500ms deps | >99% dep graph accuracy | 20 builds/min | Analyze 50 projects, build 20 |
| TCron | <10ms schedule | >99% timing accuracy | 100 schedules/s | Schedule 1000 tasks, verify execution times |
| TQuery | <50ms query | >99% SQL accuracy | 200 queries/s | Run 1000 SQL queries against 100K row table |
| TTest | <200ms per test | >99% assertion accuracy | 50 tests/s | Run 500 test cases across 20 test files |
| TScaffold | <500ms generate | >95% template accuracy | 10 scaffolds/min | Generate 20 microservice skeletons |
| TDoc | <1000ms generate | >90% docstring capture | 10 docs/min | Document 20 Python files |
| TSchema | <30ms validate | >99% validation accuracy | 500 validations/s | Validate 5000 JSON objects against 50 schemas |
| TGen | <5000ms generate | >80% code quality | 5 generations/min | Generate 20 functions from specs |
| TPipe | <200ms per stage | >99% data integrity | 100 records/s | ETL 10K records through 5-stage pipeline |
| TMigrate | <1000ms migrate | 100% migration integrity | 10 migrations/min | Run 50 migrations up and down |
| TProfile | <100ms measure | >95% measurement accuracy | 100 measurements/s | Profile 50 endpoints, verify against manual timing |
| TPackage | <200ms resolve | >99% dep accuracy | 50 resolves/s | Resolve dependency trees for 75 services |
| TDiffView | <100ms diff | >99% diff accuracy | 50 diffs/s | Diff 200 file pairs, verify hunks |
| TLint | <300ms check | >90% issue detection | 30 checks/min | Lint 100 Python files, compare to pylint |
| TWatch | <100ms detect | >99% change detection | 200 events/s | Modify 500 files, verify all events fired |
| TSnap | <2000ms capture | >99.9% state integrity | 5 snapshots/min | Snapshot 20 services, restore 10, verify |
| TContract | <200ms verify | >99% contract accuracy | 50 contracts/s | Record 200 contracts, replay 200 |
| TMock | <50ms response | >99% fixture accuracy | 200 req/s | Create 50 mock endpoints, hit 5000 times |
| TReport | <1000ms generate | >95% data aggregation | 10 reports/min | Generate 20 reports from live data |
| TRelease | <2000ms package | >99% artifact integrity | 5 releases/min | Package 10 services, verify artifacts |

### AGGREGATE TARGETS

```
TOTAL SERVICES:     75 (25 Intelligence + 25 Infrastructure + 25 Creation)
EXISTING:           35 (10 + 14 + 8 + Orchestrator + TLight + Brain)
NEW TO BUILD:       43 (15 Intelligence + 11 Infrastructure + 17 Creation)
TO FIX:              4 (TBuffer, TCache, TFetch Proxy, NovaLang)

PORT RANGES:
  Core:              9999 (Orchestrator), 9990 (Brain)
  Intelligence:      9875-9903 (existing) + 9920-9934 (new)
  Infrastructure:    9880-9912 (existing) + 9945-9955 (new)
  Creation:          9887-9911 (existing) + 9970-9986 (new)

PERFORMANCE FLOOR:
  p95 Latency:       < 343ms for all tools (turbulent boundary)
  Uptime:            > 99.5% per service (Sentinel-monitored)
  Recovery:          < 10s auto-restart (Sentinel watchdog)
  Cache Hit Rate:    > 80% (TBuffer/TCache)
  Compression:       > 50% savings on text (TZip/DeepStorage)

HARMONIC VALIDATION:
  Every tool has:    /health endpoint (3 states: +1/0/-1)
  Every tool tracks: Reynolds number per request
  Every tool uses:   3-5-7-13 constants (block=2187, pack=5, unit=7, frame=13)
  Every tool imports: nova_tlight.py (universal protection core)
```
