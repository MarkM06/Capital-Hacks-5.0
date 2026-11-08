# Samay: Demo screen (dashboard)

**You own:** `dashboard.py`. Don't edit other files.
**Goal:** the dashboard plays the full storm story smoothly on a projector, with no errors.

Start Claude Code in the repo folder and say:
> Read CLAUDE.md and builders/SAMAY.md, then do task 1.

## Task 1: Get it running
```
git pull --rebase origin main
python -m pip install -r requirements.txt
python frostline.py --no-clip
python -m streamlit run dashboard.py
```
The browser opens at http://localhost:8501. Click "Full storm story", drag the slider through every snapshot,
click Approve. (Until Hiroshi adds the growth camera, only the LIE camera shows.)
**Done when:** every snapshot loads with no red error box.

## Task 2: Play button (most important)
Add a **▶ Play** button that steps the slider forward automatically, about one snapshot every 2 seconds,
and stops at the end. Use `st.session_state` for the current index, `time.sleep(2)` + `st.rerun()` to advance.
The slider must still work by hand.
**Done when:** pressing Play runs through the whole story by itself.

## Task 3: Story labels
In "Full storm story" view, show a big banner above the images based on the camera:
- story_order 1 → "Part 1: Snow builds up on the road"
- story_order 2 → "Part 2: Plows clear the lanes, but it's still below freezing"
**Done when:** the banner changes when the slider crosses from one camera to the other.

## Task 4: Projector-friendly
Bigger metric numbers and labels, condition and priority easy to read from the back of a room.
Keep the layout. Don't remove any section.
**Done when:** it's readable with the browser at 100% zoom on a 1080p screen.

## Task 5: Push, then re-check with real data
```
git pull --rebase origin main
git add dashboard.py
git commit -m "Dashboard: play button, story banners, bigger text"
git push origin main
```
After Alex and Hiroshi push: `git pull --rebase origin main`, run `python frostline.py` (with CLIP),
then the dashboard again. Fix only what breaks.

## Task 6: Backup video (at freeze time)
Record the full Play run-through (Windows: **Win + Alt + R**, or Xbox Game Bar). Save the video in this
folder but **don't commit it** (too big); put it on a USB / Google Drive.

## Rules
- Don't change field names you read from `results.json`. If you need a new field, ask Hiroshi.
- If a task takes more than 15 minutes, skip it and move to the next.
