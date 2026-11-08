"""
Frostline pipeline. OWNER: Hiroshi.

For every snapshot of every camera in cameras.py it works out:
  1. Lane snow cover %  - pixel check inside the lane outline (no AI)
  2. CLIP label         - from clip_model.py (Alex)
  3. Agreement          - pixel method vs CLIP; disagree -> "NEEDS REVIEW"
  4. Hazard score       - 0-100 from lane cover + air temp + falling snow, plus ICE RISK flag
  5. Sign message       - suggested 511 / sign text for an operator to approve

Run:
    python frostline.py                      # all cameras, with CLIP
    python frostline.py --no-clip            # fast, pixel method only
    python frostline.py --camera growth      # one camera

Output (read by dashboard.py):
    output/<camera_id>/results.json, results.csv, overlays/*.jpg
"""
import argparse
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from cameras import CAMERAS

HERE = Path(__file__).resolve().parent
SNOW_MATCH = 0.80   # a lane pixel is snow if it is >= 80% as bright as the snow reference patch
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d{2})_(\d{2})_(\d{2})")


def polygon_mask(size, polygon):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in polygon], fill=255)
    return np.asarray(m) > 0


def snapshot_time_utc(path: Path):
    m = TIME_RE.search(path.name)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}", "%Y-%m-%d %H:%M:%S")


def lane_snow_cover(image, cam):
    gray = np.asarray(image.convert("L")).astype(float)
    lanes = polygon_mask(image.size, cam["lanes"])
    if cam.get("snow_threshold"):
        # Fixed brightness (0-255): use when no patch is snow in every frame (e.g. storm starts on a bare road)
        snowy = (gray >= cam["snow_threshold"]) & lanes
    else:
        ref = polygon_mask(image.size, cam["snow_reference"])
        snow_brightness = float(np.median(gray[ref]))
        snowy = (gray >= SNOW_MATCH * snow_brightness) & lanes
    return round(100.0 * float(snowy.sum()) / float(lanes.sum()), 1), snowy


def save_overlay(image, snowy, cam, out_path):
    arr = np.asarray(image.convert("RGB")).astype(float)
    arr[snowy] = 0.45 * arr[snowy] + 0.55 * np.array([40, 160, 255], dtype=float)
    out = Image.fromarray(arr.astype(np.uint8))
    ImageDraw.Draw(out).polygon([tuple(p) for p in cam["lanes"]], outline=(255, 40, 40))
    if cam.get("camera_box"):
        out = out.crop(cam["camera_box"])
    out.save(out_path, quality=92)


def load_readings(cam):
    if not cam.get("readings"):
        return {}
    path = HERE / cam["readings"]
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["image"]: row for row in csv.DictReader(f)}


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def condition_from_cover(cover):
    if cover >= 60:
        return "SNOW-COVERED"
    if cover >= 20:
        return "PARTLY COVERED"
    return "LANES MOSTLY CLEAR"


def hazard(cover, temp_f, precipitating, hours_since_precip):
    score = 0.6 * cover
    if temp_f is not None:
        score += 25 if temp_f <= 25 else 15 if temp_f <= 32 else 5 if temp_f <= 36 else 0
    if precipitating:
        score += 15
    score = round(min(score, 100))
    # Ice is never "seen"; it is a RISK: lanes clear, below freezing, snow in the last 12 h.
    ice_risk = bool(cover < 20 and temp_f is not None and temp_f <= 32
                    and hours_since_precip is not None and hours_since_precip <= 12)
    level = "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"
    if ice_risk and level == "LOW":
        level = "MEDIUM"
    return score, level, ice_risk


def sign_message(short, condition, ice_risk):
    if condition == "SNOW-COVERED":
        return f"{short}: SNOW COVERED ROAD / REDUCE SPEED"
    if condition == "PARTLY COVERED":
        return f"{short}: SNOW ON ROADWAY / USE CAUTION"
    if ice_risk:
        return f"{short}: ICY PATCHES POSSIBLE / USE CAUTION"
    return ""


