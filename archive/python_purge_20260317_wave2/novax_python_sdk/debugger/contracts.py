"""NovaX Button Proof Contract System"""
import time,socket,subprocess,os,hashlib,json,threading,logging
from enum import Enum

log=logging.getLogger("NovaX.Debugger.Contracts")

class ProofType(Enum):
    PORT_OPEN="port_open";HTTP_OK="http_ok";PROCESS_RUNNING="process_running"
    FILE_EXISTS="file_exists";FILE_CONTAINS="file_contains";FILE_CHECKSUM="file_checksum"
    COMMAND_OUTPUT="command_output";SERVICE_REGISTERED="service_registered"
    ROUTE_REGISTERED="route_registered";ROUTE_CALLABLE="route_callable"

class ProofResult(Enum):
    PASS="pass";FAIL="fail";TIMEOUT="timeout";ERROR="error"

class EffectProof:
    def __init__(self,proof_type,**kwargs):
        self.type=proof_type if isinstance(proof_type,ProofType) else ProofType(proof_type)
        self.params=kwargs;self.result=None;self.detail="";self.checked_at=None
    def verify(self):
        self.checked_at=time.time()
        try:
            m={"port_open":self._port,"http_ok":self._http,"process_running":self._proc,
               "file_exists":self._fexist,"file_contains":self._fcontain,"file_checksum":self._fcheck,
               "command_output":self._cmd,"route_registered":self._route_reg,"route_callable":self._route_call}
            fn=m.get(self.type.value)
            if fn:return fn()
            self.result=ProofResult.ERROR;self.detail="unknown type";return False
        except Exception as e:
            self.result=ProofResult.ERROR;self.detail=str(e);return False
    def _port(self):
        port=self.params.get("port",0);host=self.params.get("host","127.0.0.1")
        s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.settimeout(2)
        try:
            s.connect((host,port));s.close()
            self.result=ProofResult.PASS;self.detail="port "+str(port)+" open";return True
        except:
            self.result=ProofResult.FAIL;self.detail="port "+str(port)+" closed";return False
    def _http(self):
        import urllib.request
        url=self.params.get("url","");t=self.params.get("timeout",3)
        try:
            r=urllib.request.urlopen(url,timeout=t);c=r.getcode()
            if c==200:self.result=ProofResult.PASS;self.detail=url+" ok";return True
            self.result=ProofResult.FAIL;self.detail=url+" "+str(c);return False
        except Exception as e:
            self.result=ProofResult.FAIL;self.detail=url+" err";return False
    def _proc(self):
        name=self.params.get("name","")
        try:
            cmd="tasklist /FI " + chr(34) + "IMAGENAME eq "+name+chr(34)+" /NH"
            r=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=5)
            found=name.lower() in r.stdout.lower()
            self.result=ProofResult.PASS if found else ProofResult.FAIL
            self.detail=name+(" running" if found else " not found");return found
        except:self.result=ProofResult.ERROR;return False
    def _fexist(self):
        path=self.params.get("path","");e=os.path.isfile(path)
        self.result=ProofResult.PASS if e else ProofResult.FAIL
        self.detail=path+(" exists" if e else " missing");return e
    def _fcontain(self):
        path=self.params.get("path","");tok=self.params.get("token","")
        if not os.path.isfile(path):self.result=ProofResult.FAIL;self.detail=path+" missing";return False
        c=open(path,"r",encoding="utf-8",errors="replace").read()
        found=tok in c;self.result=ProofResult.PASS if found else ProofResult.FAIL
        self.detail="token "+tok[:30]+(" found" if found else " not found");return found
    def _fcheck(self):
        path=self.params.get("path","");exp=self.params.get("checksum","")
        if not os.path.isfile(path):self.result=ProofResult.FAIL;return False
        actual=hashlib.sha256(open(path,"rb").read()).hexdigest()[:16]
        m=actual==exp;self.result=ProofResult.PASS if m else ProofResult.FAIL
        self.detail="hash "+actual+(" == " if m else " != ")+exp;return m
    def _cmd(self):
        cmd=self.params.get("command","");exp=self.params.get("expect","")
        try:
            r=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=10)
            found=exp.lower() in (r.stdout+r.stderr).lower()
            self.result=ProofResult.PASS if found else ProofResult.FAIL
            self.detail=exp[:30]+(" found" if found else " missing");return found
        except:self.result=ProofResult.TIMEOUT;return False
    def _route_reg(self):
        """Verify a route is registered in the route validator manifest."""
        path=self.params.get("path","")
        try:
            import sys
            if r"C:\NovaX\core" not in sys.path: sys.path.insert(0, r"C:\NovaX\core")
            from route_validator import get_validator
            rv=get_validator()
            route=rv.get_route_status(path)
            if route:
                self.result=ProofResult.PASS;self.detail=path+" registered";return True
            self.result=ProofResult.FAIL;self.detail=path+" not in manifest";return False
        except Exception as e:
            self.result=ProofResult.ERROR;self.detail=str(e);return False
    def _route_call(self):
        """Verify a route is callable (not returning 404 from catch-all)."""
        path=self.params.get("path","")
        try:
            import sys
            if r"C:\NovaX\core" not in sys.path: sys.path.insert(0, r"C:\NovaX\core")
            from route_validator import get_validator
            rv=get_validator()
            route=rv.get_route_status(path)
            if not route:
                self.result=ProofResult.FAIL;self.detail=path+" not in manifest";return False
            status=route.get("status","UNKNOWN")
            if status=="ALIVE":
                self.result=ProofResult.PASS;self.detail=path+" ALIVE";return True
            self.result=ProofResult.FAIL;self.detail=path+" "+status;return False
        except Exception as e:
            self.result=ProofResult.ERROR;self.detail=str(e);return False
    def to_dict(self):
        return {"type":self.type.value,"params":self.params,
                "result":self.result.value if self.result else None,
                "detail":self.detail,"checked_at":self.checked_at}

