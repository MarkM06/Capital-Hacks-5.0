# Frostline: instructions for Claude Code (read fully before doing anything)

You are helping one of 3 builders (Alex, Samay, Hiroshi) finish a **hackathon demo**.
Judging is at **9:00 AM**. Code freeze is about **2 hours** after the team starts.
**Only do work that makes the demo run.** No refactors, no new features, no tests, no docs, no pitch work.

## What Frostline is
AI reads road conditions from traffic-camera snapshots that transportation departments (DOTs) already have.
For each snapshot it measures **how much of the travel lanes is covered in snow** (pixel check)
and asks **CLIP** (an open-source vision AI) what it sees. Then it gives a hazard score, an ice-risk flag
and a suggested road-sign message that a human operator approves.

## The demo (what must work at 9 AM)
`python -m streamlit run dashboard.py` → "Full storm story" view → drag the slider:
1. **Part 1, snow-growth camera** (`Images_growth/`): lane snow cover rises, priority goes up.
2. **Part 2, Long Island Expwy camera** (`Images/`): 100% covered → plows clear it to ~12% → **ICE RISK** because it's 16–20°F.
3. The sign message + **Approve** button, the lane-snow chart, the storm report.

## Files and owners: edit ONLY your builder's files
| File | Owner | What it does |
|------|-------|--------------|
| `clip_model.py` | **Alex** | CLIP classifier: prompts, labels, snow score |
| `dashboard.py` | **Samay** | Streamlit demo screen |
| `frostline.py` | **Hiroshi** | Pipeline: runs every camera, writes `output/` |
| `cameras.py` | **Hiroshi** | Per-camera settings: image folder, lane outline, snow reference |
| `station_readings.csv`, `readings_growth.csv` | **Hiroshi** | Air temp / snow depth per image |
| `Images/`, `Images_growth/` | **Hiroshi** | Snapshots (do not rename or edit) |
| `tools/grid.py` | anyone | Draws a pixel grid on an image to read coordinates |

If your task truly needs a change in someone else's file, **stop and tell your builder** to ask that person.
Never reformat or "clean up" other files. That causes Git conflicts.

Your builder's task list is in `builders/<NAME>.md`. Follow it in order.

## How to run (Windows, from the repo folder)
```
python -m pip install -r requirements.txt
python frostline.py --no-clip      # fast (seconds), pixel method only
python frostline.py                # with CLIP (first run downloads ~600 MB)
python frostline.py --camera growth
python -m streamlit run dashboard.py
```
Use `python -m pip` / `python -m streamlit` (works even if Scripts isn't on PATH).
If `torch` won't install, check `python --version`. Use Python 3.11 or 3.12.

## Data contract (don't break it)
`frostline.py` writes `output/<camera_id>/results.json`:
```
{ camera_id, name, short, lat, lon, story_order, camera_box, image_folder,
  snapshots: [ { image, overlay, time_local "YYYY-MM-DD HH:MM", lane_snow_cover_pct,
                 condition, clip_label, clip_confidence, clip_snow_score, agreement,
                 air_temp_f, ground_snow_in, snowing_now, hazard_score, priority,
                 ice_risk, sign_message } ] }
```
Empty values are `""`. `dashboard.py` reads exactly these fields. Adding a field is OK; renaming or removing one is not.
`clip_model.ClipClassifier().classify(pil_image)` must keep returning `(label, confidence, snow_score, all_scores)`.

## Git rules (shared repo: github.com/MarkM06/Capital-Hacks-5.0, branch `main`)
- Before starting and before every push: `git pull --rebase origin main`
- Commit small and often: `git add <your files>` (never `git add .`), `git commit -m "..."`, `git push origin main`
- Never commit `output/` (it's in `.gitignore`), never force-push.
- If a pull shows a conflict in a file you don't own, take their version: `git checkout --theirs <file>` and tell your builder.

## Ground truth (for checking results)
LIE camera (`Images/`), lane snow cover with the pixel method: 100 → 88 → 24 → 11 → 12 %.
Correct conditions: 11:10 snow-covered · 15:00 snow-covered (plowing started) · 17:00 partly covered ·
18:10 and 22:15 lanes mostly clear (wet/dry, below freezing → ice risk). Night frames (18:10, 22:15) have headlight glare.

## Working style
- Explain to your builder in plain words; they're not professional programmers.
- Make the smallest change that works, run it, show the result.
- If something takes more than 15 minutes, stop and tell your builder to use the fallback in their task file.
