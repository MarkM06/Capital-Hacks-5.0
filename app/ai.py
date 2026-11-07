"""AI layer: Claude for language tasks, with offline fallbacks.

Claude does three jobs, none of which is making the compliance decision:

1. ``extract_params``  - read a plain-English project description and pull out
   the objective facts the rule engine needs (structured output).
2. ``draft_letter``    - turn rule-engine findings into a clear, friendly
   correction letter that staff can edit and send.
3. ``ask_code``        - answer a resident's question, grounded only in the
   city's code text, citing sections.

If no Anthropic credentials are configured (or ``PERMIT_AI_OFFLINE=1``), every
function falls back to a deterministic heuristic so the app still works.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Tuple

from .models import Parcel, ProjectParams, ReviewResult
from .zoning import load_code

log = logging.getLogger("permitpilot.ai")

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
# Server-side refusal fallback: the API re-runs a declined request on Anthropic's
# recommended fallback model instead of returning the refusal.
FALLBACK_BETAS = ["server-side-fallback-2026-07-01"]

_client = None


def _get_client():
    """Return an Anthropic client, or None when running offline."""
    global _client
    if os.environ.get("PERMIT_AI_OFFLINE") == "1":
        return None
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def ai_status() -> dict:
    online = _get_client() is not None
    return {"mode": "claude" if online else "offline", "model": MODEL if online else None}


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def _call(**kwargs):
    """Call the Messages API with refusal fallbacks enabled. Returns None on refusal."""
    client = _get_client()
    method = client.beta.messages.parse if "output_format" in kwargs else client.beta.messages.create
    response = method(model=MODEL, betas=FALLBACK_BETAS, fallbacks="default", **kwargs)
    if response.stop_reason == "refusal":
        log.warning("Claude declined request: %s", getattr(response, "stop_details", None))
        return None
    return response


# --------------------------------------------------------------------------------------
# 1. Extraction
# --------------------------------------------------------------------------------------

EXTRACT_SYSTEM = """You are an intake assistant for a city permitting office.
Read an applicant's description of their project and extract the objective facts a plan
reviewer needs. Rules:
- Only record values the applicant stated or that follow directly by arithmetic
  (e.g. a one-story 20x30 ft building has a 600 sq ft footprint and 600 sq ft floor area).
- Never guess or fill in typical values. Leave a field null if it was not given;
  the reviewer will ask for it.
- Footprint and floor area are for the NEW work only, not the existing house.
- new_dwelling_units counts dwelling units added; an ADU is project_type "adu" and use "adu",
  not a new dwelling unit.
