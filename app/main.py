"""PermitPilot API: AI-assisted permit intake and plan review for City Hall."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, store
from .models import ApplicationIn, AskIn, LetterIn, ProjectParams
from .zoning import all_parcels, find_parcel, load_code, review

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).parent / "static"

INTAKE_STATUS = {
    "approvable": "ready_to_approve",
    "corrections_required": "needs_corrections",
    "incomplete": "needs_info",
    "hearing_required": "needs_hearing",
}
DECISIONS = {
    "approve": ("approved", "Permit approved"),
    "send_corrections": ("corrections_sent", "Correction letter sent to applicant"),
    "schedule_hearing": ("hearing_scheduled", "Referred to Planning Commission hearing"),
}
# Assumption used for the "staff hours saved" metric: a manual completeness +
# zoning check of one application takes a reviewer about 1.5 hours.
MANUAL_PRECHECK_HOURS = 1.5


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init()
    if store.count() == 0:
        seed_demo_data()
    yield


app = FastAPI(title="PermitPilot", description="AI for City Hall: permit pre-review", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def applicant_page():
    return FileResponse(STATIC / "index.html")


@app.get("/staff", include_in_schema=False)
def staff_page():
    return FileResponse(STATIC / "staff.html")


@app.get("/api/status")
def status():
    code = load_code()
    return {**ai.ai_status(), "jurisdiction": code["jurisdiction"], "code_name": code["code_name"]}


@app.get("/api/parcels")
def parcels():
    return [p.model_dump() for p in all_parcels()]


def _parcel_or_404(address: str):
    parcel = find_parcel(address)
    if parcel is None:
        raise HTTPException(404, f"No parcel on record for '{address}'. Try one of: "
                                 + ", ".join(p.address for p in all_parcels()))
    return parcel


def _run_precheck(body: ApplicationIn):
    parcel = _parcel_or_404(body.address)
    if body.params is not None:
        params, source = body.params, "applicant"
    else:
        params, source = ai.extract_params(body.description, parcel)
    return parcel, params, source, review(params, parcel)


@app.post("/api/precheck")
def precheck(body: ApplicationIn):
    """Instant, unsaved pre-check: what would plan review say right now?"""
    parcel, params, source, result = _run_precheck(body)
    return {"parcel": parcel.model_dump(), "params": params.model_dump(), "extraction_source": source,
            "review": result.model_dump()}


@app.post("/api/applications", status_code=201)
def submit(body: ApplicationIn):
    parcel, params, source, result = _run_precheck(body)
    return store.insert({
        "address": parcel.address, "parcel": parcel.model_dump(), "applicant_name": body.applicant_name,
        "applicant_email": body.applicant_email, "description": body.description,
        "params": params.model_dump(), "review": result.model_dump(), "extraction_source": source,
        "status": INTAKE_STATUS[result.outcome],
    })


@app.get("/api/applications")
def list_applications():
    return store.list_all()


def _app_or_404(app_id: int) -> dict:
    record = store.get(app_id)
    if record is None:
        raise HTTPException(404, "Application not found")
    return record


@app.get("/api/applications/{app_id}")
def get_application(app_id: int):
    return _app_or_404(app_id)


def _log(record: dict, event: str) -> list:
    return record["history"] + [{"at": store.now(), "event": event}]


@app.put("/api/applications/{app_id}/params")
def correct_params(app_id: int, params: ProjectParams):
    """Reviewer corrects an extracted value; the rule engine re-runs immediately."""
    record = _app_or_404(app_id)
    from .models import Parcel

    result = review(params, Parcel(**record["parcel"]))
    return store.update(app_id, params=params.model_dump(), review=result.model_dump(),
                        status=INTAKE_STATUS[result.outcome], letter=None, letter_source=None,
                        history=_log(record, "Reviewer edited project data; re-reviewed"))


@app.post("/api/applications/{app_id}/letter")
def draft_letter(app_id: int):
    record = _app_or_404(app_id)
    from .models import ReviewResult

    text, source = ai.draft_letter(record, ReviewResult(**record["review"]))
    return store.update(app_id, letter=text, letter_source=source,
                        history=_log(record, f"Letter drafted ({source})"))


@app.put("/api/applications/{app_id}/letter")
def save_letter(app_id: int, body: LetterIn):
    record = _app_or_404(app_id)
    return store.update(app_id, letter=body.letter, letter_source="staff",
                        history=_log(record, "Letter edited by reviewer"))


class DecisionIn(BaseModel):
    action: Literal["approve", "send_corrections", "schedule_hearing"]
    note: Optional[str] = None


@app.post("/api/applications/{app_id}/decision")
def decide(app_id: int, body: DecisionIn):
    record = _app_or_404(app_id)
    if body.action == "approve" and record["review"]["outcome"] != "approvable":
        raise HTTPException(409, "Open findings remain. Resolve them or send corrections before approving.")
    new_status, event = DECISIONS[body.action]
    if body.note:
        event += f": {body.note}"
    return store.update(app_id, status=new_status, decided_at=store.now(), history=_log(record, event))


@app.post("/api/ask")
def ask(body: AskIn):
    if not body.question.strip():
        raise HTTPException(400, "Ask a question")
    answer, citations, source = ai.ask_code(body.question)
    return {"answer": answer, "citations": citations, "source": source}


def _days(a: str, b: Optional[str] = None) -> float:
    start = datetime.fromisoformat(a)
    end = datetime.fromisoformat(b) if b else datetime.now(timezone.utc)
    return (end - start).total_seconds() / 86400


@app.get("/api/metrics")
def metrics():
    apps = store.list_all()
    by_status: dict = {}
    for a in apps:
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
    decided = [a for a in apps if a["decided_at"]]
    open_apps = [a for a in apps if not a["decided_at"]]
    intake_clear = [a for a in apps if a["history"] and a["review"]["outcome"] == "approvable"]
    return {
        "total": len(apps),
        "by_status": by_status,
        "open": len(open_apps),
        "auto_cleared_pct": round(100 * len(intake_clear) / len(apps)) if apps else 0,
        "avg_days_to_decision": round(mean(_days(a["created_at"], a["decided_at"]) for a in decided), 1) if decided else None,
        "oldest_open_days": round(max((_days(a["created_at"]) for a in open_apps), default=0), 1),
        "staff_hours_saved": round(len(apps) * MANUAL_PRECHECK_HOURS, 1),
    }


# --------------------------------------------------------------------------------------
# Demo data
# --------------------------------------------------------------------------------------

DEMO_APPLICATIONS = [
    ("412 Maple St", "Dana Whitfield", 9,
     "Detached ADU in the backyard: one-story, 600 sq ft, 16 ft tall, 6 ft from the side property line and "
     "8 ft from the rear property line. Site plan, floor plans, elevations and utility plan attached."),
    ("88 Birch Ave", "Luis Ortega", 6,
     "Two-story rear addition adding a family room and bedroom, 800 sq ft total floor area with a 400 sq ft footprint, "
     "24 ft tall, 15 ft from the rear property line and 5 ft from the side. Site plan and floor plans attached."),
    ("230 Main St", "Priya Natarajan", 4,
     "Change of use: convert the existing 2,000 sq ft retail space into a coffee shop / cafe. "
     "We have 6 parking spaces. Floor plans and occupancy letter attached, parking plan attached."),
    ("1500 Commerce Blvd", "Harbor Row Development LLC", 2,
     "New 5-story mixed use building with 20 residential units over ground floor retail, 60 ft tall, "
     "6,000 sq ft footprint, 30,000 sq ft total floor area, rear setback of 12 ft, 10 parking spaces. "
     "Site plan, floor plans, elevations, structural calcs, energy forms and survey attached."),
    ("19 Oak Ct", "Sam Kowalski", 1,
     "Build an addition: one-story 20 ft by 30 ft sunroom off the back, 14 ft tall, 10 ft from the rear "
     "property line and 8 ft from the side. Site plan, floor plans, elevations and structural calcs attached."),
    ("77 Riverside Dr", "Riverside Childcare Co-op", 0,
     "New one-story daycare building, 3,000 sq ft, 18 ft tall, 20 ft from the front, 10 ft from the side, "
     "20 ft from the rear, 6 parking spaces. Site plan, floor plans, elevations, structural, energy and survey attached."),
]


def seed_demo_data() -> None:
    """Seed a realistic queue using the offline extractor so demos are deterministic."""
    base = datetime.now(timezone.utc)
    for address, name, days_ago, desc in DEMO_APPLICATIONS:
        parcel = find_parcel(address)
        params = ai.heuristic_extract(desc)
        result = review(params, parcel)
        created = (base - timedelta(days=days_ago, hours=3)).isoformat(timespec="seconds")
        store.insert({
            "created_at": created, "address": parcel.address, "parcel": parcel.model_dump(),
            "applicant_name": name, "applicant_email": "", "description": desc, "params": params.model_dump(),
            "review": result.model_dump(), "extraction_source": "heuristic",
            "status": INTAKE_STATUS[result.outcome],
            "history": [{"at": created, "event": "Submitted and auto-reviewed"}],
        })
    # One historical approval so turnaround metrics have data.
    first = store.list_all()[0]
    if first["review"]["outcome"] == "approvable":
        decided = (datetime.fromisoformat(first["created_at"]) + timedelta(days=1)).isoformat(timespec="seconds")
        store.update(first["id"], status="approved", decided_at=decided,
                     history=first["history"] + [{"at": decided, "event": "Permit approved"}])
