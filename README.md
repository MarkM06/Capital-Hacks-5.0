# PermitPilot: AI for City Hall

> *"If you want to build a house or start a business in America, you first need permission from your city...
> In some cities, getting the permit takes longer than building the house."* (YC Request for Startups, "AI for City Hall")

PermitPilot starts where that request says to start: **building permits**. A resident describes their project in
plain English and gets an instant, code-cited pre-check. City staff get a review queue where every application has
already been checked against the zoning code, with a correction letter drafted and ready to send.

## The problem

- City staff spend their days on repetitive work: checking drawings against the code, matching applications to
  zoning rules, and sending corrections back and forth.
- Applicants wait weeks to learn about a 5 ft setback problem they could have fixed in an afternoon.
- Delay costs money. A project that waits isn't paying property tax, and some never get built. The staff console
  includes a calculator for that lost revenue.

## What it does

| For residents (`/`) | For plan reviewers (`/staff`) |
| --- | --- |
| Describe the project in your own words. Claude extracts the facts (height, setbacks, floor area, use, parking, documents). | A queue that is already triaged: *Ready to approve / Needs corrections / Needs info / Needs hearing*. |
| The parcel is looked up automatically (zoning district, lot size, existing building). | Every finding cites a code section and shows required vs. proposed values. |
| Instant result: what complies, what to fix, what's missing, and whether a hearing is needed. | Correct any extracted value and the review re-runs immediately. |
| Edit anything the AI misread and re-check, then submit. | Claude drafts a plain-language correction letter; the reviewer edits it and sends it. |
| **Ask City Hall**: questions answered only from the code, with citations. | One-click approve (blocked while findings are open), audit history, throughput metrics and a revenue-impact calculator. |

## How it's designed: AI reads and writes, rules decide

Cities can't use a black box to decide permits, so PermitPilot keeps the two jobs separate:

```
 applicant text ──► Claude (structured extraction) ──► ProjectParams ──► rule engine ──► findings + outcome
                     │ leaves unknowns null,                (editable)     deterministic,
                     │ never guesses                                       every finding cites the code
                     ▼
               findings ──► Claude (letter drafting) ──► reviewer edits ──► send
```

- **`app/zoning.py`**: a deterministic rule engine covering use permissions, density, height and stories,
  setbacks, lot coverage, FAR, ADU rules, parking (including the MU reduction) and submittal completeness. The same
  input always gives the same result, so decisions can be audited.
- **`app/ai.py`**: Claude (`claude-opus-5-5`) does the language work:
  - structured-output extraction into a Pydantic schema;
  - correction-letter drafting;
  - grounded Q&A over the code text, with the code corpus prompt-cached.

  Server-side refusal fallbacks are enabled. If no API key is set, or a call fails, every function falls back to an
  offline heuristic, so the demo always works.
- **`app/data/zoning_code.json`**: the city's code as data. To onboard a new city you replace this file and
  the parcel layer (`parcels.json`). The rule engine itself doesn't change.

The bundled jurisdiction ("City of Capitol Falls") and its code are **fictional sample data** for the demo.

## Run it

```bash
pip install -r requirements.txt
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # optional; without it the app runs on offline heuristics
```

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000 for the resident portal and http://localhost:8000/staff for the review console.
A demo queue is seeded on first run. Delete `permitpilot.db` to reset it.

| Env var | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | (unset) | Enables Claude. |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Model for extraction, letters and Q&A. |
| `PERMIT_AI_OFFLINE` | (unset) | Set to `1` to force offline heuristics. |
| `PERMITPILOT_DB` | `./permitpilot.db` | SQLite file location. |

### Demo script (3 minutes)

1. **Resident portal**: click *Backyard ADU*, then **Run instant pre-check**. It comes back *eligible for
   expedited approval* with each rule cited.
2. Click *Too-tall addition*. The house is 38 ft against a 35 ft limit, so it fails, and the missing footprint is
   flagged rather than guessed. Type a footprint into "What we understood" and re-check.
3. Click *Bar on Main St*. The rules comply, but a bar is a conditional use in C-1, so the result routes to a hearing.
4. **Ask City Hall**: "How big can a backyard cottage be?"
5. **Staff console**: open #2 (88 Birch Ave), click **Draft with AI**, then **Send corrections**. Open #4 and approve it.
6. Scroll to **Revenue impact**: enter your city's permit volume and see the tax revenue lost to delay.

## API

| Method & path | Purpose |
| --- | --- |
| `POST /api/precheck` | Extract and review without saving. Body: `{address, description, params?}` |
| `POST /api/applications` | Submit; the review runs at intake |
| `GET /api/applications[/{id}]` | Review queue / one application |
| `PUT /api/applications/{id}/params` | Reviewer correction, then re-review |
| `POST` / `PUT /api/applications/{id}/letter` | AI draft / save reviewer edits |
| `POST /api/applications/{id}/decision` | `approve` \| `send_corrections` \| `schedule_hearing` |
| `POST /api/ask` | Code Q&A with citations |
| `GET /api/metrics` | Queue and throughput metrics |

Interactive docs are at `/docs`.

## Tests

```bash
pip install -r requirements-dev.txt
```

```bash
pytest
```

The tests cover the rule engine, the heuristic extractor, the full staff workflow over HTTP, and the Claude request
shape (structured output, refusal fallbacks, prompt caching) using a mocked client. No API key is needed.

## Roadmap

1. **Plan-set reading**: send the PDF drawings to Claude's vision and document input to extract dimensions
   directly from the site plan and elevations.
2. **Real jurisdictions**: importers for municipal codes (Municode / American Legal) and GIS parcel layers.
3. **Beyond permits**, as the RFS asks: 311 request triage and routing, public records request redaction,
   business licensing (the code already includes UDC 9.1), and inspection scheduling and checklists.
4. **Integrations** with incumbent permitting systems (Accela, Tyler EnerGov) so cities adopt it without
   replacing anything.
