# NovaX Browser — Brave Fork with Ternary Encryption + Academic Crawler

**Date**: 2026-03-03
**Status**: Design approved
**Phase**: 13 (Browser + Research Archive)

---

## Vision

A full Brave browser fork rebranded as **NovaX Browser** with two unique layers:

1. **Ternary Encryption Layer** -- All network traffic flows through TZip + AES-256-GCM baked into Chromium's net/ stack. Every page, every API call, every model request gets ternary-compressed and encrypted before caching.

2. **Academic Crawler Engine** -- Background daemon (headless Chromium) that systematically crawls and archives research from thousands of sources across every field and discipline. Stored locally in TZip-compressed vaults. The hivemind's 100+ models search this archive first before hitting the live web.

**Dual-mode**: Human browses with ternary security, AI models autonomously research through it. Shared browser, two modes.

---

## 3-5-7-13 Harmonic Constants (carried from NovaX core)

- **3** = ternary states in matrix rain (-1, 0, +1)
- **5** = trit packing (3^5=243 per byte in TZip network filter)
- **7** = tool composition (7 sidebar panels, 7 context menu actions)
- **13** = TZip header bytes in network cache entries

---

## Architecture

### Base: Brave Browser (MPL 2.0, Chromium-based)

Brave uses a patching system -- `brave-core` contains overrides woven into Chromium source. NovaX follows the same pattern: a `novax-core` directory at `src/novax/` that patches on top of Brave. This allows merging upstream Brave updates without massive conflicts.

### What we keep from Brave (everything):
- Brave Shields (ad/tracker blocking)
- Tor private windows
- HTTPS Everywhere
- Fingerprint randomization
- Crypto wallet (BAT)
- All Chrome extensions supported
- DevTools

