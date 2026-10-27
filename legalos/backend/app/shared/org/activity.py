"""Recent activity feed built from the audit log (real events only), phrased for a business owner."""
from typing import Optional

from app.shared.db.models import AuditEvent

# action -> (sentence template, link template). {x} placeholders come from event.meta.
_TEXT = {
    "contract.uploaded": ("Uploaded the contract “{filename}”", "/contracts/{id}"),
    "contract.analyzed": ("Finished reviewing a contract (risk score {score})", "/contracts/{id}"),
    "contract.analysis_failed": ("A contract review could not finish", "/contracts/{id}"),
    "contract.question_asked": ("Asked a question about a contract", "/contracts/{id}"),
    "contract.deleted": ("Deleted a contract", None),
    "vendor.checked": ("Checked a supplier ({risk} risk)", "/vendors/{id}"),
    "vendor.rechecked": ("Re-checked a supplier ({risk} risk)", "/vendors/{id}"),
    "vendor.deleted": ("Removed a supplier", None),
    "notice.created": ("Added a legal notice", "/notices/{id}"),
    "notice.analyzed": ("Read a notice: {type}, urgency {urgency}", "/notices/{id}"),
    "notice.draft_regenerated": ("Redrafted a notice reply", "/notices/{id}"),
    "notice.draft_edited": ("Edited a notice reply", "/notices/{id}"),
    "notice.updated": ("Updated a notice", "/notices/{id}"),
    "notice.deleted": ("Deleted a notice", None),
    "document.uploaded": ("Added the document “{filename}”", "/documents/{id}"),
    "document.reviewed": ("Reviewed a document ({concerns} point(s) to check)", "/documents/{id}"),
    "document.deleted": ("Deleted a document", None),
    "compliance.task_created": ("Added a reminder: {title}", "/compliance"),
    "compliance.task_updated": ("Updated a compliance item", "/compliance"),
    "compliance.bulk_completed": ("Marked {count} earlier filings as already filed", "/compliance"),
    "compliance.synced": ("Refreshed the compliance calendar", "/compliance"),
    "org.updated": ("Updated the company profile", "/settings"),
    "account.registered": ("Created the account", None),
}


class _Safe(dict):
    def __missing__(self, key):
        return "?"


def describe(ev: AuditEvent) -> Optional[dict]:
    spec = _TEXT.get(ev.action)
    if spec is None:
        return None
    text, link = spec
    meta = _Safe({**(ev.meta or {}), "id": ev.entity_id or ""})
    try:
        text = text.format_map(meta)
        link = link.format_map(meta) if link and ev.entity_id else (link if link and "{id}" not in link else None)
    except Exception:
        return None
    return {"id": ev.id, "action": ev.action, "text": text, "link": link, "created_at": ev.created_at}
