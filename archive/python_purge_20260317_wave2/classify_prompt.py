"""Classify a prompt into a Go territory for optimal model routing."""
import json, sys

CODE_SIGNALS = [
    "write code", "function", "implement", "debug", "fix bug", "refactor",
    "class ", "def ", "import ", "const ", "var ", "let ", "async ", "await ",
    "python", "javascript", "typescript", "rust", "golang", "java", "c++",
    "sql", "query", "database", "api", "endpoint", "regex", "algorithm",
    "syntax", "compile", "build", "deploy", "docker", "git", "commit",
    "test", "unit test", "pytest", "jest", "```", "code review",
]

REASONING_SIGNALS = [
    "explain why", "reason", "analyze", "think step by step", "logic",
    "proof", "theorem", "math", "calculate", "solve", "equation",
    "compare and contrast", "evaluate", "assess", "deduce", "infer",
    "philosophy", "ethical", "argument", "hypothesis", "conclusion",
    "chain of thought", "step by step", "reasoning",
]

IMAGE_SIGNALS = [
    "image", "picture", "photo", "describe what you see", "screenshot",
    "visual", "look at", "diagram", "chart", "graph", "draw",
]

AUDIO_SIGNALS = [
    "audio", "sound", "music", "voice", "speak", "listen", "transcript",
    "speech", "tts", "text to speech", "whisper",
]

EMBEDDING_SIGNALS = [
    "embed", "embedding", "vector", "similarity", "semantic search",
    "rag", "retrieval", "cosine",
]

def classify_prompt(prompt):
    pl = prompt.lower()
    scores = {"code": 0, "reasoning": 0, "image": 0, "audio": 0, "embedding": 0}

    for sig in CODE_SIGNALS:
        if sig in pl:
            scores["code"] += 1
    for sig in REASONING_SIGNALS:
        if sig in pl:
            scores["reasoning"] += 1
    for sig in IMAGE_SIGNALS:
        if sig in pl:
            scores["image"] += 1
    for sig in AUDIO_SIGNALS:
        if sig in pl:
            scores["audio"] += 1
    for sig in EMBEDDING_SIGNALS:
        if sig in pl:
            scores["embedding"] += 1

    # Short prompts likely want fast models
    if len(prompt) < 50 and max(scores.values()) == 0:
        return "fast"

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return "chat"

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()
    territory = classify_prompt(prompt)

    # Also load best model for this territory
    try:
        data = json.load(open("C:/NovaX/data/go_pieces.json"))
        pieces = data.get("pieces", {})
        best = None
        best_score = -999999
        for key, piece in pieces.items():
            if piece.get("territory") == territory and piece.get("active", 1):
                score = piece.get("wins", 0) - piece.get("losses", 0)
                if score > best_score:
                    best_score = score
                    best = piece
    except:
        best = None

    result = {"territory": territory}
    if best:
        result["provider"] = best["provider"]
        result["model"] = best["model"]
        result["max_tokens"] = best["max_tokens"]
    print(json.dumps(result))
