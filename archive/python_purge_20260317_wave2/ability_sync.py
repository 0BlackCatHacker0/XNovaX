"""
NovaX Full-Spectrum Ability Scanner
====================================
Scans ALL NovaX capabilities — AI models, engines, services, tools — and
classifies them into ability categories for the Tripple Module amplifier.

Based on cymatics research: each unique ability is a resonant mode.
More modes = richer standing wave pattern = higher resonance score.
The 13:8 Fibonacci damping threshold means we want abilities UNDER 13
major categories (constructive zone) with sub-abilities adding depth.

Harmonic mapping:
  H3 (3 modes)  = Core AI abilities (chat, reasoning, code)
  H5 (5 modes)  = Engine abilities (physics, rendering, simulation, audio, microsoft)
  H7 (7 modes)  = Infrastructure abilities (cache, route, encrypt, compress, schedule, monitor, test)
  H13 (13 modes) = Full spectrum (all above + search, embed, stream, mesh, sync)
"""
import json, urllib.request

def fetch_json(url, timeout=5):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(resp.read())
    except:
        return None

def scan_ai_abilities():
    """H3 layer: AI model abilities from Model Registry."""
    data = fetch_json("http://127.0.0.1:9860/models/stats")
    if not data:
        return {}
    return data.get("ability_matrix", {})

def scan_engine_abilities():
    """H5 layer: NovaX engine capabilities (5 engines × 7 tools = 35 tools)."""
    engines = {
        "physics":    {"port": 9850, "tools": ["vector", "force", "particle", "fluid", "collide", "field", "solve"]},
        "microsoft":  {"port": 9851, "tools": ["windows", "registry", "process", "system", "theme", "clipboard", "notify"]},
        "rendering":  {"port": 9852, "tools": ["ascii", "chart", "svg", "canvas", "color", "layout", "scene"]},
        "simulation": {"port": 9853, "tools": ["automata", "agents", "monte", "network", "evolve", "terrain", "swarm"]},
        "audio":      {"port": 9854, "tools": ["wave", "freq", "synth", "envelope", "filter", "rhythm", "encode"]},
    }
    abilities = {}
    for name, info in engines.items():
        health = fetch_json(f"http://127.0.0.1:{info['port']}/health")
        if health:
            abilities[name] = len(info["tools"])  # Count of tools as ability strength
    return abilities

def scan_infrastructure_abilities():
    """H7 layer: Infrastructure service capabilities."""
    infra_map = {
        "caching":      [9956, 9886],        # TCache, TBuffer
        "routing":      [9963, 9979],        # TRouter, TGateway
        "encryption":   [9892],              # Nova Vault
        "compression":  [9972, 9893],        # TCompress, DeepStorage
        "scheduling":   [9959, 9910],        # TScheduler, TCron
        "monitoring":   [9905, 9950, 9953],  # TSysMon, TWatch, TMetrics
        "testing":      [9934, 9933],        # TTest, TBenchmark
    }
    abilities = {}
    for name, ports in infra_map.items():
        alive = 0
        for port in ports:
            health = fetch_json(f"http://127.0.0.1:{port}/health")
            if health:
                alive += 1
        if alive > 0:
            abilities[name] = alive
    return abilities

def scan_extended_abilities():
    """H13 layer: Extended spectrum capabilities."""
    extended_map = {
        "search":       [9903],              # TSkipTrace
        "embedding":    [9960],              # TEmbed
        "streaming":    [9955, 9998],        # TStream, WebSocket
        "mesh":         [9951, 9882],        # TMesh, Nexus
        "sync":         [9976],              # TSync
        "pipeline":     [9966, 9927],        # TPipeline, TCI
        "graph":        [9958],              # TGraph
        "queue":        [9957],              # TQueue
        "resilience":   [9948, 9984],        # TResilience, TBalance
        "security":     [9907, 9987, 9952],  # TSecurity, TShield, TAuth
        "intelligence": [9924, 9990],        # TIntelligence, NovaBrain
        "data":         [9928, 9916, 9917],  # TAlchemy, TSQLite, TRedis
        "media":        [9908, 9918, 9922],  # TMedia, TImage, TFFmpeg
        "text":         [9923, 9920, 9921],  # TText, TMarkdown, TYAML
        "networking":   [9906, 9919],        # TNet, THTTP
        "devops":       [9913, 9914, 9915],  # TGit, TDocker, TTerraform
        "orchestration":[9999, 9869],        # Orchestrator, NovaPrime
        "audit":        [9974, 9964],        # TAudit, TValidator
        "memory":       [9978],              # TMemory
        "notification": [9975],              # TNotify
        "profiling":    [9980],              # TProfile
        "replay":       [9937],              # TReplay
        "documentation":[9935],              # TDocs
        "configuration":[9932, 9941],        # TConfig2, TConfig
        "locking":      [9981],              # TLock
        "diffing":      [9973],              # TDiff
        "snapshot":     [9965],              # TSnapshot
    }
    abilities = {}
    for name, ports in extended_map.items():
        alive = 0
        for port in ports:
            health = fetch_json(f"http://127.0.0.1:{port}/health")
            if health:
                alive += 1
        if alive > 0:
            abilities[name] = alive
    return abilities

def scan_swarm_abilities():
    """Hivemind and multi-model swarm capabilities."""
    abilities = {}
    hive = fetch_json("http://127.0.0.1:9881/health")
    if hive:
        abilities["swarm"] = 1
        abilities["deliberation"] = 1
    cl = fetch_json("http://127.0.0.1:9888/health")
    if cl:
        abilities["feedback"] = 1
    mp = fetch_json("http://127.0.0.1:9889/health")
    if mp:
        abilities["alignment"] = 1
    return abilities

# ── Main scan ──
ai = scan_ai_abilities()
engines = scan_engine_abilities()
infra = scan_infrastructure_abilities()
extended = scan_extended_abilities()
swarm = scan_swarm_abilities()

# Merge all (AI abilities + engine + infra + extended + swarm)
all_abilities = {}
for source in [ai, engines, infra, extended, swarm]:
    for k, v in source.items():
        all_abilities[k] = all_abilities.get(k, 0) + v

total = sum(all_abilities.values())
print(json.dumps({
    "ok": True,
    "abilities": all_abilities,
    "count": len(all_abilities),
    "total": total,
    "breakdown": {
        "ai": {"count": len(ai), "total": sum(ai.values()) if ai else 0},
        "engines": {"count": len(engines), "total": sum(engines.values()) if engines else 0},
        "infra": {"count": len(infra), "total": sum(infra.values()) if infra else 0},
        "extended": {"count": len(extended), "total": sum(extended.values()) if extended else 0},
        "swarm": {"count": len(swarm), "total": sum(swarm.values()) if swarm else 0},
    }
}))
