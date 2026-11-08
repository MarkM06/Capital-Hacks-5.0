# Frostline build plan: tonight (judging 9:00 AM)

**Target:** working demo + backup video in ~2 hours. Each builder's Claude Code reads `CLAUDE.md`
(shared rules) and their own file in `builders/`.

| Builder | Owns | Task file |
|---------|------|-----------|
| **Hiroshi** | `frostline.py`, `cameras.py`, image folders, readings, repo | `builders/HIROSHI.md` |
| **Alex** | `clip_model.py` (CLIP AI) | `builders/ALEX.md` |
| **Samay** | `dashboard.py` (Streamlit demo screen) | `builders/SAMAY.md` |

Separate files per person = no Git conflicts.

## Already working (tested)
- Pipeline on the LIE camera: lane snow cover 100 → 88 → 24 → 11 → 12 %, hazard score, ice risk, sign messages, blue overlays.
- Multi-camera support (growth camera slot ready in `cameras.py`, just needs images + lane outline).
- Dashboard: full-story view across cameras, slider, camera vs. overlay, metrics, sign message + Approve, chart, storm report, treat-first table, map.
- Not yet run: **CLIP** (Alex, task 1–2) and the **growth camera** (Hiroshi, task 1–2).

## Timeline
| Time from start | Hiroshi | Alex | Samay |
|------|---------|------|-------|
| 0:00–0:10 | **Task 0: push to GitHub** | Install, start CLIP download (on any copy) | Install |
| 0:10–0:45 | Growth images + `cameras.py` outline | Clone repo; check CLIP on LIE | Clone repo; run dashboard; **Play button** |
| 0:45–1:10 | Readings (if any) → push | Tune prompts (30-min cap); check growth cam → push | Story banners, bigger text → push |
| 1:10–1:40 | **All:** pull, `python frostline.py`, play the full story twice, fix only what breaks | | |
| 1:40–2:00 | **Freeze.** Samay records the backup video. Presenting laptop has latest `main` + model downloaded. | | |

**Cut order if behind:** prompt tuning → bigger text → story banners → growth camera.
**Never cut:** LIE story, blue overlay, sign message + Approve, chart, backup video.

## Demo flow the build must support
1. Full storm story → Play.
2. Growth camera: snow cover rises → priority climbs → sign message → click Approve.
3. LIE camera: 100% covered (HIGH) → plows clear to ~12% → **ICE RISK** at 16–20°F.
4. Chart + storm report.

**Before you sleep:** the presenting laptop must have CLIP already downloaded (venue Wi-Fi may be bad)
and `output/` freshly generated.