class RepairAction:
    def __init__(self,name,command=None,action_fn=None):
        self.name=name;self.command=command;self.action_fn=action_fn
        self.executed=False;self.success=None
    def execute(self):
        self.executed=True
        try:
            if self.command:
                r=subprocess.run(self.command,shell=True,capture_output=True,text=True,timeout=15)
                self.success=r.returncode==0;return self.success
            elif self.action_fn:
                self.success=bool(self.action_fn());return self.success
        except Exception as e:
            log.error("Repair "+self.name+" failed: "+str(e));self.success=False;return False
    def to_dict(self):
        return {"name":self.name,"command":self.command,"executed":self.executed,"success":self.success}

class ButtonContract:
    def __init__(self,cid,description="",action_cmd=None,action_url=None,action_method="POST"):
        self.id=cid;self.description=description
        self.action_cmd=action_cmd;self.action_url=action_url;self.action_method=action_method
        self.proofs=[];self.repairs=[]
        self.retry_attempts=3;self.retry_interval=1.0
        self.history=[];self.created_at=time.time()
    def expect(self,proof_type,**kwargs):
        self.proofs.append(EffectProof(proof_type,**kwargs));return self
    def repair_with(self,name,command=None,action_fn=None):
        self.repairs.append(RepairAction(name,command,action_fn));return self
    def execute(self):
        record={"id":self.id,"ts":time.time(),"attempts":[],"final":"unknown"}
        self._fire_action();record["action_fired"]=True
        for attempt in range(self.retry_attempts):
            time.sleep(self.retry_interval if attempt>0 else 0.5)
            results=self._verify_all();ap=all(results)
            record["attempts"].append({"n":attempt+1,"proofs":[p.to_dict() for p in self.proofs],"all_pass":ap})
            if ap:
                record["final"]="SUCCESS";self.history.append(record)
                log.info("Contract "+self.id+": SUCCESS");return True
            if attempt<self.retry_attempts-1 and self.repairs:
                ri=min(attempt,len(self.repairs)-1);repair=self.repairs[ri]
                log.warning("Contract "+self.id+": repair: "+repair.name)
                repair.execute();record["attempts"][-1]["repair"]=repair.to_dict()
        record["final"]="FAILED";self.history.append(record)
        log.error("Contract "+self.id+": FAILED");return False
    def verify_only(self):
        return all(self._verify_all())
    def _fire_action(self):
        try:
            if self.action_cmd:
                subprocess.Popen(self.action_cmd,shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);return True
            if self.action_url:
                import urllib.request
                urllib.request.urlopen(urllib.request.Request(self.action_url,method=self.action_method),timeout=5);return True
        except:pass
        return False
    def _verify_all(self):
        return [p.verify() for p in self.proofs]
    def success_rate(self):
        if not self.history:return 0.0
        ok=sum(1 for h in self.history if h["final"]=="SUCCESS")
        return round(ok/len(self.history),3)
    def to_dict(self):
        return {"id":self.id,"description":self.description,
                "proofs":[p.to_dict() for p in self.proofs],
                "repairs":[r.to_dict() for r in self.repairs],
                "retry_attempts":self.retry_attempts,
                "success_rate":self.success_rate(),
                "history_count":len(self.history),
                "last_result":self.history[-1]["final"] if self.history else "never_run"}