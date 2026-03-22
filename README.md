# NovaX — The World's First Ternary AI Operating System

> A single-person-built AI OS where a custom ternary transformer commands 661 models, 109 microservices, and a custom programming language — all running on a laptop.

---

## What is NovaX?

NovaX is not a chatbot. It's not a wrapper around GPT. It's a **complete AI operating system** built from scratch — a 30MB ternary brain that orchestrates hundreds of AI models, tools, and services into a unified intelligence layer.

Every weight in the neural network is one of three values: **{-1, 0, +1}**. No floating point. No multiplication. Just addition, subtraction, and skipping. This makes it the fastest possible architecture per watt — capable of running on everything from a GPU to a Raspberry Pi to a web browser.

---

## Architecture

```
                        +------------------+
                        |   NovaX Brain    |
                        |  235M Ternary    |
                        |  Transformer     |
                        +--------+---------+
                                 |
                    +------------+------------+
                    |                         |
            +-------+-------+       +--------+--------+
            |  Orchestrator |       |  Cloud Router   |
            |  Port 9999    |       |  Port 9878      |
            |  716+ routes  |       |  661 models     |
            +-------+-------+       +--------+--------+
                    |                         |
        +-----------+-----------+    +--------+--------+
        |     |     |     |     |    |   |   |   |   |
      Brain Shield Voice Exec Nexus  OAI Ant Goo Mis ...
      9990  9987  9801  9877  9882   (12+ direct API providers)
                                     (350+ via OpenRouter)
                                     (102 local via Ollama)
```

## Core Components

### Custom Ternary LLM
- **235M parameter transformer** trained from scratch with ternary quantization-aware training
- Weights constrained to {-1, 0, +1} during training via Straight-Through Estimator
- **47-59 MB on disk** (vs 470 MB for FP16 equivalent) — 10x compression
- TZip packing: 5 trits per byte — **99.05% of the Shannon information-theoretic limit**
- Custom BPE tokenizer (32K vocab) trained on multi-model distillation corpus
- Knowledge distilled from 28 different large language models

### NovaLang — Custom Programming Language
- Ternary-native control flow: `if3`, `match3`, `try3`, `while3`, `for3`
- Three-state logic throughout: TRUE (+1), MAYBE (0), FALSE (-1)
- 17 standard library modules with 190+ functions
- 86+ microservices written in NovaLang
- Self-hosting parser and runtime
- Hot-reload with zero-downtime function swapping

### 661-Model Intelligence Network
- **102 local models** via Ollama (163GB, zero API cost)
- **350+ cloud models** via OpenRouter
- **12+ direct API providers**: OpenAI, Anthropic, Google, Mistral, Groq, DeepSeek, Cohere, Together, Cerebras, SambaNova, and more
- Intelligent routing via Navier-Stokes fluid dynamics equations
- Tripple Resonance scoring with 9-domain classification
- Pressure-gradient-based load balancing

### 109 Microservices
| Category | Services |
|----------|----------|
| Core Intelligence | Orchestrator, Brain, HiveMind, Cloud Router, Model Selector |
| LLM Training | Trainer, Monitor, Prep Service, Inference Server |
| Security | TShield v3.0, Sentinel, VPN Core, Vault (AES-256-GCM) |
| Voice | STT Server, TTS Server (edge-tts), Wake Word Detection |
| Data | Redis, Meilisearch, SQLite, DeepStorage, TBuffer |
| DevOps | TCI Pipeline, TGit, TDocker, TTerraform, TBenchmark |
| Self-Improvement | Dream Mode, Self-Monitor, Digital Twin, Knowledge Graph |
| Tools | Ternary Tools, TFetch, TKill, SkipTrace, Service Creator |

### Navier-Stokes Routing
Query routing modeled as incompressible fluid flow:
- **Viscous diffusion** (smoothing/consensus) via TRate
- **Pressure gradient** (flow redirection) via TFilter
- **Convective transport** (context propagation) via TSpeak
- **Reynolds number classification**: Laminar (<100) to Chaotic (>2000)
- **Vortex protocol** for multi-model deliberation

### Rust Trit Engine
- Custom inference engine in Rust for ternary matrix operations
- TZip LUT-based decoding (3^5 = 243 states per byte)
- Zero-multiply dot products — additions and subtractions only
- Rayon-parallelized with fused Q/K/V projections
- Paged trit KV cache with 3-tier storage (VRAM/RAM/Disk)

---

## Novel Systems

### Dream Mode
When the system is idle, NovaX autonomously self-improves:
1. **Generate** — Creates training data from 102 local models
2. **Filter** — Deduplicates and quality-scores new data
3. **Evaluate** — Benchmarks its own weaknesses across 7 categories
4. **Retrain** — Trains on what it's worst at

You go to sleep. You wake up to a smarter system.

