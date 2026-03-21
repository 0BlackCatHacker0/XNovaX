# skills_engine.py — Skills Engine: matches user queries to learned skills
# Loads from C:\NovaX\skills/*.json, matches via trigger phrases + token overlap.
# Orchestrator calls: match_skill(text), load_skills(), list_skills(), save_skill()

import os
import json
import time
import re

_SKILLS_DIR = r"C:\NovaX\skills"
_skills = {}  # {skill_id: skill_dict}
_loaded = False

# Suggestion levels: auto-execute → suggest → inform → silent
_SUGGESTION_LEVELS = {}  # {skill_id: "auto"|"suggest"|"inform"|"silent"}
_CONFIDENCE_SCORES = {}  # {skill_id: float 0-1}


def _tokenize(text):
    """Split text into lowercase tokens for matching."""
    return set(re.findall(r'[a-z]+', text.lower()))


def load_skills(path=None):
    """Load all skills from the skills directory."""
    global _skills, _loaded
    skills_dir = path or _SKILLS_DIR
    if not os.path.isdir(skills_dir):
        return _skills

    for fname in os.listdir(skills_dir):
        full = os.path.join(skills_dir, fname)
        if fname.endswith(".json") and os.path.isfile(full):
            try:
                with open(full, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # Flat dict: {skill_id: skill_data}
                    for sid, sdata in data.items():
                        if isinstance(sdata, dict):
                            sdata["id"] = sid
                            sdata["source"] = fname
                            # Pre-compute token set for fast matching
                            trigger_text = " ".join(sdata.get("trigger_phrases", []))
                            sdata["_tokens"] = _tokenize(
                                trigger_text + " " + sdata.get("name", "") + " " + sdata.get("description", "")
                            )
                            _skills[sid] = sdata
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            sid = item.get("id", item.get("name", f"skill_{len(_skills)}"))
                            item["id"] = sid
                            item["source"] = fname
                            trigger_text = " ".join(item.get("trigger_phrases", []))
                            item["_tokens"] = _tokenize(
                                trigger_text + " " + item.get("name", "") + " " + item.get("description", "")
                            )
                            _skills[sid] = item
            except Exception:
                pass

    _loaded = True
    return _skills


def match_skill(query, threshold=0.3):
    """
    Match a user query to the best skill using trigger phrases + token overlap.
    Returns the best matching skill dict or None.
    """
    if not _loaded:
        load_skills()
    if not query or not _skills:
        return None

    query_lower = query.lower()
    query_tokens = _tokenize(query)
    best_score = 0
    best_skill = None

    for sid, skill in _skills.items():
        score = 0

        # 1. Exact trigger phrase match (highest weight)
        for phrase in skill.get("trigger_phrases", []):
            if phrase.lower() in query_lower:
                score += 2.0
                break

        # 2. Token overlap scoring
        skill_tokens = skill.get("_tokens", set())
        if skill_tokens and query_tokens:
            overlap = query_tokens & skill_tokens
            if overlap:
                # Jaccard-like: overlap / query size (how much of query matches)
                score += len(overlap) / max(len(query_tokens), 1)

        # 3. Category keyword boost
        category = skill.get("category", "")
        if category and category in query_lower:
            score += 0.5

        # 4. Apply learned confidence modifier
        confidence = _CONFIDENCE_SCORES.get(sid, 0.5)
        score *= (0.5 + confidence)  # Range: 0.25x to 1.5x

        if score > best_score:
            best_score = score
            best_skill = skill

    if best_skill and best_score >= threshold:
        # Return a clean copy without internal tokens
        result = {k: v for k, v in best_skill.items() if not k.startswith("_")}
        result["confidence"] = round(min(best_score, 1.0), 3)
        result["match_score"] = round(best_score, 3)
        return result

    return None


def list_skills():
    """List all loaded skills (clean, no internal fields)."""
    if not _loaded:
        load_skills()
    return [
        {k: v for k, v in s.items() if not k.startswith("_")}
        for s in _skills.values()
    ]


def save_skill(name, data):
    """Save a skill definition to memory and disk."""
    if isinstance(data, dict):
        data["id"] = name
        data["saved_at"] = time.time()
        data["_tokens"] = _tokenize(
            " ".join(data.get("trigger_phrases", []))
            + " " + data.get("name", name)
            + " " + data.get("description", "")
        )
        _skills[name] = data

        # Persist to custom skills file
        custom_path = os.path.join(_SKILLS_DIR, "custom_skills.json")
        try:
            if os.path.isfile(custom_path):
                with open(custom_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            else:
                existing = {}
            existing[name] = {k: v for k, v in data.items() if not k.startswith("_")}
            with open(custom_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass
    return True


def update_confidence(skill_id, delta=0.0):
    """Update confidence score for a skill based on usage feedback."""
    current = _CONFIDENCE_SCORES.get(skill_id, 0.5)
    _CONFIDENCE_SCORES[skill_id] = max(0.0, min(1.0, current + delta))
    return True


def get_skill_suggestion_level(skill_id=None):
    """Get the suggestion level for a skill."""
    if skill_id:
        return _SUGGESTION_LEVELS.get(skill_id, "suggest")
    return "suggest"


def set_skill_suggestion_level(skill_id, level="suggest"):
    """Set suggestion level: auto, suggest, inform, or silent."""
    if level in ("auto", "suggest", "inform", "silent"):
        _SUGGESTION_LEVELS[skill_id] = level
    return True


def skill_stats():
    """Get skills engine statistics."""
    if not _loaded:
        load_skills()
    categories = {}
    for s in _skills.values():
        cat = s.get("category", "uncategorized")
        categories[cat] = categories.get(cat, 0) + 1
    return {
        "total_skills": len(_skills),
        "categories": categories,
        "custom_skills": sum(1 for s in _skills.values() if s.get("source") == "custom_skills.json"),
        "loaded": _loaded,
    }
