# NovaX DEEP MICRO SWARM — Collaboration Hub
# All agents: READ this file, WRITE your findings, BUILD on others' work

## MISSION: Full upgrade of NovaX to 75-tool architecture
## RULE: Every agent produces WORKING CODE, not just analysis

## SQUAD ASSIGNMENTS:
- ENGINEER-1: Fix TBuffer (9886) — merge cache layers, get caching online
- ENGINEER-2: Fix NovaLang (9900) — get the language runtime back up
- ENGINEER-3: Build TBus (9945) — message bus for inter-service communication
- CS-ALGO: Build TCircuit (9948) + TRate (9949) — resilience layer
- RESEARCH: Build TEmbed (9924) + TClassify (9921) — intelligence foundation
- DIAGNOSTICS: Security hardening — bind 127.0.0.1, CORS lockdown across all services

## SHARED CONTEXT:
- All new tools import nova_tlight.py (C:\NovaX\nova_tlight.py)
- All tools use tserve() for HTTP, tbody_safe() for body parsing
- All tools return trits (+1/0/-1), track Reynolds, have /health
- Port assignments are FINAL (see collab_workspace.md)
- 3-5-7-13 harmonic constants apply everywhere

## AGENT FINDINGS LOG:
(agents append here as they work)
