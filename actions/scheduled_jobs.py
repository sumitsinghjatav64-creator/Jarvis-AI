"""Create, inspect, cancel and explicitly retry durable assistant jobs."""
from __future__ import annotations

from datetime import datetime

from core.job_store import job_store


def _render_job(job: dict) -> str:
    due = datetime.fromtimestamp(job["due_at"]).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return f"{job['id']} | {job['status']} | {due} | {job['prompt'][:180]}"


def scheduled_job(parameters: dict, player=None) -> str:
    """Manage one-shot scheduled assistant tasks with restart-safe checkpoints."""
    params = parameters or {}
    action = str(params.get("action", "list")).strip().lower()
    job_id = str(params.get("job_id", "")).strip()

    if action == "schedule":
        raw = str(params.get("run_at", "")).strip()
        try:
            run_at = datetime.fromisoformat(raw)
            if run_at.tzinfo is None:
                run_at = run_at.astimezone()
            job = job_store.create(str(params.get("prompt", "")), run_at.timestamp())
        except (TypeError, ValueError, OverflowError) as exc:
            return f"Could not schedule the task: {exc}"
        return f"Scheduled task {job['id']} for {_render_job(job).split(' | ')[2]}. It will run once Mark-LV is online."

    if action == "list":
        jobs = job_store.list()
        return "No scheduled assistant tasks." if not jobs else "Scheduled assistant tasks:\n" + "\n".join(
            _render_job(job) for job in jobs
        )

    if not job_id:
        return "A job_id is required for this action."
    job = job_store.get(job_id)
    if job is None:
        return f"No scheduled task found with ID {job_id}."

    if action == "cancel":
        status = job_store.cancel(job_id)
        if status == "cancelled":
            return f"Cancelled scheduled task {job_id}."
        if status == "running":
            return "That task is already running and cannot be cancelled mid-action."
        return f"Task {job_id} is {status}; it was not cancelled."

    if action == "retry":
        if job["status"] not in {"failed", "needs_review"}:
            return f"Task {job_id} is {job['status']}; only failed or interrupted tasks can be retried."
        if player and hasattr(player, "request_say"):
            player.request_say(
                f"A confirmation for retrying scheduled task {job_id} is on the HUD. "
                "Wait for the user to approve or cancel; do not call retry again."
            )
        from core import confirm
        detail = (
            f"Retry task {job_id}: {job['prompt'][:180]}\n\n"
            "An earlier run may already have performed an external action. Retrying can repeat it."
        )
        result = confirm.request(
            key=f"retry-job-{job_id}",
            title=f"Retry scheduled task {job_id}",
            detail=detail,
            run=lambda: _retry_job(job_id, player),
        )
        return result

    if action in {"complete", "fail"}:
        if job["status"] != "running":
            return f"Task {job_id} is not running; completion report ignored."
        result = str(params.get("result", ""))[:5000]
        ok = job_store.finish(job_id, result, failed=action == "fail")
        return f"Task {job_id} marked {('failed' if action == 'fail' else 'completed')}." if ok else "Task state changed; report ignored."

    return "Unknown action. Use schedule, list, cancel, retry, complete, or fail."


def _retry_job(job_id: str, player=None) -> str:
    status = job_store.retry_if_reviewed(job_id)
    if status == "pending":
        if player and hasattr(player, "request_say"):
            player.request_say(
                f"The user approved retrying scheduled task {job_id}. "
                "It is now queued; run it when Mark-LV is ready."
            )
        return f"Task {job_id} queued for retry."
    return f"Task {job_id} could not be retried because its current status is {status}."


TOOL = {
    "name": "scheduled_job",
    "description": (
        "Schedules a one-time assistant task for a future local date and time, lists or cancels tasks, "
        "and reports completion for a task explicitly sent to you by the background scheduler. "
        "Interrupted/failed tasks are never replayed automatically; retry requires the user's on-screen approval. "
        "When a scheduled task finishes, call action='complete' with its job_id and a concise result; "
        "if it cannot be completed, call action='fail'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "schedule | list | cancel | retry | complete | fail"},
            "run_at": {"type": "STRING", "description": "Local ISO date/time, YYYY-MM-DDTHH:MM (or an ISO timestamp with timezone)"},
            "prompt": {"type": "STRING", "description": "The user-requested task to perform once Mark-LV is online"},
            "job_id": {"type": "STRING", "description": "Job ID for list/cancel/retry/complete/fail"},
            "result": {"type": "STRING", "description": "Short completion or failure report"},
        },
        "required": ["action"],
    },
    "handler": scheduled_job,
}