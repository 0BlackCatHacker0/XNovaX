"""
NovaX Digital Twin Service - Port 9946
Learns user preferences, communication style, and decision patterns
to personalize all NovaX responses. All data stays local.
"""

import json
import os
import re
import time
import threading
from datetime import datetime, timezone
from collections import Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PROFILE_PATH = os.path.join(DATA_DIR, "user_profile.json")
HOST = "127.0.0.1"
PORT = 9946
MAX_DECISIONS = 100
SAVE_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Profile management
# ---------------------------------------------------------------------------

def default_profile():
    return {
        "response_length": {"short": 0, "medium": 0, "long": 0, "preferred": "medium"},
        "complexity": {"simple": 0, "technical": 0, "expert": 0, "preferred": "technical"},
        "topics": {},
        "style": {"formal": 0.0, "casual": 0.0, "technical": 0.0, "preferred": "technical"},
        "active_hours": [0] * 24,
        "decisions": [],
        "explicit_preferences": {},
        "interaction_count": 0,
        "first_seen": datetime.now(timezone.utc).isoformat(),
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }


def load_profile():
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure all keys exist (forward compat)
            base = default_profile()
            for k, v in base.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            pass
    return default_profile()


def save_profile(profile):
    with SAVE_LOCK:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = PROFILE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=True)
        # Atomic-ish rename
        if os.path.exists(PROFILE_PATH):
            os.replace(tmp, PROFILE_PATH)
        else:
            os.rename(tmp, PROFILE_PATH)


PROFILE = load_profile()

# ---------------------------------------------------------------------------
# Analysis helpers (lightweight, no ML)
# ---------------------------------------------------------------------------

TECHNICAL_WORDS = {
    "api", "function", "class", "module", "server", "port", "endpoint",
    "database", "query", "deploy", "debug", "error", "exception", "log",
    "config", "parameter", "variable", "thread", "async", "request",
    "response", "json", "http", "tcp", "socket", "cache", "buffer",
    "compile", "runtime", "kernel", "process", "container", "docker",
    "git", "branch", "merge", "pipeline", "ci", "cd", "test", "mock",
    "algorithm", "hash", "encrypt", "token", "auth", "oauth", "cors",
    "ternary", "hivemind", "nova", "novalang", "orchestrator", "model",
}

CASUAL_MARKERS = {
    "hey", "hi", "yo", "sup", "cool", "awesome", "nice", "lol",
    "haha", "yeah", "nah", "ok", "okay", "thanks", "thx", "btw",
    "gonna", "wanna", "gotta", "dunno", "kinda", "sorta", "idk",
}

FORMAL_MARKERS = {
    "please", "kindly", "would", "could", "shall", "regarding",
    "therefore", "furthermore", "additionally", "consequently",
    "respectfully", "appreciate", "sincerely", "acknowledge",
}

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "about",
    "between", "under", "above", "it", "its", "this", "that",
    "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "she", "they", "them", "their", "what", "which", "who",
    "how", "when", "where", "why", "not", "no", "so", "if", "or",
    "and", "but", "all", "each", "every", "both", "few", "more",
}


def classify_length(text):
    """Classify text length as short/medium/long."""
    words = len(text.split())
    if words < 30:
        return "short"
    elif words < 150:
        return "medium"
    return "long"


def classify_complexity(text):
    """Classify text complexity by technical word density."""
    words = text.lower().split()
    if not words:
        return "simple"
    tech = sum(1 for w in words if w in TECHNICAL_WORDS)
    ratio = tech / len(words)
    if ratio > 0.08:
        return "expert"
    elif ratio > 0.03:
        return "technical"
    return "simple"


def detect_style(text):
    """Return style scores for a piece of text."""
    words = set(text.lower().split())
    casual = len(words & CASUAL_MARKERS)
    formal = len(words & FORMAL_MARKERS)
    technical = len(words & TECHNICAL_WORDS)
    return {"formal": formal, "casual": casual, "technical": technical}


