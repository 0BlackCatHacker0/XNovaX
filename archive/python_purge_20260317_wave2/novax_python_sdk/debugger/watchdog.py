"""NovaX Watchdog - Process monitor, API contract monitor, drift detector."""
import time,socket,subprocess,os,threading,json,logging,hashlib
from collections import deque

log=logging.getLogger("NovaX.Debugger.Watchdog")

class ServiceProbe:
    def __init__(self,name,port,health_url=None,process_name=None):
        self.name=name;self.port=port;self.health_url=health_url;self.process_name=process_name
        self.status="unknown";self.latency_history=deque(maxlen=60)
        self.fail_count=0;self.restart_count=0;self.last_check=None;self.last_up=None;self.consecutive_fails=0
    def check(self):
        self.last_check=time.time()
        s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.settimeout(2)
        t0=time.time()
        try:
            s.connect(("127.0.0.1",self.port));s.close()
            self.latency_history.append((time.time()-t0)*1000)
        except:
            self.status="down";self.fail_count+=1;self.consecutive_fails+=1;return False
        if self.health_url:
            try:
                import urllib.request
                t1=time.time();r=urllib.request.urlopen(self.health_url,timeout=3)
                self.latency_history.append((time.time()-t1)*1000)
                if r.getcode()!=200:self.status="degraded";self.consecutive_fails+=1;return False
            except:self.status="degraded";self.consecutive_fails+=1;return False
        self.status="up";self.last_up=time.time();self.consecutive_fails=0;return True
    def avg_latency(self):
        if not self.latency_history:return 0
        return round(sum(self.latency_history)/len(self.latency_history),1)
    def latency_trend(self):
        h=list(self.latency_history)
        if len(h)<10:return "stable"
        fh=sum(h[:len(h)//2])/(len(h)//2);sh=sum(h[len(h)//2:])/(len(h)-len(h)//2)
        if sh>fh*(H3/2):return "rising"    # 3/2 = 1.5 (already harmonic!)
        if sh<fh*(1/2):return "falling"
        return "stable"
    def to_dict(self):
        return {"name":self.name,"port":self.port,"status":self.status,
                "avg_latency_ms":self.avg_latency(),"latency_trend":self.latency_trend(),
                "fail_count":self.fail_count,"consecutive_fails":self.consecutive_fails,
                "restart_count":self.restart_count,"last_check":self.last_check,"last_up":self.last_up}

class FailureSignature:
    def __init__(self,sig_id,symptom,conditions=None,root_cause="unknown",fix_sequence=None):
        self.id=sig_id;self.symptom=symptom;self.conditions=conditions or []
        self.root_cause=root_cause;self.fix_sequence=fix_sequence or []
        self.occurrences=0;self.fixes_attempted=0;self.fixes_succeeded=0;self.created_at=time.time()
    @property
    def success_rate(self):
        if self.fixes_attempted==0:return 0.0
        return round(self.fixes_succeeded/self.fixes_attempted,3)
    def to_dict(self):
        return {"id":self.id,"symptom":self.symptom,"conditions":self.conditions,
                "root_cause":self.root_cause,"fix_sequence":self.fix_sequence,
                "occurrences":self.occurrences,"success_rate":self.success_rate}

H3,H5,H7,H13=3,5,7,13  # 3-5-7-13 harmonic constants

class DriftSignal:
    def __init__(self,name,threshold=2.0/3):  # 2/H3 harmonic
        self.name=name;self.values=deque(maxlen=100);self.threshold=threshold;self.triggered=False
    def record(self,value):
        self.values.append({"v":value,"ts":time.time()});self._evaluate()
    def _evaluate(self):
        if len(self.values)<10:self.triggered=False;return
        recent=[x["v"] for x in list(self.values)[-10:]]
        older=[x["v"] for x in list(self.values)[:-10]]
        if not older:return
        ar=sum(recent)/len(recent);ao=sum(older)/len(older)
        if ao>0:self.triggered=abs(ar-ao)/ao>self.threshold
    def to_dict(self):
        return {"name":self.name,"triggered":self.triggered,"samples":len(self.values)}

class FileVerifier:
    def __init__(self):
        self.verified=0;self.failed=0;self.history=deque(maxlen=50)
    def verify_write(self,path,expected_content):
        try:
            eh=hashlib.sha256(expected_content.encode()).hexdigest()[:16]
            actual=open(path,"r",encoding="utf-8").read()
            ah=hashlib.sha256(actual.encode()).hexdigest()[:16]
            m=eh==ah
            if m:self.verified+=1
            else:self.failed+=1
            self.history.append({"path":path,"match":m,"ts":time.time()});return m
        except Exception as e:
            self.failed+=1;self.history.append({"path":path,"match":False,"error":str(e),"ts":time.time()});return False
    def to_dict(self):
        return {"verified":self.verified,"failed":self.failed,"recent":list(self.history)[-10:]}

class Watchdog:
    def __init__(self):
        self.probes={};self.signatures={};self.drifts={}
        self.file_verifier=FileVerifier()
        self.incidents=deque(maxlen=200)
        self.repairs_performed=0;self.issues_prevented=0
        self.running=False;self._thread=None;self._lock=threading.Lock()
        self._register_defaults()
    def _register_defaults(self):
        self.add_probe(ServiceProbe("bridge",9999,"http://127.0.0.1:9999/api/status"))
        self.add_probe(ServiceProbe("brain",9990,"http://127.0.0.1:9990/health"))
        self.add_probe(ServiceProbe("websocket",9998))
        self.add_probe(ServiceProbe("ollama",11434,"http://127.0.0.1:11434/api/tags"))
        self.add_probe(ServiceProbe("qbittorrent",8080))
        self.add_probe(ServiceProbe("kodi",8081))
        self.drifts["bridge_latency"]=DriftSignal("bridge_latency",1.0/H3)
        self.drifts["brain_latency"]=DriftSignal("brain_latency",1.0/H3)
        self.drifts["fail_rate"]=DriftSignal("fail_rate",1.0/H5)
    def add_probe(self,probe):
        self.probes[probe.name]=probe
    def add_signature(self,sig):
        self.signatures[sig.id]=sig
    def check_all(self):
        results={};total_fails=0
        for name,probe in self.probes.items():
            ok=probe.check();results[name]=probe.status
            if not ok:
                total_fails+=1
                self._record_incident(name,probe.status,name+" on :"+str(probe.port)+" is "+probe.status)
            if name=="bridge" and probe.latency_history:
                self.drifts["bridge_latency"].record(probe.avg_latency())
            if name=="brain" and probe.latency_history:
                self.drifts["brain_latency"].record(probe.avg_latency())
        if self.probes:self.drifts["fail_rate"].record(total_fails/len(self.probes))
        return results
    def _record_incident(self,source,severity,message):
        self.incidents.append({"source":source,"severity":severity,"message":message,"ts":time.time()})
    def attempt_repair(self,service_name):
        probe=self.probes.get(service_name)
        if not probe:return {"ok":False,"error":"unknown service"}
        repair_cmds={"bridge":"cd /d C:/NovaX && start /B python nova_bridge_v3.py",
                     "brain":"cd /d C:/NovaX && start /B python -m novax.brain",
                     "ollama":"start /B ollama serve"}
        cmd=repair_cmds.get(service_name)
        if cmd:
            try:
                subprocess.Popen(cmd,shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                probe.restart_count+=1;self.repairs_performed+=1
                self._record_incident(service_name,"repair","Attempted restart of "+service_name)
                time.sleep(2)
                if probe.check():self.issues_prevented+=1;return {"ok":True,"status":"repaired"}
                return {"ok":False,"status":"repair_failed"}
            except Exception as e:return {"ok":False,"error":str(e)}
        return {"ok":False,"error":"no repair command for "+service_name}
    def risk_scores(self):
        scores={}
        for name,probe in self.probes.items():
            risk=0.0
            if probe.consecutive_fails>0:risk+=min(probe.consecutive_fails*(1.0/H5),2.0/H3)
            if probe.latency_trend()=="rising":risk+=1.0/H3
            if probe.fail_count>H5:risk+=1.0/H7
            dk=name+"_latency"
            if dk in self.drifts and self.drifts[dk].triggered:risk+=1.0/H3
            scores[name]=round(min(risk,1.0),2)
        return scores
    def start(self,interval=15):
        if self.running:return
        self.running=True
        def loop():
            while self.running:
                self.check_all()
                for name,probe in self.probes.items():
                    if probe.consecutive_fails>=3 and probe.status=="down":
                        log.warning("Watchdog: "+name+" down, attempting repair")
                        self.attempt_repair(name)
                time.sleep(interval)
        self._thread=threading.Thread(target=loop,daemon=True)
        self._thread.start();log.info("Watchdog: Continuous monitoring started")
    def stop(self):
        self.running=False
    def summary(self):
        return {"services":{n:p.to_dict() for n,p in self.probes.items()},
                "risk_scores":self.risk_scores(),
                "drift_signals":{n:d.to_dict() for n,d in self.drifts.items()},
                "incidents":list(self.incidents)[-20:],
                "repairs_performed":self.repairs_performed,
                "issues_prevented":self.issues_prevented,
                "file_verifier":self.file_verifier.to_dict(),
                "signatures":{k:v.to_dict() for k,v in self.signatures.items()},
                "running":self.running}