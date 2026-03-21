import socket, json, time, datetime, os
CONFIG = r"C:\NovaX\config\servers\recovery\recovery_commands.json"
LOG_DIR = r"C:\NovaX\config\servers\logs"
REPORT = r"C:\NovaX\config\servers\health\health_report.json"

def check_port(port):
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.settimeout(2)
    try: s.connect(("127.0.0.1",port)); return True
    except: return False
    finally: s.close()

def log_event(svc,evt,det=""):
    ts=datetime.datetime.now().isoformat()
    entry=f"[{ts}] [{svc}] {evt} {det}"
    with open(os.path.join(LOG_DIR,"supervisor.log"),"a") as lf: lf.write(entry+"\n")
    print(entry)

def run():
    with open(CONFIG) as f: svcs=json.load(f)
    results=[]
    for name,cfg in svcs.items():
        port=cfg["port"]
        alive=check_port(port)
        st="UP" if alive else "DOWN"
        results.append({"name":name,"port":port,"status":st})
        if not alive:
            log_event(name,"DOWN",f"port {port}")
            for i in range(1,4):
                log_event(name,f"RETRY {i}/3","wait 5s")
                time.sleep(5)
                if check_port(port):
                    log_event(name,"RECOVERED"); results[-1]["status"]="UP"; break
            else: log_event(name,"CRASH",f"port {port} 3x fail")
    rpt={"timestamp":datetime.datetime.now().isoformat(),"services":results,"up":sum(1 for r in results if r["status"]=="UP"),"down":sum(1 for r in results if r["status"]=="DOWN")}
    with open(REPORT,"w") as rf: json.dump(rpt,rf,indent=2)
    print(f"Health: {rpt['up']}/{len(results)} UP")
    return rpt

if __name__=="__main__": run()