- submittals: only documents the applicant says are attached or included.
- Setbacks are distances from the new structure to the property lines.
"""


def extract_params(description: str, parcel: Optional[Parcel] = None) -> Tuple[ProjectParams, str]:
    if _get_client() is not None and description.strip():
        try:
            context = ""
            if parcel:
                context = (f"\n\nParcel on record: {parcel.address}, zoned {parcel.district}, "
                           f"lot {parcel.lot_area_sqft:.0f} sq ft, existing floor area "
                           f"{parcel.existing_floor_area_sqft:.0f} sq ft, {parcel.existing_units} existing unit(s).")
            response = _call(
                max_tokens=8000,
                output_config={"effort": "low"},
                system=EXTRACT_SYSTEM,
                messages=[{"role": "user", "content": f"Project description:\n{description}{context}"}],
                output_format=ProjectParams,
            )
            if response is not None and response.parsed_output is not None:
                return response.parsed_output, "claude"
        except Exception as exc:  # network, auth, rate limit... keep the counter open
            log.warning("Claude extraction failed, using heuristics: %s", exc)
    return heuristic_extract(description), "heuristic"


_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "twelve": 12, "single": 1, "a": 1}
_NUM = r"(\d[\d,]*(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twelve|single)"


def _num(s: str) -> float:
    s = s.lower().replace(",", "")
    return float(_WORDNUM.get(s, s))


def heuristic_extract(text: str) -> ProjectParams:
    t = " " + text.lower() + " "
    p: dict = {}

    if re.search(r"\badu\b|accessory dwelling|granny flat|in-law|backyard cottage|carriage house", t):
        p["project_type"], p["use"] = "adu", "adu"
    elif re.search(r"change of use|convert(ing)? .{0,40} (to|into)|open (a|an|my) ", t):
        p["project_type"] = "change_of_use"
    elif re.search(r"tenant improvement|interior (remodel|renovation|build-?out)", t):
        p["project_type"] = "tenant_improvement"
    elif re.search(r"\baddition\b|\badd (a|an|on)\b|expand|extend", t):
        p["project_type"] = "addition"
    elif re.search(r"\b(shed|detached garage|carport|workshop)\b", t):
        p["project_type"], p["use"] = "accessory_structure", "accessory_structure"
    elif re.search(r"\b(build|construct|new)\b", t):
        p["project_type"] = "new_construction"

    m = re.search(_NUM + r"[- ](?:new )?(?:residential |dwelling |apartment |housing )?(?:units?|apartments|homes|townhomes)", t)
    if m:
        p["new_dwelling_units"] = int(_num(m.group(1)))

    if "use" not in p:
        uses = [
            (r"restaurant|caf[eé]|coffee|bakery|pizzeria|diner", "restaurant"),
            (r"\bbar\b|brewery|taproom|tavern|pub\b", "bar"),
            (r"day ?care|child ?care|preschool", "daycare"),
            (r"salon|barber|nail|spa\b|tattoo", "personal_services"),
            (r"\boffice", "office"),
            (r"retail|\bshop\b|\bstore\b|boutique", "retail"),
            (r"drive-?thr", "drive_through"),
            (r"duplex", "duplex"),
            (r"triplex", "triplex"),
            (r"apartment|multi-?family|condo", "multifamily"),
            (r"house|home|single-?family|bedroom|kitchen|family room|sunroom|garage conversion", "single_family"),
        ]
        for pattern, use in uses:
            if re.search(pattern, t):
                p["use"] = use
                break
        units = p.get("new_dwelling_units")
        if units and (units >= 4 or p.get("use") in (None, "single_family", "multifamily", "duplex", "triplex")):
            # A building with 4+ homes is multifamily even with ground-floor retail.
            p["use"] = {1: "single_family", 2: "duplex", 3: "triplex"}.get(units, "multifamily")
        if p.get("project_type") == "new_construction" and p.get("use") == "single_family":
            p.setdefault("new_dwelling_units", 1)

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')\s*(?:tall|high|in height)", t) or \
        re.search(r"height (?:of|is|at)?\s*(\d+(?:\.\d+)?)", t)
    if m:
        p["height_ft"] = float(m.group(1))
    m = re.search(_NUM + r"[- ]stor(?:y|ies|ey)", t)
    if m:
        p["stories"] = _num(m.group(1))

    m = re.search(r"(\d[\d,]*)\s*(?:sq\.?\s*ft|square[- ]f(?:ee|oo)t|sf)\b(?: building)? footprint", t) or \
        re.search(r"footprint (?:of|is)?\s*(\d[\d,]*)", t)
    if m:
        p["footprint_sqft"] = _num(m.group(1))
    m = re.search(r"(\d+)\s*(?:ft|feet|')?\s*(?:x|by)\s*(\d+)\s*(?:ft|feet|')", t)
    dims_area = float(m.group(1)) * float(m.group(2)) if m else None
    areas = [_num(a) for a in re.findall(r"(\d[\d,]*)\s*(?:sq\.?\s*ft|square[- ]f(?:ee|oo)t|sf)\b", t)]
    if areas:
        p["floor_area_sqft"] = max(areas)
    elif dims_area:
        p["floor_area_sqft"] = dims_area * (p.get("stories") or 1)
    if "footprint_sqft" not in p:
        if dims_area:
            p["footprint_sqft"] = dims_area
        elif "floor_area_sqft" in p and p.get("stories"):
            p["footprint_sqft"] = p["floor_area_sqft"] / p["stories"]

    for side in ("front", "side", "rear"):
        alias = "(?:rear|back)" if side == "rear" else side
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|')\s*(?:from|to|off)\s*(?:the\s*)?(?:\w+\s){0,2}?" + alias, t) or \
            re.search(alias + r"(?: yard)? setback (?:of|is)?\s*(\d+(?:\.\d+)?)", t)
        if m:
            p[f"{side}_setback_ft"] = float(m.group(1))

    m = re.search(_NUM + r"\s*(?:off-street |on-site )?(?:parking spaces|parking spots|spaces|car garage|-car garage)", t)
    if m:
        p["parking_spaces"] = int(_num(m.group(1)))
    elif re.search(r"no (?:off-street )?parking", t):
        p["parking_spaces"] = 0

    docs = {
        "site_plan": r"site plan|plot plan", "floor_plans": r"floor plans?", "elevations": r"elevations",
        "structural_calcs": r"structural", "energy_compliance": r"energy", "survey": r"survey",
        "utility_plan": r"utility", "occupancy_letter": r"occupancy", "parking_plan": r"parking (?:plan|layout)",
    }
    p["submittals"] = [k for k, pat in docs.items() if re.search(pat, t)]
    p["summary"] = text.strip().split(".")[0][:200]
    return ProjectParams(**p)


# --------------------------------------------------------------------------------------
# 2. Correction letters
# --------------------------------------------------------------------------------------

LETTER_SYSTEM = """You write plan-review correspondence for a city permitting office.
Given a rule-engine review of a permit application, write the letter the reviewer will send.
- Plain language a homeowner or small-business owner understands; no jargon without explanation.
- Lead with the outcome. Then a numbered list: one item per issue, each with the code section,
  what the plans show, what the code requires, and a concrete way to fix it.