def run_camera(cam_id, cam, clip):
    folder = HERE / cam["folder"]
    images = [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES] if folder.exists() else []
    if not images:
        print(f"[{cam_id}] skipped: no images in {folder}")
        return
    if not cam.get("lanes") or not (cam.get("snow_reference") or cam.get("snow_threshold")):
        print(f"[{cam_id}] skipped: set 'lanes' and 'snow_reference' (or 'snow_threshold') in cameras.py")
        return
    images.sort(key=lambda p: (snapshot_time_utc(p) or datetime.min, p.name))

    out_dir = HERE / "output" / cam_id
    (out_dir / "overlays").mkdir(parents=True, exist_ok=True)
    readings = load_readings(cam)
    print(f"\n[{cam_id}] {cam['name']}")

    rows = []
    for path in images:
        image = Image.open(path).convert("RGB")
        cover, snowy = lane_snow_cover(image, cam)
        overlay_name = path.stem + "_overlay.jpg"
        save_overlay(image, snowy, cam, out_dir / "overlays" / overlay_name)

        t_utc = snapshot_time_utc(path)
        t_local = t_utc + timedelta(hours=cam["utc_offset_hours"]) if t_utc else None
        r = readings.get(path.name, {})
        temp_f = to_float(r.get("air_temp_f"))
        depth_m = to_float(r.get("snow_depth_m"))
        precipitating = str(r.get("precipitating", "")).strip().lower() == "true"
        since = to_float(r.get("hours_since_precip"))

        condition = condition_from_cover(cover)
        score, level, ice_risk = hazard(cover, temp_f, precipitating, since)

        clip_label = clip_conf = snow_score = None
        agreement = "pixel method only"
        if clip:
            crop = image.crop(cam["camera_box"]) if cam.get("camera_box") else image
            clip_label, clip_conf, snow_score, _ = clip.classify(crop)
            agreement = "agree" if (cover >= 20) == (snow_score >= 0.5) else "NEEDS REVIEW"

        rows.append({
            "image": path.name,
            "overlay": overlay_name,
            "time_local": t_local.strftime("%Y-%m-%d %H:%M") if t_local else path.stem,
            "lane_snow_cover_pct": cover,
            "condition": condition,
            "clip_label": clip_label or "",
            "clip_confidence": clip_conf if clip_conf is not None else "",
            "clip_snow_score": snow_score if snow_score is not None else "",
            "agreement": agreement,
            "air_temp_f": temp_f if temp_f is not None else "",
            "ground_snow_in": round(depth_m * 39.37, 1) if depth_m is not None else "",
            "snowing_now": precipitating,
            "hazard_score": score,
            "priority": level,
            "ice_risk": ice_risk,
            "sign_message": sign_message(cam["short"], condition, ice_risk),
        })
        clip_txt = f"  CLIP: {clip_label} ({clip_conf:.0%}) snow {snow_score:.2f} {agreement}" if clip else ""
        print(f"  {rows[-1]['time_local']}  lanes {cover:5.1f}%  {condition:18s} hazard {score:3d} {level:6s}"
              f"{'  ICE RISK' if ice_risk else ''}{clip_txt}")

    with open(out_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    meta = {k: cam[k] for k in ("name", "short", "lat", "lon", "story_order", "camera_box")}
    with open(out_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump({"camera_id": cam_id, **meta, "image_folder": cam["folder"], "snapshots": rows}, f, indent=2)
    print(f"  saved -> {out_dir / 'results.json'}")


def main():
    parser = argparse.ArgumentParser(description="Frostline road-condition pipeline")
    parser.add_argument("--no-clip", action="store_true", help="skip CLIP (pixel method only)")
    parser.add_argument("--camera", help="run only this camera id from cameras.py")
    args = parser.parse_args()

    clip = None
    if not args.no_clip:
        from clip_model import ClipClassifier
        clip = ClipClassifier()

    for cam_id, cam in CAMERAS.items():
        if args.camera and cam_id != args.camera:
            continue
        run_camera(cam_id, cam, clip)


if __name__ == "__main__":
    main()