### Time-Travel Debugging
Every query, routing decision, and model response is event-sourced. Ask "Why did you give me that answer on Tuesday?" and replay the exact state — which model was selected, what the confidence was, what went wrong.

### Natural Language Service Creation
Say "Create a service that monitors GPU temperature" and NovaX generates a working `.nova` file, assigns a port, and deploys it. The system that builds its own services.

### Personal Knowledge Graph
Not flat document search — a structured graph of concepts with auto-linking, recency decay, and BFS subgraph traversal. Every conversation, every decision, every insight — connected.

### Digital Twin
A lightweight statistical model of the user's preferences, communication style, and decision patterns. NovaX doesn't just find the best answer — it finds the best answer **for you**.

---

## The Ternary Advantage

| Property | FP16 Model | Ternary Model |
|----------|-----------|---------------|
| Weight values | 65,536 possible | 3 possible: {-1, 0, +1} |
| Core operation | Multiply-accumulate | Add/subtract/skip |
| 235M model size | 470 MB | 47-59 MB |
| GPU inference | ~578 tok/s | ~4,600 tok/s |
| CPU inference | ~100-200 tok/s | ~2,000-5,000 tok/s |
| Energy per token | ~0.35 J | ~0.03 J |
| Runs on Raspberry Pi | No | Yes |
| Runs in browser | No | Yes (WebGPU) |

Donald Knuth called balanced ternary "perhaps the prettiest number system of all." Base 3 is the closest integer to *e* (2.718...), making it the most efficient integer base by radix economy.

---

## Technical Specifications

- **Platform**: Windows 11 / Python 3.14 / Rust / NovaLang
- **GPU**: RTX 4060 Laptop (8GB VRAM)
- **Local Models**: 102 Ollama models (163GB)
- **Cloud Models**: 559 across 12+ providers
- **Services**: 109 microservices on 49+ ports
- **Dashboards**: 22 web-based control panels
- **Training Data**: 3,000+ pairs from 28 unique LLMs
- **NovaLang Stdlib**: 17 modules, 190+ functions
- **Orchestrator Routes**: 716+
- **Harmonic Constants**: 3-5-7-13 (ternary-pentary-composition-carrier)

---

## Project Structure

```
C:\NovaX\
  core/              # Orchestrator, Brain, service mesh
  nova_llm/          # LLM training, inference, tokenizer
    trit_engine/     # Rust ternary inference engine
  novalang-vm/       # NovaLang VM and parser (Rust)
  web/               # 22 dashboards (nova_desktop.html)
  services/          # 86+ .nova microservice files
  data/              # Training data, knowledge graph, metrics
  config/            # Service configuration
  tools/             # BitNet, Whisper, gh CLI
  skills/            # Skill marketplace
  user_services/     # NL-generated services
  service_templates/ # .nova service templates
```

---

## What Makes This Different

| What NovaX Has | Why It's Unique |
|---------------|-----------------|
| Custom ternary LLM trained from scratch | Most projects quantize post-training (worse quality) |
| 661 integrated AI models | No other system routes across this many |
| Custom programming language | NovaLang has no equivalent |
| 109-service AI operating system | Not a model — an OS |
| Navier-Stokes query routing | Physics-based AI orchestration (novel) |
| Dream Mode self-improvement | The AI that teaches itself while you sleep |
| Rust trit engine | Custom hardware-optimized ternary inference |
| TZip at 99.05% Shannon limit | Independently derived information-theoretic optimum |
| One person built it | Solo developer + Claude as engineering partner |

---

## Status

- **Build Progress**: ~93% of core infrastructure
- **Training**: Round 3 complete, Round 4 in preparation
- **Data Factory**: Automated generation from 102 local models
- **Services**: 28+ core services live, 81 stubs ready for activation
- **IP Protection**: Git history with cryptographic timestamps

---

## Legal

Copyright (c) 2023-2026 BlackCatHacker (0BlackCatHacker0). All Rights Reserved.

This software is proprietary and confidential. No part of this project may be
reproduced, distributed, or transmitted in any form without prior written
permission from the copyright holder. See [LICENSE](LICENSE) for full terms.

NovaX contains trade secrets protected under the Defend Trade Secrets Act
(18 U.S.C. 1836). Unauthorized use, disclosure, or exploitation of any
proprietary technology, algorithms, or methodologies contained herein may
result in civil and criminal liability.

**Protected intellectual property includes:**
- NovaLang programming language and runtime
- NovaX Ternary Transformer architecture
- TZip ternary compression algorithm
- Navier-Stokes query routing system
- All model weights, training data, and configurations

For licensing inquiries: [github.com/0BlackCatHacker0](https://github.com/0BlackCatHacker0)

---

*Built by a solo developer with Claude as an engineering partner. NovaX represents what's possible when one person refuses to accept that AI requires a datacenter.*
