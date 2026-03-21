"""
NovaX Capability Verification Contract
DETECTED -> READ -> SCANNED -> WRITE_REQUESTED -> MODIFIED -> COMPLETE -> VERIFIED -> TRUSTED
Two truths: presence AND verified_effect
Token: NOVAX::<component_id>::<nonce>::READ>SCAN>WRITE>MODIFY>COMPLETE
"""
import uuid, time, hashlib, threading, logging
from enum import Enum

log = logging.getLogger("NovaX.Verify")

class Stage(Enum):
    DETECTED="DETECTED"; READ="READ"; SCANNED="SCANNED"
    WRITE_REQUESTED="WRITE_REQUESTED"; MODIFIED="MODIFIED"
    COMPLETE="COMPLETE"; VERIFIED="VERIFIED"; TRUSTED="TRUSTED"; FAILED="FAILED"

ORDER = [Stage.DETECTED, Stage.READ, Stage.SCANNED, Stage.WRITE_REQUESTED,
         Stage.MODIFIED, Stage.COMPLETE, Stage.VERIFIED, Stage.TRUSTED]

class Contract:
    def __init__(self, comp_id, comp_type="unknown"):
        self.id = str(uuid.uuid4())[:12]
        self.comp_id = comp_id
        self.comp_type = comp_type
        self.nonce = str(uuid.uuid4())[:8]
        self.stage = Stage.DETECTED
        self.history = [{"stage": "DETECTED", "ts": time.time()}]
        self.presence = False
        self.effect = False
        self.trusted = False
        self.token = None
        self.evidence = {}
        self.created = time.time()

    def advance(self, proof=None):
        idx = ORDER.index(self.stage) if self.stage in ORDER else -1
        if idx < 0 or idx >= len(ORDER) - 1:
            return {"ok": False, "error": "cannot advance"}
        nxt = ORDER[idx + 1]
        if nxt == Stage.READ:
            self.presence = True
        if nxt == Stage.TRUSTED and not (self.presence and self.effect):
            return {"ok": False, "error": "both truths required"}
        self.stage = nxt
        self.history.append({"stage": nxt.value, "ts": time.time()})
        if proof:
            self.evidence[nxt.value] = proof
            if nxt in (Stage.MODIFIED, Stage.COMPLETE) and proof.get("verified_change"):
                self.effect = True
        if nxt == Stage.TRUSTED:
            self.trusted = True
            stages = ">".join(h["stage"] for h in self.history if h["stage"] != "FAILED")
            raw = f"NOVAX::{self.comp_id}::{self.nonce}::{stages}"
            self.token = raw + "::SIG=" + hashlib.sha256(raw.encode()).hexdigest()[:16]
            log.info(f"TRUSTED: {self.comp_id}")
        return {"ok": True, "stage": nxt.value, "trusted": self.trusted}

    def fail(self, reason=""):
        self.stage = Stage.FAILED
        self.history.append({"stage": "FAILED", "ts": time.time(), "reason": reason})
        self.trusted = False; self.token = None

    def to_dict(self):
        return {"id": self.id, "comp_id": self.comp_id, "comp_type": self.comp_type,
                "stage": self.stage.value, "presence": self.presence, "effect": self.effect,
                "trusted": self.trusted, "token": self.token, "history": self.history,
                "evidence": {k: str(v)[:200] for k, v in self.evidence.items()}}

class VerificationRegistry:
    def __init__(self):
        self.contracts = {}
        self._lock = threading.Lock()

    def begin(self, comp_id, comp_type="unknown"):
        c = Contract(comp_id, comp_type)
        with self._lock: self.contracts[comp_id] = c
        return c

    def advance(self, comp_id, proof=None):
        c = self.contracts.get(comp_id)
        return c.advance(proof) if c else {"ok": False, "error": "no contract"}

    def fail(self, comp_id, reason=""):
        c = self.contracts.get(comp_id)
        if c: c.fail(reason)

    def is_trusted(self, comp_id):
        c = self.contracts.get(comp_id)
        return c.trusted if c else False

    def trusted_list(self):
        return [c.comp_id for c in self.contracts.values() if c.trusted]

    def all_contracts(self):
        return {k: v.to_dict() for k, v in self.contracts.items()}

    def summary(self):
        t = len(self.contracts)
        ok = sum(1 for c in self.contracts.values() if c.trusted)
        fail = sum(1 for c in self.contracts.values() if c.stage == Stage.FAILED)
        return {"total": t, "trusted": ok, "failed": fail, "pending": t - ok - fail}

    def auto_verify(self, comp_id, comp_type, presence_fn, effect_fn):
        c = self.begin(comp_id, comp_type)
        if not presence_fn():
            c.fail("presence failed"); return c
        c.advance({"response": True})      # -> READ
        c.advance({"scanned": True})        # -> SCANNED
        c.advance({"requested": True})      # -> WRITE_REQUESTED
        c.advance({"verified_change": effect_fn()})  # -> MODIFIED
        c.advance({"complete": True})       # -> COMPLETE
        if c.presence:
            c.advance({"verified": True})   # -> VERIFIED
        else:
            c.fail("no presence at verify"); return c
        if c.presence and c.effect:
            c.advance({"trusted": True})    # -> TRUSTED
        else:
            c.fail(f"trust failed: p={c.presence} e={c.effect}")
        return c
