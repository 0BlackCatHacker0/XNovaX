"""NovaX MCP Server — Pure Python, direct HTTP to NovaX fleet.
No novalang dependency. Minimal. Reliable."""
import sys
import json
import urllib.request
import urllib.error

MCP_VERSION = "2024-11-05"
ORCH = "http://127.0.0.1:9999"
HIVE = "http://127.0.0.1:9881"
CLOUD = "http://127.0.0.1:9878"

TOOLS = [
    {"name":"nova_query","description":"Query the NovaX hivemind cluster. Uses N-S fluid dynamics to route your query through the optimal number of AI models with full deliberation.","inputSchema":{"type":"object","properties":{"prompt":{"type":"string","description":"The query to send to the hivemind"},"channel":{"type":"string","description":"Flow channel (REASON, MATH, CODE, INSTRUCT, FACT, LONG, VISION, LANGUAGE, AGENT, DOMAIN). Auto-detected if omitted."}},"required":["prompt"]}},
    {"name":"nova_status","description":"Get NovaX system status including running services, loaded models, and overall health.","inputSchema":{"type":"object","properties":{}}},
    {"name":"nova_tools","description":"Execute NovaX native tools: read (file), write (file), grep (search), glob (find files), run (command), edit (file). All data flows use TZip ternary compression.","inputSchema":{"type":"object","properties":{"tool":{"type":"string","description":"Which tool to use (read, write, grep, glob, run, edit)"},"path":{"type":"string","description":"File/directory path (for read, write, glob, edit)"},"pattern":{"type":"string","description":"Search pattern (for grep, glob)"},"content":{"type":"string","description":"Content to write (for write)"},"command":{"type":"string","description":"Command to run (for run)"},"old":{"type":"string","description":"Text to replace (for edit)"},"new":{"type":"string","description":"Replacement text (for edit)"}},"required":["tool"]}},
    {"name":"nova_multi","description":"TMulti tool composition: every tool gains secondary abilities. Modes: read(stats/diff/extract/classify), write(template/append/atomic), grep(analyze/replace/todo), glob(tree/size/recent), run(safe/timed/retry), edit(regex/multi), pipe(parallel/conditional). Returns ternary trits.","inputSchema":{"type":"object","properties":{"tool":{"type":"string","description":"Base tool to compose (read, write, grep, glob, run, edit, pipe)"},"mode":{"type":"string","description":"Composition mode (e.g. stats, analyze, tree, safe, todo)"},"path":{"type":"string","description":"File/directory path"},"pattern":{"type":"string","description":"Search pattern (for grep modes)"},"command":{"type":"string","description":"Command to execute (for run modes)"},"path_b":{"type":"string","description":"Second file path (for read/diff mode)"},"content":{"type":"string","description":"Content (for write modes)"},"template":{"type":"string","description":"Template string (for write/template mode)"},"old_string":{"type":"string","description":"Text to replace (for edit modes)"},"new_string":{"type":"string","description":"Replacement text (for edit modes)"},"glob":{"type":"string","description":"File glob filter (e.g. *.py)"}},"required":["tool","mode"]}},
    {"name":"nova_hive","description":"Query a specific AI model or the full hivemind swarm directly. Can target local Ollama models, cloud models, or desktop models.","inputSchema":{"type":"object","properties":{"prompt":{"type":"string","description":"The query"},"model":{"type":"string","description":"Specific model name (e.g. mistral, llama3.3, cortex:claude). Uses swarm if omitted."}},"required":["prompt"]}},
    {"name":"nova_ttools","description":"Execute NovaX ternary tools built on 3-5-7-13 harmonic constants. Tools: tdiff (3-state file diff), tcache_get/tcache_set (compressed cache), tsync (delta sync), tindex (ternary search index), tsearch (search index), tforge (Reynolds code analyzer), tstream (ternary streaming). TZombie: tzombie_scan, tzombie_kill, tzombie_sweep.","inputSchema":{"type":"object","properties":{"tool":{"type":"string","description":"Which ternary tool to use (tdiff, tcache_get, tcache_set, tsync, tindex, tsearch, tforge, tstream, tfilter, tzombie_scan, tzombie_kill, tzombie_sweep, status)"},"path":{"type":"string","description":"File path (for tdiff, tindex, tforge)"},"path_a":{"type":"string","description":"First file path (for tdiff comparison)"},"path_b":{"type":"string","description":"Second file path (for tdiff comparison)"},"key":{"type":"string","description":"Cache key (for tcache_get/set)"},"value":{"type":"string","description":"Cache value (for tcache_set)"},"query":{"type":"string","description":"Search query (for tsearch)"},"source":{"type":"string","description":"Source path (for tsync)"},"dest":{"type":"string","description":"Destination path (for tsync)"},"port":{"type":"number","description":"Port number (for tzombie_kill)"}},"required":["tool"]}},
    {"name":"nova_deep","description":"NovaX DeepStorage - N-S flow-routed compression, dedup, and tiered storage. Actions: scan (analyze directory), quantize (compress+store), restore (decompress), status (storage stats), watch/unwatch (auto-monitor directory).","inputSchema":{"type":"object","properties":{"action":{"type":"string","description":"DeepStorage action (scan, quantize, restore, status, watch, unwatch)"},"path":{"type":"string","description":"File or directory path"},"output":{"type":"string","description":"Output path (for restore)"}},"required":["action"]}},
    {"name":"nova_vault","description":"NovaX Vault - TZip ternary compress + AES-256-GCM encryption for files. Actions: lock (encrypt file), unlock (decrypt file), shred (secure delete with 3-pass overwrite), status (vault state).","inputSchema":{"type":"object","properties":{"action":{"type":"string","description":"Vault action (lock, unlock, shred, status)"},"path":{"type":"string","description":"File path to lock/unlock/shred"},"password":{"type":"string","description":"Encryption password (for lock/unlock)"}},"required":["action"]}},
    {"name":"nova_cortex","description":"NovaX Cortex - Desktop AI bridge. Query Claude Desktop or ChatGPT Desktop through UI automation. Actions: status, claude, gpt, both, chain, fuse, arrange.","inputSchema":{"type":"object","properties":{"action":{"type":"string","description":"Cortex action (status, claude, gpt, both, chain, fuse, arrange)"},"prompt":{"type":"string","description":"Prompt for claude/gpt/both/chain/fuse"},"rounds":{"type":"number","description":"Debate rounds for chain (default 1)"}},"required":["action"]}},
    {"name":"nova_cloud","description":"NovaX Cloud Router - Query specific cloud AI providers (OpenAI, Anthropic, Google, Mistral, Groq, DeepSeek, Cohere, Together, OpenRouter). Can target specific models or let the router choose.","inputSchema":{"type":"object","properties":{"prompt":{"type":"string","description":"The query to send"},"provider":{"type":"string","description":"Cloud provider (openai, anthropic, google, mistral, groq, deepseek, cohere, together, openrouter). Auto-routed if omitted."},"model":{"type":"string","description":"Specific model name. Uses provider default if omitted."}},"required":["prompt"]}},
    {"name":"nova_tbuffer","description":"NovaX TBuffer - Ternary Response Membrane. Compressed ternary cache between hivemind and world. Actions: query, store, write, lookup, status, invalidate.","inputSchema":{"type":"object","properties":{"action":{"type":"string","description":"TBuffer action (query, store, write, lookup, status, invalidate)"},"prompt":{"type":"string","description":"Prompt text (for query/store)"},"response":{"type":"string","description":"Response text (for store)"},"channel":{"type":"string","description":"Flow channel (for query/store)"},"entry_id":{"type":"string","description":"Entry ID (for lookup/invalidate/write)"},"data":{"type":"string","description":"Raw data (for write)"}},"required":["action"]}},
]

