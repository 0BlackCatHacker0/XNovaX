"""Explain layer - translate system events into human language."""

class Explainer:
    def __init__(self):
        self.templates = {
            "service.crashed": "{service} went down: {error}",
            "recovery.performed": "{service} was automatically restarted",
            "job.completed": "Task {job_id} finished successfully",
            "job.failed": "Task {job_id} failed: {error}",
            "policy.denied": "Action blocked (risk: {risk}): {intent}",
        }

    def explain(self, event, data):
        tmpl = self.templates.get(event, f"{event}: {data}")
        try: return tmpl.format(**data)
        except: return f"{event}: {data}"

    def summarize_incidents(self, incidents):
        if not incidents: return "No incidents recorded."
        return f"{len(incidents)} incidents. Latest: {incidents[-1].error}"
