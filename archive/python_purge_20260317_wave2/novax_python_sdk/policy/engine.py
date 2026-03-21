"""Policy engine - evaluates whether actions are allowed."""
from ..objects import PolicyDecision, RiskLevel, Intent
from ..events.bus import bus, POLICY_DENIED

class PolicyEngine:
    def __init__(self):
        self.rules = []
        self.mode = "normal"

    def add_rule(self, name, check_fn, risk=RiskLevel.LOW):
        self.rules.append({"name": name, "check": check_fn, "risk": risk})

    def evaluate(self, intent: Intent) -> PolicyDecision:
        matched = []
        max_risk = RiskLevel.SAFE
        for rule in self.rules:
            if rule["check"](intent):
                matched.append(rule["name"])
                if rule["risk"].value > max_risk.value:
                    max_risk = rule["risk"]
        decision = PolicyDecision(
            allowed=max_risk.value <= RiskLevel.MEDIUM.value or self.mode == "autonomous",
            risk=max_risk, rules_matched=matched,
            requires_approval=max_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL))
        if not decision.allowed:
            bus.emit(POLICY_DENIED, {"intent": intent.text, "risk": max_risk.value})
        return decision

    def set_mode(self, mode): self.mode = mode
