"""
NovaX Gameplay Learning System
Learns from experience rather than images.
Pipeline: Frame -> Perception -> State -> Action -> Outcome -> Memory
Skill records with cooperative improvement across models.
"""
import uuid, time, json, os, threading, logging

log = logging.getLogger("NovaX.Gameplay")

SKILLS_PATH = "C:/NovaX/memory/skills"

class SkillRecord:
    """One learned skill: situation + action + success rate."""
    def __init__(self, situation, action, game="unknown"):
        self.id = str(uuid.uuid4())[:10]
        self.situation = situation
        self.action = action
        self.game = game
        self.attempts = 0
        self.successes = 0
        self.last_used = None
        self.created = time.time()

    @property
    def success_rate(self):
        return round(self.successes / max(self.attempts, 1), 3)

    def record_outcome(self, success):
        self.attempts += 1
        if success:
            self.successes += 1
        self.last_used = time.time()

    def to_dict(self):
        return {"id": self.id, "situation": self.situation, "action": self.action,
                "game": self.game, "attempts": self.attempts, "successes": self.successes,
                "success_rate": self.success_rate, "last_used": self.last_used}

class GameState:
    """Structured game state extracted from perception."""
    def __init__(self, game="unknown"):
        self.game = game
        self.frame = 0
        self.entities = []
        self.player = {}
        self.environment = {}
        self.timestamp = time.time()

    def to_dict(self):
        return {"game": self.game, "frame": self.frame, "entities": self.entities,
                "player": self.player, "environment": self.environment, "ts": self.timestamp}

class ModelRole:
    MOVEMENT = "movement"
    TACTICS = "tactics"
    PLANNING = "planning"
    AIMING = "aiming"

class GameplayLearner:
    """
    Experience-based learning system.
    Multiple model roles collaborate: movement, tactics, planning, aiming.
    Decisions merged by NovaX before execution.
    """
    def __init__(self):
        self.skill_graph = {}     # situation_hash -> SkillRecord
        self.active_game = None
        self.model_roles = {}     # model_name -> ModelRole
        self.decision_buffer = [] # pending decisions from models
        self.episode_log = []     # full episode history
        self._lock = threading.Lock()
        os.makedirs(SKILLS_PATH, exist_ok=True)
        self._load_skills()

    def _load_skills(self):
        path = os.path.join(SKILLS_PATH, "skill_graph.json")
        if os.path.isfile(path):
            try:
                data = json.load(open(path, encoding="utf-8"))
                for k, v in data.items():
                    s = SkillRecord(v["situation"], v["action"], v.get("game", "unknown"))
                    s.id = v.get("id", s.id)
                    s.attempts = v.get("attempts", 0)
                    s.successes = v.get("successes", 0)
                    self.skill_graph[k] = s
                log.info(f"Loaded {len(self.skill_graph)} skills")
            except Exception as e:
                log.error(f"Skill load failed: {e}")

    def _save_skills(self):
        path = os.path.join(SKILLS_PATH, "skill_graph.json")
        data = {k: v.to_dict() for k, v in self.skill_graph.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def assign_role(self, model_name, role):
        self.model_roles[model_name] = role
        log.info(f"Gameplay: {model_name} -> {role}")

    def set_game(self, game_name):
        self.active_game = game_name
        self.episode_log = []
        log.info(f"Gameplay: Active game -> {game_name}")

    def observe(self, state):
        """Pipeline step: receive perceived game state."""
        if isinstance(state, dict):
            gs = GameState(state.get("game", self.active_game or "unknown"))
            gs.entities = state.get("entities", [])
            gs.player = state.get("player", {})
            gs.environment = state.get("environment", {})
            gs.frame = state.get("frame", 0)
        else:
            gs = state
        self.episode_log.append({"type": "observe", "state": gs.to_dict(), "ts": time.time()})
        return gs

    def propose_action(self, model_name, action, confidence=1.0):
        """A model proposes an action for the current state."""
        role = self.model_roles.get(model_name, "unknown")
        self.decision_buffer.append({
            "model": model_name, "role": role,
            "action": action, "confidence": confidence, "ts": time.time()
        })

    def merge_decisions(self):
        """Merge all model proposals into one final action."""
        if not self.decision_buffer:
            return None
        # Weight by confidence, prefer role-specific expertise
        best = max(self.decision_buffer, key=lambda d: d["confidence"])
        merged = {
            "final_action": best["action"],
            "decided_by": best["model"],
            "role": best["role"],
            "confidence": best["confidence"],
            "alternatives": len(self.decision_buffer) - 1,
        }
        self.episode_log.append({"type": "decision", "merged": merged, "ts": time.time()})
        self.decision_buffer = []
        return merged

    def record_outcome(self, situation_key, action, success):
        """Record outcome to update skill graph."""
        if situation_key not in self.skill_graph:
            self.skill_graph[situation_key] = SkillRecord(
                situation_key, action, self.active_game or "unknown")
        self.skill_graph[situation_key].record_outcome(success)
        self.episode_log.append({
            "type": "outcome", "situation": situation_key,
            "action": action, "success": success, "ts": time.time()
        })
        # Auto-save periodically
        if len(self.episode_log) % 20 == 0:
            self._save_skills()

    def best_action(self, situation_key):
        """Look up best known action for a situation."""
        skill = self.skill_graph.get(situation_key)
        if skill and skill.success_rate > 0.5:
            return {"action": skill.action, "confidence": skill.success_rate, "from": "memory"}
        return None

    def save(self):
        self._save_skills()

    def status(self):
        return {
            "active_game": self.active_game,
            "skills": len(self.skill_graph),
            "model_roles": self.model_roles,
            "episode_length": len(self.episode_log),
            "pending_decisions": len(self.decision_buffer),
        }

    def skill_summary(self, top_n=20):
        sorted_skills = sorted(self.skill_graph.values(), key=lambda s: s.success_rate, reverse=True)
        return [s.to_dict() for s in sorted_skills[:top_n]]
