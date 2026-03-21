"""
Hivemind Helper — Scatter/Warm queries to Ollama models
Called by nova_hivemind_service.nova via nova_run()
"""
import sys
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

OLLAMA_URL = "http://127.0.0.1:11434"


def query_model(model, prompt, system_prompt, timeout):
    """Query a single Ollama model."""
    t0 = time.time()
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=timeout
        )
        data = r.json()
        elapsed = int((time.time() - t0) * 1000)

        if "error" in data:
            return {
                "model": model,
                "ok": False,
                "error": data["error"],
                "response": "",
                "time_ms": elapsed
            }

        return {
            "model": model,
            "ok": True,
            "response": data.get("response", ""),
            "time_ms": elapsed,
            "eval_count": data.get("eval_count", 0),
            "eval_duration": data.get("eval_duration", 0)
        }
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        return {
            "model": model,
            "ok": False,
            "error": str(e),
            "response": "",
            "time_ms": elapsed
        }


def scatter(payload_str):
    """Scatter query to multiple models in parallel."""
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        print(json.dumps({"results": [], "ok_count": 0, "total_ms": 0, "error": "invalid_json"}))
        return

    models = payload.get("models", [])
    prompt = payload.get("prompt", "")
    system_prompt = payload.get("system", "")
    timeout = payload.get("timeout", 30)
    max_workers = min(payload.get("max_workers", 13), 13)
    early_return = payload.get("early_return", 7)

    if not models or not prompt:
        print(json.dumps({"results": [], "ok_count": 0, "total_ms": 0, "error": "missing_models_or_prompt"}))
        return

    t0 = time.time()
    results = []
    ok_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(query_model, m, prompt, system_prompt, timeout): m
            for m in models
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result.get("ok"):
                ok_count += 1
            # Early return if we have enough good results
            if ok_count >= early_return:
                break

    total_ms = int((time.time() - t0) * 1000)
    print(json.dumps({
        "results": results,
        "ok_count": ok_count,
        "total_ms": total_ms
    }))


def warm(payload_str):
    """Warm up models by sending a tiny prompt."""
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        print(json.dumps({"warmed": 0, "error": "invalid_json"}))
        return

    models = payload.get("models", [])
    max_workers = min(payload.get("max_workers", 5), 10)

    warmed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(query_model, m, "hi", "", 10): m
            for m in models
        }
        for future in as_completed(futures):
            result = future.result()
            if result.get("ok"):
                warmed += 1

    print(json.dumps({"warmed": warmed, "total": len(models)}))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: hivemind_helper.py <scatter|warm> <json_payload>"}))
        sys.exit(1)

    cmd = sys.argv[1]
    payload = sys.argv[2]

    if cmd == "scatter":
        scatter(payload)
    elif cmd == "warm":
        warm(payload)
    else:
        print(json.dumps({"error": f"unknown command: {cmd}"}))