def extract_topics(text, top_n=5):
    """Extract candidate topic words from text."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    filtered = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return [w for w, _ in Counter(filtered).most_common(top_n)]


def extract_explicit_preferences(text):
    """Detect explicit preference statements."""
    prefs = {}
    lower = text.lower()
    # "I like X" / "I prefer X"
    for pattern in [r"i (?:like|prefer|want|love)\s+(.+?)(?:\.|,|$)",
                    r"(?:don'?t|do not)\s+(?:like|want|show)\s+(.+?)(?:\.|,|$)"]:
        for m in re.finditer(pattern, lower):
            val = m.group(1).strip()[:80]
            if "don" in pattern:
                prefs[val] = "dislike"
            else:
                prefs[val] = "like"
    # Concise / detailed
    if any(w in lower for w in ["be concise", "keep it short", "brief", "tldr"]):
        prefs["response_length"] = "short"
    if any(w in lower for w in ["more detail", "explain more", "elaborate", "in depth"]):
        prefs["response_length"] = "long"
    return prefs


def pick_preferred(counts_dict):
    """Pick the key with the highest count, ignoring 'preferred' key."""
    filtered = {k: v for k, v in counts_dict.items() if k != "preferred"}
    if not filtered or max(filtered.values()) == 0:
        return counts_dict.get("preferred", "medium")
    return max(filtered, key=filtered.get)


# ---------------------------------------------------------------------------
# Core update logic
# ---------------------------------------------------------------------------

def observe(query, response, feedback="none"):
    """Process one interaction and update the profile."""
    global PROFILE
    now = datetime.now(timezone.utc)
    hour = datetime.now().hour  # local hour

    # Interaction count
    PROFILE["interaction_count"] += 1
    PROFILE["last_seen"] = now.isoformat()

    # Active hours
    PROFILE["active_hours"][hour] += 1

    # Response length preference (from what the user GOT and liked)
    resp_len = classify_length(response)
    if feedback == "good":
        PROFILE["response_length"][resp_len] += 2
    elif feedback == "bad":
        # They disliked this length, so don't boost it
        pass
    else:
        PROFILE["response_length"][resp_len] += 1
    PROFILE["response_length"]["preferred"] = pick_preferred(PROFILE["response_length"])

    # Complexity (from the query -- what level the user operates at)
    q_complexity = classify_complexity(query)
    PROFILE["complexity"][q_complexity] += 1
    PROFILE["complexity"]["preferred"] = pick_preferred(PROFILE["complexity"])

    # Style detection from query
    style = detect_style(query)
    for k in ("formal", "casual", "technical"):
        PROFILE["style"][k] += style[k]
    total_style = sum(PROFILE["style"][k] for k in ("formal", "casual", "technical"))
    if total_style > 0:
        PROFILE["style"]["preferred"] = max(
            ("formal", "casual", "technical"),
            key=lambda k: PROFILE["style"][k]
        )

    # Topics
    topics = extract_topics(query)
    for t in topics:
        if t not in PROFILE["topics"]:
            PROFILE["topics"][t] = {"count": 0, "last_seen": "", "sentiment": 0.0}
        PROFILE["topics"][t]["count"] += 1
        PROFILE["topics"][t]["last_seen"] = now.isoformat()
        if feedback == "good":
            PROFILE["topics"][t]["sentiment"] = min(1.0, PROFILE["topics"][t]["sentiment"] + 0.1)
        elif feedback == "bad":
            PROFILE["topics"][t]["sentiment"] = max(-1.0, PROFILE["topics"][t]["sentiment"] - 0.1)

    # Explicit preferences from query text
    explicit = extract_explicit_preferences(query)
    if explicit:
        PROFILE["explicit_preferences"].update(explicit)
        # Apply length preference immediately if detected
        if "response_length" in explicit:
            pref = explicit["response_length"]
            PROFILE["response_length"][pref] += 5  # strong signal
            PROFILE["response_length"]["preferred"] = pick_preferred(PROFILE["response_length"])

    # Decision tracking
    if feedback in ("good", "bad"):
        decision = {
            "context": query[:200],
            "choice": feedback,
            "response_length": resp_len,
            "complexity": q_complexity,
            "timestamp": now.isoformat(),
        }
        PROFILE["decisions"].append(decision)
        if len(PROFILE["decisions"]) > MAX_DECISIONS:
            PROFILE["decisions"] = PROFILE["decisions"][-MAX_DECISIONS:]

    save_profile(PROFILE)
    return True


def suggest(query):
    """Suggest personalization parameters for an incoming query."""
    q_complexity = classify_complexity(query)
    q_topics = extract_topics(query, top_n=3)

    # Base suggestion from profile
    suggestion = {
        "response_length": PROFILE["response_length"]["preferred"],
        "complexity": PROFILE["complexity"]["preferred"],
        "style": PROFILE["style"]["preferred"],
        "relevant_topics": [],
        "notes": [],
    }

    # Check explicit preferences
    ep = PROFILE.get("explicit_preferences", {})
    if "response_length" in ep:
        suggestion["response_length"] = ep["response_length"]
        suggestion["notes"].append("User explicitly set response_length")

    # If the query is expert-level, don't dumb it down
    if q_complexity == "expert" and PROFILE["complexity"]["preferred"] != "simple":
        suggestion["complexity"] = "expert"

    # Check if any query topics match known favorites
    top_topics = sorted(
        PROFILE["topics"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:20]
    fav_set = {t for t, info in top_topics if info["sentiment"] >= 0}
    disliked = {t for t, info in top_topics if info["sentiment"] < -0.3}

    for t in q_topics:
        if t in fav_set:
            suggestion["relevant_topics"].append({"topic": t, "affinity": "positive"})
        elif t in disliked:
            suggestion["relevant_topics"].append({"topic": t, "affinity": "negative"})
            suggestion["notes"].append(f"User has negative sentiment toward '{t}'")

    return suggestion


def get_patterns():
    """Analyze discovered patterns from interaction history."""
    patterns = {
        "total_interactions": PROFILE["interaction_count"],
        "preferred_response_length": PROFILE["response_length"]["preferred"],
        "preferred_complexity": PROFILE["complexity"]["preferred"],
        "preferred_style": PROFILE["style"]["preferred"],
        "top_topics": [],
        "peak_hours": [],
        "recent_decisions_summary": {"good": 0, "bad": 0},
        "explicit_preferences": PROFILE.get("explicit_preferences", {}),
    }

    # Top topics by count
    sorted_topics = sorted(
        PROFILE["topics"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:10]
    patterns["top_topics"] = [
        {"topic": t, "count": info["count"], "sentiment": round(info["sentiment"], 2)}
        for t, info in sorted_topics
    ]

    # Peak active hours
    hours = PROFILE["active_hours"]
    if max(hours) > 0:
        threshold = max(hours) * 0.5
        patterns["peak_hours"] = [h for h in range(24) if hours[h] >= threshold]

    # Decision summary
    for d in PROFILE["decisions"][-50:]:
        choice = d.get("choice", "none")
        if choice in patterns["recent_decisions_summary"]:
            patterns["recent_decisions_summary"][choice] += 1

    # Satisfaction rate
    total_rated = sum(patterns["recent_decisions_summary"].values())
    if total_rated > 0:
        good = patterns["recent_decisions_summary"]["good"]
        patterns["satisfaction_rate"] = round(good / total_rated, 2)

    return patterns


def get_active_hours():
    """Return the active hours histogram with analysis."""
    hours = PROFILE["active_hours"]
    total = sum(hours)
    result = {
        "histogram": {str(h): hours[h] for h in range(24) if hours[h] > 0},
        "total_observations": total,
        "peak_hours": [],
        "quiet_hours": [],
    }
    if total > 0 and max(hours) > 0:
        threshold = max(hours) * 0.5
        result["peak_hours"] = [h for h in range(24) if hours[h] >= threshold]
        result["quiet_hours"] = [h for h in range(24) if hours[h] == 0]
    return result


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class TwinHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Digital Twin service."""

    def log_message(self, fmt, *args):
        # Quieter logging
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "/health":
            self._send_json({
                "status": "healthy",
                "service": "digital_twin",
                "port": PORT,
                "interactions": PROFILE["interaction_count"],
                "uptime_profile": PROFILE["last_seen"],
            })

        elif path == "/twin/profile":
            self._send_json(PROFILE)

        elif path == "/twin/suggest":
            query = params.get("query", [""])[0]
            if not query:
                self._send_json({"error": "query parameter required"}, 400)
                return
            self._send_json(suggest(query))

        elif path == "/twin/patterns":
            self._send_json(get_patterns())

        elif path == "/twin/active-hours":
            self._send_json(get_active_hours())

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/twin/observe":
            try:
                body = self._read_body()
                query = body.get("query", "")
                response = body.get("response", "")
                feedback = body.get("feedback", "none")
                if not query:
                    self._send_json({"error": "query field required"}, 400)
                    return
                if feedback not in ("good", "bad", "none"):
                    feedback = "none"
                observe(query, response, feedback)
                self._send_json({
                    "status": "observed",
                    "interaction_count": PROFILE["interaction_count"],
                    "current_preferences": {
                        "response_length": PROFILE["response_length"]["preferred"],
                        "complexity": PROFILE["complexity"]["preferred"],
                        "style": PROFILE["style"]["preferred"],
                    }
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/twin/preference":
            try:
                body = self._read_body()
                key = body.get("key", "")
                value = body.get("value", "")
                if not key or not value:
                    self._send_json({"error": "key and value required"}, 400)
                    return
                # Apply known structured preferences
                if key == "response_length" and value in ("short", "medium", "long"):
                    PROFILE["response_length"][value] += 10
                    PROFILE["response_length"]["preferred"] = value
                elif key == "complexity" and value in ("simple", "technical", "expert"):
                    PROFILE["complexity"][value] += 10
                    PROFILE["complexity"]["preferred"] = value
                elif key == "style" and value in ("formal", "casual", "technical"):
                    PROFILE["style"][value] += 10
                    PROFILE["style"]["preferred"] = value
                else:
                    # Store as explicit preference
                    PROFILE["explicit_preferences"][key] = value
                save_profile(PROFILE)
                self._send_json({"status": "preference_set", "key": key, "value": value})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        else:
            self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        global PROFILE
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/twin/reset":
            PROFILE = default_profile()
            save_profile(PROFILE)
            self._send_json({"status": "reset", "message": "All learned data cleared"})
        else:
            self._send_json({"error": "not found"}, 404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"NovaX Digital Twin starting on {HOST}:{PORT}")
    print(f"  Profile: {PROFILE_PATH}")
    print(f"  Interactions tracked: {PROFILE['interaction_count']}")
    server = HTTPServer((HOST, PORT), TwinHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDigital Twin shutting down")
        save_profile(PROFILE)
        server.server_close()


if __name__ == "__main__":
    main()
