# Alex: AI check (CLIP)

**You own:** `clip_model.py`. Don't edit other files.
**Goal:** CLIP's label agrees with the lane-snow % on most snapshots of both cameras, so the dashboard
shows "✅ both methods agree" during the demo.

Start Claude Code in the repo folder and say:
> Read CLAUDE.md and builders/ALEX.md, then do task 1.

## Task 1: Install and start the download (do this first, it's slow)
```
git pull --rebase origin main
python -m pip install -r requirements.txt
python clip_model.py Images
```
The first run downloads CLIP (~600 MB). Let it finish.
**Done when:** it prints a label + snow score for each of the 5 images.

## Task 2: Check CLIP inside the real pipeline
```
python frostline.py --camera lie_clearing
```
(The pipeline crops off the text header on the images; `clip_model.py` on its own doesn't, so trust this run.)
Compare against the correct answers in CLAUDE.md (Ground truth).
**Done when:** you've written down, per snapshot: CLIP label, snow score, agree / NEEDS REVIEW.

## Task 3: Fix wrong labels (wording only)
If labels are wrong, edit only the sentences in `PROMPTS` in `clip_model.py`. Keep the 6 label names and
`SNOW_LABELS` the same. Rerun task 2 after each change.
Ideas Claude can try: mention "plowed lanes with snow on the shoulders", "at night", "traffic camera".
**Done when:** at least 4 of 5 LIE snapshots say "agree". Don't chase 5/5. Night frames are hard;
"NEEDS REVIEW" on one night frame is fine (it shows the safety check working).
**Time limit: 30 minutes**, then stop and keep the best version.

## Task 4: Check the growth camera
When Hiroshi says `Images_growth/` and `cameras.py` are ready:
```
git pull --rebase origin main
python frostline.py --camera growth
```
Same check. Tune prompts only if the growth camera is clearly wrong and it doesn't break the LIE results.

## Task 5: Push
```
git pull --rebase origin main
git add clip_model.py
git commit -m "Tune CLIP prompts"
git push origin main
```
Tell Hiroshi and Samay it's pushed.

## Fallback
If torch won't install or the download fails after 20 minutes: tell the team. The demo runs without CLIP
(`python frostline.py --no-clip`); the dashboard just hides the AI-check line. Don't switch to a paid API tonight.
