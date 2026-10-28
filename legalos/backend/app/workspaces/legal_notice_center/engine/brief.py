"""One-page lawyer handoff, built only from what is already stored on the case (no AI call).

A lawyer should be able to read it in two minutes and know: what arrived, from whom, the dates and amounts, what the
deadline rests on, what we drafted, and what is still open. Unverified items are labelled as such, never smoothed over.
"""
from datetime import date
from typing import List, Optional


def _d(value) -> Optional[str]:
    if isinstance(value, date):
        return value.strftime("%d %b %Y").lstrip("0")
    return str(value) if value else None


def _inr(amount: Optional[float]) -> Optional[str]:
    """Indian digit grouping: 240000 -> Rs 2,40,000."""
    if amount is None:
        return None
    s = f"{int(round(amount))}"
    head, parts = s[:-3], [s[-3:]]
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return "Rs " + ",".join(([head] if head else []) + parts)


def _flagged(value, ok: bool, warning: str) -> Optional[str]:
    text = _d(value)
    return text and (text if ok else f"{text} ({warning})")


def _line(label: str, value) -> Optional[str]:
    return f"{label}: {value}" if value not in (None, "", []) else None


def build_lawyer_brief(d: dict, company: Optional[str] = None) -> str:
    """`d` is the case detail dict (service.to_detail before the brief is attached)."""
    info = d.get("type_info") or {}
    latest = (d.get("drafts") or [None])[0]
    out: List[Optional[str]] = [f"LAWYER BRIEF - {d.get('title') or 'Notice'}", ""]

    out += ["1. THE NOTICE",
            _line("Type", d.get("type_label")),
            _line("Client", company or d.get("addressed_to")),
            _line("From", ", ".join(x for x in (d.get("issuer_name"), d.get("issuer_role")) if x)),
            _line("Reference", d.get("reference_number")),
            _line("Notice dated", _flagged(d.get("notice_date"), d.get("notice_date_verified", True), "not found in the text - check")),
            _line("Received", _flagged(d.get("received_date"), d.get("received_confirmed", False), "assumed - client to confirm")),
            _line("Amount claimed", _inr(d.get("amount_claimed"))),
            _line("Sections cited", "; ".join(d.get("statutes") or [])),
            _line("Read by OCR", "yes - check figures against the original" if d.get("ocr_used") else None),
            ""]

    deadline = _d(d.get("response_deadline"))
    out += ["2. DEADLINE",
            (f"{deadline} ({'verified against the notice' if d.get('deadline_verified') else 'NOT verified - check'})" if deadline
             else "No deadline could be fixed."),
            d.get("deadline_note")]
    out += [f"- {_d(c.get('due'))}: {c.get('explanation')}{'' if c.get('verified') else ' [unverified]'}" for c in d.get("deadline_basis") or []]
    out.append("")

    out += ["3. WHAT THEY ALLEGE AND DEMAND"]
    out += [f"- {a}" for a in d.get("allegations") or []]
    out += [f"- Demand: {x}" for x in d.get("demands") or []]
    out += [f'- "{q["text"]}" [{q["kind"]}, {"verified" if q["verified"] else "UNVERIFIED"}]' for q in d.get("key_quotes") or []]
    out.append("")

    out += ["4. LAW (reference table, decision support)",
            _line("Governing provisions", info.get("ref")),
            _line("If ignored", info.get("if_ignored")),
            _line("Response route", info.get("channel")),
            _line("Status of this note", None if info.get("verified", True) else f"being verified - {info.get('verify_note') or ''}".strip(" -")),
            ""]

    out += ["5. WHAT WE DRAFTED"]
    if latest:
        kind = "Action plan" if d.get("draft_kind") == "action_plan" else "Reply letter"
        out.append(f"{kind}, version {latest.get('version')} ({'edited by the client' if latest.get('author') == 'user' else 'AI first draft'}); "
                   f"review status: {d.get('review_status', 'draft').replace('_', ' ')}.")
    else:
        out.append("No draft yet.")
    out.append("")

    open_q = list(dict.fromkeys(
        (latest.get("placeholders") or []) + (latest.get("points_to_confirm") or []) if latest else []))
    if d.get("needs_received_date"):
        open_q.insert(0, "Date the notice was actually received (the deadline counts from it).")
    if d.get("needs_notice_date"):
        open_q.insert(0, "Date of the notice (could not be read).")
    out += ["6. OPEN QUESTIONS"] + ([f"- {q}" for q in open_q] or ["- None recorded."]) + [""]

    docs = list(dict.fromkeys((latest.get("documents_to_gather") or [] if latest else []) + (info.get("documents") or [])))
    out += ["7. DOCUMENTS TO COLLECT"] + [f"- {x}" for x in docs]
    out += ["", "Prepared by LegalOS from the stored case. Decision support, not legal advice."]
    return "\n".join(x for x in out if x is not None).strip()
