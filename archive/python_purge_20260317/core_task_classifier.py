# task_classifier.py — Intent classifier for NovaX queries
# Classifies user text into task categories and risk levels.
# Orchestrator calls: classify(text), classify_risk(text)

import re

# Category patterns — each maps to trigger words/phrases
_CATEGORIES = {
    "code": [
        r"\b(code|program|function|class|debug|error|fix bug|syntax|compile|build|import|npm|pip|git)\b",
        r"\b(python|javascript|rust|typescript|novalang|html|css|java|c\+\+)\b",
    ],
    "file": [
        r"\b(file|folder|directory|create file|delete file|read file|write|save|open|rename|move|copy)\b",
        r"\b(path|extension|\.py|\.js|\.nova|\.json|\.txt)\b",
    ],
    "system": [
        r"\b(system|process|cpu|memory|ram|disk|service|restart|reboot|kill|port|pid|health)\b",
        r"\b(install|uninstall|update|upgrade|package|driver)\b",
    ],
    "search": [
        r"\b(search|find|look up|google|what is|who is|where is|when did)\b",
        r"\b(wiki|article|documentation|docs|reference|source)\b",
    ],
    "creative": [
        r"\b(write|story|poem|song|creative|design|imagine|generate|compose|draft)\b",
        r"\b(blog|essay|email|letter|script|content|marketing)\b",
    ],
    "analysis": [
        r"\b(analyze|explain|compare|evaluate|review|assess|audit|inspect|scan|check)\b",
        r"\b(why|how does|what causes|difference between|pros and cons)\b",
    ],
    "terminal": [
        r"\b(run|execute|command|terminal|shell|powershell|cmd|bash|script)\b",
        r"\b(ls|dir|cd|mkdir|rm|mv|cp|grep|curl|wget)\b",
    ],
    "network": [
        r"\b(api|http|request|endpoint|url|fetch|download|upload|server|client)\b",
        r"\b(port|socket|tcp|udp|dns|ip|proxy|vpn)\b",
    ],
    "data": [
        r"\b(data|database|sql|query|table|schema|csv|json|xml|parse)\b",
        r"\b(sort|filter|aggregate|transform|clean|merge|join)\b",
    ],
    "chat": [],  # Default fallback
}

# Risk patterns — actions that modify state
_RISK_PATTERNS = {
    "high": [
        r"\b(delete|remove|drop|destroy|format|wipe|purge|reset)\b",
        r"\b(sudo|admin|root|elevated|force|override)\b",
        r"\b(password|credential|secret|token|api.?key|private.?key)\b",
    ],
    "medium": [
        r"\b(modify|change|update|edit|replace|overwrite|rename)\b",
        r"\b(install|uninstall|restart|reboot|kill|stop)\b",
        r"\b(send|email|post|publish|deploy|push)\b",
    ],
    "low": [
        r"\b(read|view|list|show|get|fetch|search|find|check|status)\b",
        r"\b(explain|describe|help|what|how|why)\b",
    ],
}

# Trit mapping: -1 = destructive, 0 = neutral, +1 = safe/read-only
_RISK_TRITS = {"high": -1, "medium": 0, "low": 1}


def classify(text, context=None):
    """
    Classify a user query into a task category.
    Returns: {"category": str, "confidence": float, "trit": int, "scores": dict}
    """
    if not text:
        return {"category": "chat", "confidence": 0.0, "trit": 0}

    text_lower = text.lower()
    scores = {}

    for category, patterns in _CATEGORIES.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            score += len(matches)
        scores[category] = score

    # Find best match
    best_cat = max(scores, key=scores.get) if scores else "chat"
    best_score = scores.get(best_cat, 0)

    if best_score == 0:
        best_cat = "chat"

    # Normalize confidence (sigmoid-like: more matches = higher confidence)
    confidence = min(best_score / (best_score + 2), 0.99) if best_score > 0 else 0.1

    # Trit: +1 for safe categories, 0 for neutral, -1 for risky
    safe_cats = {"chat", "search", "creative", "analysis"}
    risky_cats = {"terminal", "system", "file"}
    trit = 1 if best_cat in safe_cats else (-1 if best_cat in risky_cats else 0)

    return {
        "category": best_cat,
        "confidence": round(confidence, 3),
        "trit": trit,
        "scores": {k: v for k, v in scores.items() if v > 0},
    }


def classify_risk(text, context=None):
    """
    Classify the risk level of a user query.
    Returns: {"risk": str, "score": float, "trit": int, "triggers": list}
    """
    if not text:
        return {"risk": "low", "score": 0.0, "trit": 1}

    text_lower = text.lower()
    triggers = []

    for level in ("high", "medium", "low"):
        for pattern in _RISK_PATTERNS[level]:
            matches = re.findall(pattern, text_lower)
            if matches:
                triggers.append({"level": level, "matches": matches[:3]})

    # Determine overall risk from highest-severity trigger
    if any(t["level"] == "high" for t in triggers):
        risk = "high"
        score = 0.9
    elif any(t["level"] == "medium" for t in triggers):
        risk = "medium"
        score = 0.5
    else:
        risk = "low"
        score = 0.1

    return {
        "risk": risk,
        "score": round(score, 2),
        "trit": _RISK_TRITS.get(risk, 0),
        "triggers": triggers[:5],
    }