- Mention what already complies in one short sentence so the applicant knows what NOT to change.
- Do not invent requirements beyond the findings provided. Do not promise approval.
- Plain text, no markdown headers. Sign off as "Plan Review, City of Capitol Falls".
"""


def _findings_text(review: ReviewResult) -> str:
    lines = []
    for f in review.findings:
        line = f"- [{f.status}] {f.title} ({f.section}): {f.detail}"
        if f.required:
            line += f" Required: {f.required}."
        if f.proposed:
            line += f" Proposed: {f.proposed}."
        lines.append(line)
    return "\n".join(lines)


def draft_letter(app: dict, review: ReviewResult) -> Tuple[str, str]:
    if _get_client() is not None:
        try:
            prompt = (f"Applicant: {app['applicant_name']}\nAddress: {app['address']}\n"
                      f"Application #: {app['id']}\nProject: {app.get('description') or ''}\n\n"
                      f"Outcome: {review.outcome_label}\nFindings:\n{_findings_text(review)}")
            response = _call(
                max_tokens=8000,
                output_config={"effort": "medium"},
                system=LETTER_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            if response is not None:
                text = _text(response)
                if text:
                    return text, "claude"
        except Exception as exc:
            log.warning("Claude letter drafting failed, using template: %s", exc)
    return template_letter(app, review), "template"


def template_letter(app: dict, review: ReviewResult) -> str:
    issues = [f for f in review.findings if f.status in ("fail", "info_needed", "discretionary")]
    ok = [f.title for f in review.findings if f.status == "pass"]
    out = [f"Dear {app['applicant_name']},", "",
           f"Re: Permit application #{app['id']} - {app['address']}", "",
           f"Review outcome: {review.outcome_label}.", ""]
    if issues:
        out.append("Please address the following items and resubmit:")
        for i, f in enumerate(issues, 1):
            line = f"{i}. {f.title} ({f.section}): {f.detail}"
            if f.status == "fail" and f.required and f.proposed:
                line += f" Your plans show {f.proposed}; the code requires {f.required}."
            out.append(line)
        out.append("")
    else:
        out += ["Your application complies with all objective standards we checked and is complete.", ""]
    if ok:
        out += [f"These items already comply and need no changes: {', '.join(ok)}.", ""]
    out += ["If you have questions, reply to this message or call the permit counter.", "",
            "Plan Review, City of Capitol Falls"]
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# 3. Ask the code
# --------------------------------------------------------------------------------------

def _code_corpus() -> str:
    code = load_code()
    return "\n\n".join(f"[{s['id']}] {s['title']}\n{s['text']}" for s in code["sections"])


ASK_SYSTEM_HEAD = """You answer residents' questions about the City of Capitol Falls development code
(permits, zoning, ADUs, parking, fences, business licenses).
- Answer ONLY from the code sections below. If they do not answer the question, say so and suggest
  contacting the permit counter. Never invent numbers.
- Cite the section id in brackets, e.g. [UDC 6.3], after each fact.
- Keep it short: 2-6 sentences, plain language.

CODE SECTIONS:
"""


def ask_code(question: str) -> Tuple[str, List[str], str]:
    if _get_client() is not None:
        try:
            response = _call(
                max_tokens=4000,
                output_config={"effort": "medium"},
                # The code text is identical on every request, so cache it.
                system=[{"type": "text", "text": ASK_SYSTEM_HEAD + _code_corpus(),
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": question}],
            )
            if response is not None:
                answer = _text(response)
                cites = sorted(set(re.findall(r"UDC \d+\.\d+", answer)))
                return answer, cites, "claude"
        except Exception as exc:
            log.warning("Claude Q&A failed, using keyword search: %s", exc)
    return keyword_answer(question)


_STOP = set("a an the is are do does i my can to of in on for and or what how much many need with be it".split())


def keyword_answer(question: str) -> Tuple[str, List[str], str]:
    words = [w for w in re.findall(r"[a-z0-9-]+", question.lower()) if w not in _STOP and len(w) > 1]
    adu = ["adu", "accessory", "dwelling"]
    synonyms = {"adu": adu, "granny": adu, "cottage": adu, "in-law": adu, "casita": adu, "backyard": adu,
                "fence": ["fences"], "parking": ["spaces"], "business": ["license"], "shop": ["license"],
                "tall": ["height"], "high": ["height"], "big": ["sq", "ft"], "large": ["sq", "ft"],
                "size": ["sq", "ft"], "hearing": ["conditional"], "variance": ["variances"]}
    for w in list(words):
        words += synonyms.get(w, [])
    scored = []
    for s in load_code()["sections"]:
        hay = (s["title"] + " " + s["text"]).lower()
        score = sum(hay.count(w) for w in words) + 3 * sum(w in s["title"].lower() for w in words)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    top = [s for _, s in scored[:2]]
    if not top:
        return ("I couldn't find a code section that answers that. Please contact the permit counter.", [], "keyword")
    answer = " ".join(f"[{s['id']}] {s['title']}: {s['text']}" for s in top)
    return answer, [s["id"] for s in top], "keyword"
