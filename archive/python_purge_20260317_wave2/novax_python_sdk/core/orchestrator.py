"""Job orchestrator - receives intents, creates jobs, drives execution."""
import time
from ..objects import Job, Intent, Status, Receipt
from ..events.bus import bus, JOB_CREATED, JOB_COMPLETED, JOB_FAILED

class Orchestrator:
    def __init__(self):
        self.jobs = {}
        self.queue = []

    def submit(self, intent: Intent) -> Job:
        job = Job(intent=intent, status=Status.PENDING)
        self.jobs[job.id] = job
        self.queue.append(job.id)
        bus.emit(JOB_CREATED, {"job_id": job.id, "action": intent.action})
        return job

    def run_next(self) -> Receipt:
        if not self.queue:
            return Receipt(success=False, output="no jobs queued")
        jid = self.queue.pop(0)
        job = self.jobs[jid]
        job.status = Status.RUNNING
        job.started = time.time()
        try:
            job.result = f"executed: {job.intent.action}"
            job.status = Status.DONE
            job.finished = time.time()
            bus.emit(JOB_COMPLETED, {"job_id": jid})
            return Receipt(job_id=jid, success=True, output=str(job.result),
                         duration=job.finished - job.started)
        except Exception as e:
            job.status = Status.FAILED
            job.error = str(e)
            job.finished = time.time()
            bus.emit(JOB_FAILED, {"job_id": jid, "error": str(e)})
            return Receipt(job_id=jid, success=False, output=str(e))

    def get(self, jid): return self.jobs.get(jid)
    def active(self): return [j for j in self.jobs.values() if j.status in (Status.PENDING, Status.RUNNING)]
    def history(self, n=20):
        done = [j for j in self.jobs.values() if j.status in (Status.DONE, Status.FAILED)]
        return sorted(done, key=lambda j: j.finished, reverse=True)[:n]
    def cancel(self, jid):
        if jid in self.jobs and self.jobs[jid].status == Status.PENDING:
            self.jobs[jid].status = Status.CANCELLED
            if jid in self.queue: self.queue.remove(jid)
            return True
        return False