# Route table: tool_name -> (method, url_template)
ROUTES = {
    "nova_query":  ("POST", HIVE + "/query"),
    "nova_status": ("GET",  ORCH + "/api/services/health"),
    "nova_tools":  ("POST", ORCH + "/api/tools/execute"),
    "nova_multi":  ("POST", ORCH + "/api/tools/multi"),
    "nova_hive":   ("POST", HIVE + "/query"),
    "nova_ttools":  ("POST", ORCH + "/api/ttools/execute"),
    "nova_deep":    ("POST", ORCH + "/api/deep/execute"),
    "nova_vault":   ("POST", ORCH + "/api/vault/execute"),
    "nova_cortex":  ("POST", ORCH + "/api/cortex/execute"),
    "nova_cloud":   ("POST", CLOUD + "/query"),
    "nova_tbuffer": ("POST", ORCH + "/api/tbuffer/execute"),
}


def send(obj):
    line = json.dumps(obj, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def http_call(method, url, body=None):
    try:
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def handle_tool_call(name, args):
    route = ROUTES.get(name)
    if not route:
        return {"error": f"Unknown tool: {name}"}
    method, url = route
    if method == "GET":
        return http_call("GET", url)
    else:
        return http_call("POST", url, args)


def handle_message(msg):
    method = msg.get("method", "")
    mid = msg.get("id")

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": MCP_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "novax", "version": "1.0.0"}
        }})
    elif method == "notifications/initialized":
        pass  # no response needed
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name", "")
        args = params.get("arguments", {})
        result = handle_tool_call(name, args)
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
        }})
    elif method == "ping":
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
    elif mid is not None:
        send({"jsonrpc": "2.0", "id": mid, "error": {
            "code": -32601, "message": f"Method not found: {method}"
        }})


def main():
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            handle_message(msg)
        except json.JSONDecodeError:
            send({"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700, "message": "Parse error"
            }})


if __name__ == "__main__":
    main()
