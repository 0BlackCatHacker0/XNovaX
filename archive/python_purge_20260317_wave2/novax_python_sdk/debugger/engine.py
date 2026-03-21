"""NovaX Continuous Verification & Repair Engine - The Nervous System."""
import time,json,os,threading,logging
from novax.debugger.contracts import ButtonContract,ProofType
from novax.debugger.watchdog import Watchdog,FailureSignature

log=logging.getLogger("NovaX.Debugger.Engine")
SIGNATURES_PATH="C:/NovaX/memory/signatures.json"

class DebugEngine:
    def __init__(self):
        self.watchdog=Watchdog()
        self.contracts={};self.active_watchers=0
        self.total_checks=0;self.total_repairs=0;self.total_prevented=0
        self.last_repair_ts=None;self.running=False;self._lock=threading.Lock()
        self._register_default_contracts()
        self._load_signatures()
    def _register_default_contracts(self):
        c=ButtonContract("bridge.start","Start NovaX Bridge",action_cmd="cd /d C:/NovaX && start /B python nova_bridge_v3.py")
        c.expect(ProofType.PORT_OPEN,port=9999)
        c.expect(ProofType.HTTP_OK,url="http://127.0.0.1:9999/api/status")
        c.repair_with("kill_old",command="powershell -c \"Get-Process -Id (Get-NetTCPConnection -LocalPort 9999).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force\"")
        c.repair_with("restart_bridge",command="cd /d C:/NovaX && start /B python nova_bridge_v3.py")
        self.contracts[c.id]=c
        c=ButtonContract("brain.start","Start NovaX Brain")
        c.expect(ProofType.PORT_OPEN,port=9990)
        c.repair_with("restart_brain",command="cd /d C:/NovaX && start /B python -m novax.brain")
        self.contracts[c.id]=c
        c=ButtonContract("ollama.start","Start Ollama")
        c.expect(ProofType.PORT_OPEN,port=11434)
        c.expect(ProofType.HTTP_OK,url="http://127.0.0.1:11434/api/tags")
        c.repair_with("start_ollama",command="start /B ollama serve")
        self.contracts[c.id]=c
        c=ButtonContract("bridge.health","Bridge health")
        c.expect(ProofType.PORT_OPEN,port=9999)
        c.expect(ProofType.HTTP_OK,url="http://127.0.0.1:9999/api/status")
        self.contracts[c.id]=c
        c=ButtonContract("websocket.health","WebSocket health")
        c.expect(ProofType.PORT_OPEN,port=9998)
        self.contracts[c.id]=c
        c=ButtonContract("fs.novax","NovaX filesystem")
        c.expect(ProofType.FILE_EXISTS,path="C:/NovaX/novax/__init__.py")
        self.contracts[c.id]=c
        # Route validation contracts — Layer 2 security sublayer
        for path,label in [("/health","Health endpoint"),("/api/status","Status API"),
                           ("/api/vcc","VCC API"),("/api/pm/status","Process Manager"),
                           ("/api/watch/status","Watch API"),("/api/hive/status","Hive API"),
                           ("/api/tshell/status","TShell API")]:
            cid="route"+path.replace("/",".")
            c=ButtonContract(cid,f"Route: {label} ({path})")
            c.expect(ProofType.ROUTE_REGISTERED,path=path)
            c.expect(ProofType.ROUTE_CALLABLE,path=path)
            self.contracts[c.id]=c
        # ═══ Universal Patch Layer — ALL connected services and APIs ═══
        # Service contracts: every NovaX service + external software
        svc_list=[
            ("cloud_router",9878,"Cloud Router"),("hivemind",9881,"Hivemind"),
            ("nexus",9882,"Nexus"),("sentinel",9884,"Sentinel"),
            ("ternary",9885,"Ternary Server"),("exec_server",9877,"Exec Server"),
            ("closed_loop",9888,"Closed Loop"),("max_patch",9889,"Max Patch"),
            ("redis",6379,"Redis"),("meilisearch",7700,"Meilisearch"),
            ("caddy",8080,"Caddy"),
        ]
        for svc_id,port,label in svc_list:
            c=ButtonContract(f"svc.{svc_id}",f"Service: {label} (:{port})")
            c.expect(ProofType.PORT_OPEN,port=port)
            self.contracts[c.id]=c
        # Cloud API contracts: verify provider health via Cloud Router
        c=ButtonContract("api.cloud_router_health","Cloud Router health check")
        c.expect(ProofType.HTTP_OK,url="http://127.0.0.1:9878/health")
        self.contracts[c.id]=c
        c=ButtonContract("api.max_patch_health","Max Patch health check")
        c.expect(ProofType.HTTP_OK,url="http://127.0.0.1:9889/health")
        self.contracts[c.id]=c
        c=ButtonContract("api.hivemind_health","Hivemind health check")
        c.expect(ProofType.HTTP_OK,url="http://127.0.0.1:9881/health")
        self.contracts[c.id]=c
        log.info("Registered "+str(len(self.contracts))+" contracts (routes + services + APIs)")
    def _load_signatures(self):
        os.makedirs(os.path.dirname(SIGNATURES_PATH),exist_ok=True)
        if os.path.isfile(SIGNATURES_PATH):
            try:
                data=json.load(open(SIGNATURES_PATH,encoding="utf-8"))
                for k,v in data.items():
                    sig=FailureSignature(v["id"],v["symptom"],v.get("conditions"),v.get("root_cause","unknown"),v.get("fix_sequence"))
                    sig.occurrences=v.get("occurrences",0)
                    sig.fixes_attempted=v.get("fixes_attempted",0)
                    sig.fixes_succeeded=v.get("fixes_succeeded",0)
                    self.watchdog.signatures[k]=sig
                log.info("Loaded "+str(len(self.watchdog.signatures))+" signatures")
            except Exception as e:log.error("Signature load failed: "+str(e))
    def _save_signatures(self):
        data={k:v.to_dict() for k,v in self.watchdog.signatures.items()}
        with open(SIGNATURES_PATH,"w",encoding="utf-8") as f:json.dump(data,f,indent=2)
    def register_contract(self,contract):
        self.contracts[contract.id]=contract
    def execute_contract(self,contract_id):
        c=self.contracts.get(contract_id)
        if not c:return {"ok":False,"error":"unknown contract"}
        result=c.execute();self.total_checks+=1
        if not result:self.total_repairs+=1;self.last_repair_ts=time.time()
        return {"ok":result,"contract":c.to_dict()}
    def verify_contract(self,contract_id):
        c=self.contracts.get(contract_id)
        if not c:return {"ok":False,"error":"unknown contract"}
        return {"ok":c.verify_only(),"contract":c.to_dict()}
    def verify_all_contracts(self):
        results={}
        for cid,c in self.contracts.items():
            ok=c.verify_only()
            results[cid]={"ok":ok,"proofs":[p.to_dict() for p in c.proofs]}
        return results
    def start(self,interval=15):
        self.watchdog.start(interval)
        self.running=True
        self.active_watchers=len(self.watchdog.probes)+len(self.contracts)
        log.info("DebugEngine started: "+str(self.active_watchers)+" watchers")
    def stop(self):
        self.watchdog.stop();self.running=False;self._save_signatures()
    def full_diagnosis(self):
        self.watchdog.check_all()
        cr=self.verify_all_contracts()
        risks=self.watchdog.risk_scores()
        su=sum(1 for p in self.watchdog.probes.values() if p.status=="up")
        st=len(self.watchdog.probes)
        cp=sum(1 for r in cr.values() if r["ok"])
        ct=len(cr)
        hr={k:v for k,v in risks.items() if v>0.5}
        health="OK" if su==st and cp==ct else "DEGRADED" if su>0 else "CRITICAL"
        return {"ts":time.time(),"services_up":su,"services_total":st,
                "contracts_pass":cp,"contracts_total":ct,
                "risk_scores":risks,"high_risk":hr,
                "contract_results":cr,"watchdog":self.watchdog.summary(),"health":health}
    def status(self):
        return {"running":self.running,"active_watchers":self.active_watchers,
                "contracts":len(self.contracts),"probes":len(self.watchdog.probes),
                "total_checks":self.total_checks,"total_repairs":self.total_repairs,
                "issues_prevented":self.watchdog.issues_prevented,
                "last_repair":self.last_repair_ts,
                "signatures":len(self.watchdog.signatures)}