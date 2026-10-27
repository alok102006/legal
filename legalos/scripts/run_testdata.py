"""Push every file in docs/testdata through the product (as the demo company) and print what it found.

Uses the real AI, so it costs about 2 calls per contract/notice and 1 per document, plus the questions.
Run from the legalos folder:  python scripts/run_testdata.py [--only contracts|notices|documents|questions]
"""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://localhost:8010/api/v1"
H = {"X-User-Role": "owner"}
ROOT = Path(__file__).resolve().parents[1] / "docs" / "testdata"
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None


def wait(url, done, label, seconds=240):
    t0 = time.time()
    while time.time() - t0 < seconds:
        d = requests.get(url, headers=H, timeout=30).json()
        if done(d):
            return d
        time.sleep(4)
    raise SystemExit(f"timed out waiting for {label}")


def contracts():
    print("\n== CONTRACTS")
    for f in sorted((ROOT / "contracts").glob("*.txt")):
        with f.open("rb") as fh:
            r = requests.post(f"{BASE}/contracts/upload", headers=H, files={"file": (f.name, fh, "text/plain")}, timeout=60).json()
        d = wait(f"{BASE}/contracts/{r['id']}", lambda x: x["status"] in ("analyzed", "failed"), f.name)
        if d["status"] != "analyzed":
            print(f"  FAILED {f.name}: {d.get('error_message')}")
            continue
        finds = d.get("findings") or []
        sev = {}
        for x in finds:
            sev[x.get("severity")] = sev.get(x.get("severity"), 0) + 1
        print(f"  {f.name}: type={d.get('contract_type')} risk={d.get('risk_score')} ({d.get('risk_level')}) findings={len(finds)} {sev}")
        for x in finds[:4]:
            print(f"     - [{x.get('severity')}] {x.get('title')}" + (f"  (p.{x.get('page')})" if x.get("page") else ""))


def notices():
    print("\n== NOTICES")
    for f in sorted((ROOT / "notices").glob("*.txt")):
        text = f.read_text(encoding="utf-8")
        r = requests.post(f"{BASE}/notices/text", headers=H, json={"text": text, "received_date": time.strftime("%Y-%m-%d")}, timeout=60).json()
        d = wait(f"{BASE}/notices/{r['id']}", lambda x: x["status"] in ("analyzed", "failed"), f.name)
        if d["status"] != "analyzed":
            print(f"  FAILED {f.name}: {d.get('error_message')}")
            continue
        print(f"  {f.name}: type={d.get('notice_type')} from={d.get('issuer_name')} amount={d.get('amount')} "
              f"deadline={d.get('deadline_date')} ({d.get('deadline_source')}) days_left={d.get('days_left')} urgency={d.get('urgency')} "
              f"actions={len(d.get('actions') or [])} quotes_verified={sum(1 for q in d.get('key_quotes') or [] if q.get('verified'))}/{len(d.get('key_quotes') or [])}")


def documents():
    print("\n== DOCUMENTS")
    cats = {"14": "HR", "15": "Operations", "16": "Safety", "17": "Sales", "18": "Board", "19": "Insurance"}
    for f in sorted((ROOT / "documents").glob("*.txt")):
        with f.open("rb") as fh:
            r = requests.post(f"{BASE}/knowledge/documents/upload", headers=H, files={"file": (f.name, fh, "text/plain")},
                              data={"category": cats.get(f.name[:2], "General")}, timeout=60).json()
        d = wait(f"{BASE}/knowledge/documents/{r['id']}", lambda x: x["status"] == "failed" or (x["status"] == "ready" and x.get("review_state") != "pending"), f.name)
        print(f"  {f.name}: status={d['status']} review={d.get('review_state')} type={d.get('doc_type')} lang={d.get('language')} chunks={d.get('chunk_count')} "
              f"expiry={d.get('expiry_date')} questions={len(d.get('suggested_questions') or [])}")


QUESTIONS = [
    "How many days of casual leave do I get in a year?",
    "What is the approval limit for a purchase order of 3 lakh?",
    "accident report kitne ghante ke andar karna hai?",
    "What is the price and MOQ of SKU SIP-1005?",
    "Who is authorised to sign cheques and up to what amount?",
    "When does the fire and burglary policy expire and how soon must a claim be intimated?",
    "summarise the leave policy",
]


def questions():
    print("\n== QUESTIONS")
    c = requests.post(f"{BASE}/knowledge/conversations", headers=H, json={}, timeout=30).json()
    for q in QUESTIONS:
        d = requests.post(f"{BASE}/knowledge/conversations/{c['id']}/ask", headers=H, json={"question": q}, timeout=180).json()
        cits = d.get("citations") or []
        print(f"  Q: {q}\n     found={d.get('found_in_documents')} conf={d.get('confidence')} cited={len(cits)} verified={sum(1 for x in cits if x.get('verified'))}\n     A: {(d.get('content') or '')[:220].replace(chr(10), ' ')}")
    requests.patch(f"{BASE}/knowledge/conversations/{c['id']}", headers=H, json={"title": "Demo rehearsal"}, timeout=30)


for name, fn in [("contracts", contracts), ("notices", notices), ("documents", documents), ("questions", questions)]:
    if only in (None, name):
        fn()
print("\ndone")
