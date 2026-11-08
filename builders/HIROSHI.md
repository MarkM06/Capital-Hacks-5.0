# Hiroshi: Pipeline, second camera, repo, final integration

**You own:** `frostline.py`, `cameras.py`, `station_readings.csv`, `readings_growth.csv`, `Images/`, `Images_growth/`.
**Goal:** both cameras run through the pipeline with correct lane-snow numbers, and the final version
on `main` runs end to end.

Start Claude Code in the Hackerton folder and say:
> Read CLAUDE.md and builders/HIROSHI.md, then do task 1.

## Task 0: Put the code on GitHub (do this FIRST; the others are waiting)
You need write access to `MarkM06/Capital-Hacks-5.0` (ask Mark to add you as a collaborator if a push is refused).
In `C:\Users\hirok\OneDrive\Desktop\Hackerton`:
```
git init -b main
git remote add origin https://github.com/MarkM06/Capital-Hacks-5.0.git
git fetch origin
git reset --mixed origin/main
git add .gitignore CLAUDE.md PLAN.md README.md builders tools requirements.txt *.py *.csv Images Images_growth
git commit -m "Frostline demo: pipeline, CLIP, dashboard, builder instructions"
git push -u origin main
```
(`git reset --mixed` keeps your files and just attaches them to the repo's existing first commit.)
Then tell Alex and Samay: **"Clone it now"**:
`git clone https://github.com/MarkM06/Capital-Hacks-5.0.git`
**Done when:** the files show on github.com on branch `main`.

## Task 1: Add the snow-growth images
Put the growth camera's snapshots in `Images_growth/` (same camera, in time order: bare/wet road → snow).
Filenames must contain the time like `2022-01-29-16_10_46` so they sort correctly. If they don't,
ask Claude to adjust `TIME_RE` in `frostline.py` to match your filenames (don't rename the files).

## Task 2: Set up the growth camera in `cameras.py`
```
python tools/grid.py Images_growth/<one image>.jpg
```
Give Claude the image from `output/grids/` and say:
> Fill in the "growth" entry in cameras.py: camera_box (picture without any text header), lanes
> (outline of the travel lanes in one direction, not the median or shoulder), and either snow_reference
> (a patch that is snow in EVERY frame) or snow_threshold (if the first frames have no snow anywhere).
> Also fill name, short, lat, lon.

Then run and **look at the overlays** in `output/growth/overlays/`: blue should cover only snow on the lanes.
```
python frostline.py --no-clip --camera growth
```
**Done when:** lane snow cover rises across the frames and the blue matches the snow you see.
Tweak the outline or `snow_threshold` until it does (10-point steps).

## Task 3: Temperature for the growth camera (only if the images show it)
If the growth images have a text header with temperature / snow depth like the LIE ones, ask Claude:
> Read each image in Images_growth/ and make readings_growth.csv with the same columns as station_readings.csv.

Then set `"readings": "readings_growth.csv"` in `cameras.py`. If there's no header, skip this; the dashboard shows "—".

## Task 4: Push
```
git pull --rebase origin main
git add cameras.py frostline.py Images_growth
git add readings_growth.csv        # only if you made it in task 3
git commit -m "Add snow-growth camera"
git push origin main
```
Tell Alex (task 4) and Samay.

## Task 5: Final integration (at about 1:20 into the plan)
```
git pull --rebase origin main
python frostline.py
python -m streamlit run dashboard.py
```
Play the full story twice with the team. Fix **only** what breaks. At code freeze, announce
**"freeze: no more pushes"**, then make sure the latest `main` runs on the laptop you'll present from.

## Fallback
If the growth images won't line up within 30 minutes: set `"story_order": 2` on LIE and skip the growth camera
(remove its images from `Images_growth/`). The demo still runs with the LIE story.
