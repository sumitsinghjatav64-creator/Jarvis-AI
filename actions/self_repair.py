"""Supervised repair drafts for errors in Mark-LV's own source tree."""
from __future__ import annotations

from core import confirm
from core.self_repair import repair_manager, sanitize_text


def self_repair(parameters: dict, player=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action", "list")).strip().lower()
    incident_id = str(params.get("incident_id", "")).strip()

    if action == "list":
        incidents = repair_manager.list_incidents()
        if not incidents:
            return "No runtime repair incidents have been recorded."
        return "Recent runtime incidents (sanitized):\n" + "\n".join(
            f"{item['id']} | {item['status']} | {item.get('target') or 'no safe source target'} | "
            f"{item['tool_name']}: {item['message'][:180]}"
            for item in incidents
        )

    if action == "repair":
        if not incident_id:
            incidents = repair_manager.list_incidents(limit=1)
            if not incidents:
                return "There is no recorded runtime error to repair."
            incident_id = incidents[0]["id"]
        if confirm.pending_title():
            return "A confirmation is already waiting on the HUD. Resolve it before requesting a repair."
        try:
            staged = repair_manager.draft_repair(incident_id)
        except Exception as exc:
            return f"Could not draft a safe repair: {sanitize_text(str(exc))[:400]}"

        diff = staged["diff"]
        if player and hasattr(player, "show_content"):
            player.show_content(f"REPAIR DRAFT — {staged['target']}", diff)
        detail = (
            f"Target: {staged['target']}\nIncident: {incident_id}\n\n"
            "The candidate is staged separately and passed a Python syntax check. "
            "Behavioral tests were not run automatically. Applying writes a local backup; "
            "restart JARVIS and verify the fix.\n\n"
            f"Patch preview:\n{diff[:4500]}"
            f"{'\n… (preview truncated; full diff is in the repair preview)' if len(diff) > 4500 else ''}"
        )
        return confirm.request(
            key=f"self-repair-{incident_id}",
            title=f"Apply staged repair to {staged['target']}?",
            detail=detail,
            run=lambda iid=incident_id: _apply(iid),
        )

    if action == "apply":
        if not incident_id:
            return "Specify the incident_id for the staged repair."
        incident = repair_manager.get_incident(incident_id)
        if not incident or incident.get("status") != "staged":
            return "That incident has no staged repair to apply."
        if confirm.pending_title():
            return "A confirmation is already waiting on the HUD. Resolve it before requesting another repair."
        diff = incident.get("diff") or ""
        detail = (
            f"Target: {incident['target']}\nIncident: {incident_id}\n\n"
            "This candidate passed syntax checking only; behavioral tests were not run. "
            "Applying writes a backup and requires a JARVIS restart.\n\n"
            f"Patch preview:\n{diff[:4500]}"
        )
        return confirm.request(
            key=f"self-repair-{incident_id}",
            title=f"Apply staged repair to {incident['target']}?",
            detail=detail,
            run=lambda iid=incident_id: _apply(iid),
        )

    if action == "rollback":
        if not incident_id:
            return "Specify the incident_id for the repair to roll back."
        incident = repair_manager.get_incident(incident_id)
        if not incident or incident.get("status") != "applied":
            return "That incident has no applied repair to roll back."
        if confirm.pending_title():
            return "A confirmation is already waiting on the HUD. Resolve it before requesting rollback."
        return confirm.request(
            key=f"self-repair-rollback-{incident_id}",
            title=f"Roll back repair to {incident['target']}?",
            detail=(
                f"Restore the saved pre-repair version of {incident['target']}?\n"
                "Rollback is refused if the file has changed since the repair was applied."
            ),
            run=lambda iid=incident_id: _rollback(iid),
        )

    return "Unknown action. Use list, repair, apply, or rollback."


def _rollback(incident_id: str) -> str:
    result = repair_manager.rollback_repair(incident_id)
    if result["status"] == "conflict":
        return result["message"]
    return f"Restored {result['target']} from the saved pre-repair backup. Restart JARVIS and verify."


def _apply(incident_id: str) -> str:
    result = repair_manager.apply_repair(incident_id)
    if result["status"] == "conflict":
        return result["message"]
    return (
        f"Repair applied to {result['target']}. Backup saved locally at {result['backup']}. "
        "Restart JARVIS and verify the behavior; ask me to roll it back if it fails."
    )


TOOL = {
    "name": "self_repair",
    "description": (
        "Lists sanitized runtime incidents, drafts a repair for the latest or selected incident, "
        "and stages it. Applying or rolling back source requires explicit HUD confirmation. "
        "Draft generation sends the affected source and sanitized traceback to Gemini. "
        "Candidates get a Python syntax check only; behavioral tests must be run separately."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "list | repair | rollback"},
            "incident_id": {"type": "STRING", "description": "Optional incident ID; repair defaults to the latest"},
        },
        "required": ["action"],
    },
    "handler": self_repair,
}
