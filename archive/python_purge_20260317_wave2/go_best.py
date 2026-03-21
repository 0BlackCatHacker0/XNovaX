"""Return the best piece (model) per Go territory based on win/loss score."""
import json, sys

def main():
    try:
        with open("C:/NovaX/data/go_pieces.json", "r") as f:
            data = json.load(f)
    except Exception:
        print(json.dumps({"ok": 0, "error": "no pieces file"}))
        return

    pieces = data.get("pieces", {})
    best = {}

    for key, piece in pieces.items():
        terr = piece.get("territory", "")
        wins = piece.get("wins", 0)
        losses = piece.get("losses", 0)
        score = wins - losses
        active = piece.get("active", 1)
        if not active:
            continue

        if terr not in best or score > best[terr]["score"]:
            best[terr] = {
                "provider": piece.get("provider", ""),
                "model": piece.get("model", ""),
                "territory": terr,
                "max_tokens": piece.get("max_tokens", 8192),
                "wins": wins,
                "losses": losses,
                "score": score,
            }

    print(json.dumps({"ok": 1, "best_per_territory": best, "territories": len(best)}))

if __name__ == "__main__":
    main()
