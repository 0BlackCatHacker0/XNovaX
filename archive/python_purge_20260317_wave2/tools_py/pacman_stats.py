"""Stats reader for pacman_registry.json v2.0"""
import json
try:
    d = json.load(open("C:/NovaX/data/pacman_registry.json"))
    s = d.get("stats", {})
    models = d.get("models", {})
    skills = d.get("skills", {})
    abilities = d.get("abilities", {})
    features = d.get("features", {})

    s["total_models"] = len(models)
    s["total_skills"] = len(skills)
    s["total_abilities"] = len(abilities)
    s["ready_abilities"] = sum(1 for a in abilities.values() if a.get("status") == "ready")
    s["total_features"] = len(features)
    s["active_features"] = sum(1 for f in features.values() if f.get("status") == "active")
    s["total_skill_instances"] = sum(
        v.get("count", 0) for v in skills.values()
    )

    cats = {}
    for sk_data in skills.values():
        cat = sk_data.get("category", "unknown")
        cats[cat] = cats.get(cat, 0) + 1
    s["categories"] = cats
    s["version"] = d.get("version", "1.0.0")

    print(json.dumps(s))
except Exception as e:
    print(json.dumps({"error": str(e)}))
