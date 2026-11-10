"""Stable draft identity. Keep migration identical to bot/draft_ids.py."""
import re


def ensure_draft_ids(state: dict) -> bool:
    drafts = state.get("drafts", [])
    used = set()
    next_id = max(1, int(state.get("next_draft_id", 1)))
    for draft in drafts:
        identity = draft.get("id")
        if identity is None:
            continue
        if not isinstance(identity, str) or not identity or identity in used:
            raise ValueError("Invalid or duplicate draft identity")
        used.add(identity)
        match = re.fullmatch(r"draft-([0-9]+)", identity)
        if match:
            next_id = max(next_id, int(match[1]) + 1)
    changed = False
    for draft in drafts:
        if draft.get("id") is None:
            identity = f"draft-{next_id}"
            next_id += 1
            draft["id"] = identity
            used.add(identity)
            changed = True
    if state.get("next_draft_id") != next_id:
        state["next_draft_id"] = next_id
        changed = True
    return changed


def pending_draft(state: dict, identity: str) -> dict:
    if not isinstance(identity, str) or not identity:
        raise ValueError("Draft ID is required")
    matches = [d for d in state.get("drafts", []) if d.get("id") == identity]
    if len(matches) != 1 or matches[0].get("published") or matches[0].get("rejected"):
        raise ValueError("Unknown or stale draft ID")
    return matches[0]