### What NovaX adds:
- Ternary encryption on all cached data
- TZip compression on network payloads (savings visible in DevTools)
- Built-in hivemind sidebar (ask models while browsing)
- Academic crawler with local archive search
- Reynolds-based traffic analysis (TShield in browser)
- Cyberpunk neon UI (dark #0d0d15, cyan glow, matrix rain)
- Neon N logo (pulsing glow animation)
- New tab page = NovaX AI Console

---

## Repository Structure

```
novax-browser/
+-- package.json                  <- Pins Brave version + NovaX deps
+-- scripts/
|   +-- novax_branding.js         <- Replace "Brave" -> "NovaX" strings
|   +-- novax_patches.js          <- Apply Chromium net/ patches
|   +-- novax_assets.js           <- Inject neon N logo, icons, themes
+-- src/
|   +-- novax/                    <- Mounted at src/novax/
|       +-- browser/
|       |   +-- novax_new_tab/    <- AI Console new tab page
|       |   +-- novax_sidebar/    <- Hivemind + Crawler + Archive sidebar
|       |   +-- novax_theme/      <- Cyberpunk dark theme
|       +-- net/
|       |   +-- tzip_filter.cc    <- TZip compress/decompress HTTP bodies
|       |   +-- ternary_cache.cc  <- AES-256-GCM encrypted disk cache
|       |   +-- tshield_monitor.cc <- Reynolds traffic analysis
|       |   +-- dns_ternary.cc    <- Ternary-encoded DNS
|       +-- crawler/
|       |   +-- crawler_daemon.cc <- Headless Chromium crawl engine
|       |   +-- source_registry.json <- 1000+ academic sources
|       |   +-- content_extractor.cc <- HTML/PDF -> clean text
|       |   +-- archive_indexer.cc   <- TIndex integration
|       +-- hivemind/
|       |   +-- hivemind_bridge.cc   <- localhost:9881 connection
|       |   +-- model_sidebar.cc     <- In-browser model chat
|       |   +-- context_menu.cc      <- "Ask Hivemind" right-click
|       +-- branding/
|       |   +-- novax_logo.svg       <- Neon N (multiple sizes)
|       |   +-- novax_icon.ico       <- Taskbar/desktop icon
|       |   +-- matrix_rain.js       <- Ternary digit rain animation
|       |   +-- neon_theme.css       <- Glow effects, glass-morphism
|       +-- chromium_src/            <- Overrides for Chromium files
|           +-- net/url_request/     <- Hook TZip into request pipeline
|           +-- chrome/browser/ui/   <- Theme overrides
+-- patches/                         <- Patch files for brave-core
+-- build/                           <- Build output
```

---

## Ternary Network Layer

### Injection points in Chromium's net/ stack:

| Layer | Chromium Location | NovaX Addition |
|-------|-------------------|----------------|
| Network intercept | src/net/url_request/ | TZip compress/decompress all HTTP bodies |
| Cache encryption | src/net/http/http_cache_* | AES-256-GCM encrypt entire disk cache |
| DNS encryption | src/net/dns/ | Ternary-encoded DNS queries |
| Traffic analysis | src/net/socket/ | Reynolds number on connection patterns |
| Model bridge | NEW: src/novax/hivemind/ | localhost:9881 for model queries |

### Data flow:

```
User Request -> Brave Shields (ad/tracker strip)
             -> TZip Compress Request Body
             -> HTTPS to server
             -> Response received
             -> TZip Compress Response for cache
             -> AES-256-GCM Encrypt -> Disk Cache
             -> TShield Reynolds analysis (log pattern)
             -> Render page
```

### Cache format (.novax.cache):
- 13-byte TZip header (magic + orig_size + trit_count + flags)
- AES-256-GCM encrypted payload
- Same vault format as nova_vault.py
- PBKDF2-SHA256 key derivation (600K iterations)

### Address bar dual-mode:

```
Web mode:  [N] [https://arxiv.org/paper]    [Shield:ON] [TZip:43%] [Re:27]
AI mode:   [N] [Ask: quantum entanglement]   [Models:15] [REASON]   [Re:340]
```

Typing "Ask:" prefix routes to hivemind instead of web search.

---

## Browser Visual Design

### Theme: Cyberpunk Neon (matching NovaX Desktop OS)

- Background: #0d0d15 (near-black)
- Primary: #00ffff (cyan neon glow)
- Accent: #bf5af2 (purple, for ternary tools)
- Success: #00ff41 (green, for loaded states)
- Warning: #ff9500 (orange, for loading/degraded)
- Error: #ff2d55 (red, for failed states)
- Glass panels: backdrop-filter: blur(18px), rgba backgrounds

### New Tab Page = NovaX AI Console:
- Full-screen ternary matrix rain (-1, 0, +1 instead of binary 0/1)
- Neon N logo center-top with logoPulse animation (3s cycle)
- Glass-morphism AI Console panel (chat with hivemind)
- Claude + Llama status badges top-right
- Sidebar quick-launch icons
- Search bar = hivemind query bar

### Tab indicators (ternary state):
- +1 (green glow): Page loaded successfully
- 0 (orange): Loading / processing
- -1 (red): Error / blocked

### Context menu additions:
- "Ask Hivemind about this" (selected text -> cluster_query)
- "Archive this page" (save to DeepStorage via TZip)
- "TZip stats" (compression ratio for current page)

---

## Academic Crawler Engine

### Source categories:

| Category | Sources | Est. Volume |
|----------|---------|-------------|
| Physics/Math | arXiv, APS, IOP, MathSciNet | ~2.5M papers |
| Biomedical | PubMed, PMC, bioRxiv, medRxiv | ~35M abstracts |
| Computer Science | ACM DL, IEEE Xplore, DBLP, Semantic Scholar | ~5M papers |
| General Science | Nature, Science, PLOS ONE, Springer Open | ~3M papers |
| Government | USA.gov, data.gov, NIST, NASA Technical Reports | ~10M documents |
| Legal | PACER, Supreme Court, Congress.gov, state courts | ~5M records |
| Patents | USPTO, EPO, WIPO, Google Patents | ~15M patents |
| Encyclopedia | Wikipedia (all languages), Britannica, Stanford Encyclopedia | ~60M pages |
| Education | MIT OCW, Khan Academy, Coursera catalog, OpenStax | ~500K courses |
| Standards | IETF RFCs, W3C specs, ISO previews, NIST standards | ~100K documents |
| History | Internet Archive texts, Project Gutenberg, HathiTrust | ~5M texts |
| Economics | FRED, World Bank, IMF, NBER working papers | ~2M datasets |

**Total estimated**: ~140M+ documents across all fields.

### Crawler architecture:

```
Crawler Daemon (port 9897, headless Chromium)
|
+-- Source Registry (JSON: URLs, schedules, CSS selectors, rate limits)
+-- Queue Manager (priority: user-requested > scheduled > discovery)
+-- Rate Limiter (robots.txt compliance, 1 req/s per domain default)
|
v
Fetch Page -> Extract Content -> Classify (Reynolds/Channel)
|                |                     |
|                v                     v
|          Clean HTML/PDF         REASON? MATH? CODE?
|          -> Plain text          -> Tag with FLOW_CHANNEL
|
v
TZip Compress -> AES-256-GCM Encrypt -> DeepStorage (tiered)
|
v
TIndex (ternary search index) -> Models search instantly
```

### Storage estimates:
- Average paper: ~50KB text after extraction
- TZip compression: ~50% reduction -> 25KB per paper
- 10M papers: ~250GB compressed + encrypted
- With DeepStorage dedup: ~150GB realistic
- Full 140M archive: ~2-3TB (could use cold/frozen tiers)

### Crawler respects:
- robots.txt (always)
- Rate limits (1 req/s default, configurable per domain)
- Open access only (no paywalled content)
- API-first where available (arXiv API, PubMed E-utilities, etc.)
- Incremental updates (only fetch new/changed content)

---

## Integration with NovaX Services

```
NovaX Browser
|
+---> Orchestrator (:9999)     <- All API routing
|       +---> Hivemind (:9881) <- Model queries from address bar
|       +---> Cloud Router (:9878) <- 31 cloud models
|       +---> TTools (:9894)   <- TShield traffic monitor
|       +---> TSpeak (:9895)   <- Model deliberation
|       +---> DeepStorage (:9893) <- Crawler archive
|
+---> Crawler Daemon (:9897)   <- NEW service
|       +-- Source Registry
|       +-- Queue + Rate Limiter
|       +-- TZip + AES-256-GCM -> DeepStorage
|
+---> Archive Index (via TIndex on :9894)
```

### New NovaLang builtins:
- browser_status() -- Browser + crawler health
- crawler_start(source) -- Begin crawling a source category
- crawler_pause() -- Pause all crawling
- archive_search(query) -- Search local academic archive
- archive_stats() -- Papers/pages per category

### New Orchestrator routes:
- GET /api/browser/status
- POST /api/crawler/start
- POST /api/crawler/pause
- GET /api/crawler/queue
- POST /api/archive/search
- GET /api/archive/stats

### New Desktop UI panel:
- "NovaX Browser" panel in desktop
- Crawler status grid (per-category progress)
- Archive size/growth chart
- Search box for archive queries

---

## Build Pipeline

### Prerequisites:
- Windows 11
- Visual Studio 2022 with C++ Desktop Development workload (~10GB)
- 100GB+ free disk space
- 16GB+ RAM (32GB recommended)
- Node.js v24+, Python 3, Git 2.41+

### Build steps:

```bash
# 1. Clone our repo
git clone novax-browser && cd novax-browser

# 2. Install deps (fetches depot_tools)
npm install

# 3. Initialize (clones Brave + Chromium ~30GB)
npm run init

# 4. Apply NovaX patches (branding + ternary layer + crawler)
npm run apply-novax-patches

# 5. Build (4-8 hrs first time, ~30min incremental)
npm run build Release

# 6. Output
out/Release/novax.exe
```

### Incremental development:
- After first build, changes to src/novax/ rebuild in ~30 minutes
- Branding changes (logos, strings) rebuild in ~5 minutes
- New tab page changes (HTML/CSS/JS) need no rebuild (served as web resources)

---

## Implementation Phases

### Phase 13A: Browser Shell (Week 1-2)
1. Clone brave-browser repo
2. Set up build environment (VS 2022, depot_tools)
3. First successful build of unmodified Brave
4. Rebrand: NovaX strings, neon N logo, dark theme
5. Custom new tab page (AI Console with matrix rain)
6. Build + test NovaX Browser binary

### Phase 13B: Ternary Network Layer (Week 3-4)
1. TZip filter in net/url_request/ (compress HTTP bodies)
2. Ternary cache encryption (AES-256-GCM disk cache)
3. TShield monitor (Reynolds on traffic patterns)
4. DevTools integration (show TZip savings per request)
5. DNS ternary encoding

### Phase 13C: Hivemind Integration (Week 5)
1. Hivemind bridge (localhost:9881 from browser)
2. "Ask:" prefix in address bar routes to models
3. Sidebar panel (model chat while browsing)
4. Context menu ("Ask Hivemind about this")
5. NovaLang builtins + orchestrator routes

### Phase 13D: Academic Crawler (Week 6-8)
1. Crawler daemon service (port 9897)
2. Source registry (start with arXiv, PubMed, Wikipedia)
3. Content extractor (HTML/PDF to clean text)
4. TZip + AES-256-GCM + DeepStorage pipeline
5. TIndex integration for search
6. Scale to 1000+ sources
7. Desktop UI panel for crawler management

### Phase 13E: Polish + Scale (Week 9+)
1. Installer/updater (NSIS or similar)
2. Auto-update mechanism (track upstream Brave releases)
3. Performance optimization
4. Scale crawler to millions of documents
5. Cold/frozen tier storage for massive archive

---

## Legal Notes

- Brave source: MPL 2.0 (allows modification + redistribution)
- Chromium source: BSD 3-Clause (allows modification + redistribution)
- Must not use Brave trademarks in the fork (we rebrand to NovaX)
- Academic content: crawl open-access only, respect robots.txt
- Personal/local use: no distribution concerns for self-hosted browser
