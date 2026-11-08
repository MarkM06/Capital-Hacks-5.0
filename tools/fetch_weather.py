"""
One-time script: real historical weather for the growth camera (I-29 at Sidney, Iowa)
from Open-Meteo (free, no API key) -> readings_growth.csv (same columns as station_readings.csv).

    python tools/fetch_weather.py

Per image in Images_growth/ (time from the filename, already local Central time):
  air_temp_f         temperature at the hour nearest the image time
  snow_depth_m       snow depth at that hour (meters)
  precipitating      True if snowfall > 0 in that hour
  hours_since_precip hours since the last hour with snowfall > 0 (blank if none in the data)
"""
import csv
import json
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "Images_growth"
OUT = ROOT / "readings_growth.csv"
TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d{2})_(\d{2})_(\d{2})")
BASE = ("https://archive-api.open-meteo.com/v1/archive?latitude=40.75&longitude=-95.65"
        "&start_date={start}&end_date={end}&hourly=temperature_2m,snowfall,snow_depth"
        "&temperature_unit=fahrenheit&timezone=America/Chicago")
RANGES = [("2023-10-15", "2023-10-15"), ("2024-01-10", "2024-01-13")]

# hour (datetime) -> (temp_f, snowfall, snow_depth_m)
hours = {}
for start, end in RANGES:
    with urllib.request.urlopen(BASE.format(start=start, end=end), timeout=30) as r:
        h = json.load(r)["hourly"]
    for t, temp, snow, depth in zip(h["time"], h["temperature_2m"], h["snowfall"], h["snow_depth"]):
        hours[datetime.strptime(t, "%Y-%m-%dT%H:%M")] = (temp, snow, depth)


def blank(v):
    return "" if v is None else v


rows = []
for path in sorted(IMAGES.iterdir()):
    m = TIME_RE.search(path.name)
    if not m:
        continue
    t = datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}", "%Y-%m-%d %H:%M:%S")
    hour = (t + timedelta(minutes=30)).replace(minute=0, second=0)   # nearest hour
    temp, snow, depth = hours.get(hour, (None, None, None))
    snowy_hours = [h for h, v in hours.items() if h <= hour and (v[1] or 0) > 0]
    since = round(max((t - max(snowy_hours)).total_seconds() / 3600, 0), 2) if snowy_hours else None
    rows.append({
        "image": path.name,
        "air_temp_f": blank(temp),
        "snow_depth_m": blank(depth),
        "precipitating": bool(snow and snow > 0),
        "hours_since_precip": blank(since),
    })
    print(f"{path.name}: hour {hour:%Y-%m-%d %H:%M}  temp {temp}F  snowfall {snow}  depth {depth} m  since {since} h")

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["image", "air_temp_f", "snow_depth_m", "precipitating", "hours_since_precip"])
    w.writeheader()
    w.writerows(rows)
print(f"Saved {OUT}")
