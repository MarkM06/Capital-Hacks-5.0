"""
Camera setup. OWNER: Hiroshi.

One entry per camera. All coordinates are pixels in the ORIGINAL snapshot
(open an image with `python tools/grid.py <image>` to read coordinates).

Fields:
  name              shown on the dashboard
  short             used in sign messages
  folder            folder of snapshots (filenames must contain YYYY-MM-DD-HH_MM_SS)
  readings          CSV with air_temp_f, snow_depth_m, precipitating, hours_since_precip
                    per image (optional: leave "" if you don't have it)
  utc_offset_hours  filenames are UTC; this converts to local time
  camera_box        (left, top, right, bottom) of the actual camera picture
                    (cuts off any text header)
  lanes             outline of the travel lanes to measure
  snow_reference    a patch that is snow in EVERY frame (median / shoulder snowbank).
                    A lane pixel counts as snow if it is >= 80% as bright as this patch.
  snow_threshold    use INSTEAD of snow_reference when no patch is snowy in every frame
                    (e.g. the storm starts on a bare road): fixed gray level 0-255,
                    lane pixels at least this bright count as snow. Check the overlays!
  story_order       order in the demo: 1 = shown first
"""

CAMERAS = {
    # Snow building up. Iowa DOT camera; times on the images are already local (Central)
    "growth": {
        "name": "I-29 at Sidney (RWIS39), Iowa",
        "short": "I-29 SIDNEY",
        "folder": "Images_growth",
        "readings": "readings_growth.csv",   # Open-Meteo history, made by tools/fetch_weather.py
        "utc_offset_hours": 0,
        "lat": 40.75, "lon": -95.65,
        "camera_box": (0, 32, 1000, 566),   # cuts off the black text bar at the top
        # Travel lanes nearest the camera, between the white edge line and the yellow median line
        "lanes": [(195, 250), (295, 250), (990, 557), (990, 566), (530, 566)],
        # Camera angle moves between frames: per-image outlines (falls back to "lanes")
        "lanes_per_image": {
            "I29_Sidney_2024-01-13-12_54_57.png": [(215, 250), (300, 250), (990, 555), (990, 566), (548, 566)],
        },
        "snow_reference": None,
        # Exposure changes a lot between days, so frames that have snow use the snowy verge
        # left of the road IN THAT FRAME as the reference (same 80% rule as the LIE camera)
        "snow_reference_per_image": {
            "I29_Sidney_2024-01-12-07_51_48.png": [(20, 330), (110, 330), (110, 470), (20, 470)],
            "I29_Sidney_2024-01-12-12_53_53.png": [(20, 330), (110, 330), (110, 470), (20, 470)],
            "I29_Sidney_2024-01-13-12_54_57.png": [(20, 330), (110, 330), (110, 470), (20, 470)],
        },
        "snow_threshold": 200,     # frames without a reference (Oct: no snow anywhere): fixed brightness
        "story_order": 1,
    },
    # Plows clearing the road. Done and tested: lanes 100 -> 88 -> 24 -> 11 -> 12 %
    "lie_clearing": {
        "name": "I-495 Long Island Expwy, west of CR 101 (Sills Rd), NY",
        "short": "LIE W OF CR 101",
        "folder": "Images",
        "readings": "station_readings.csv",
        "utc_offset_hours": -5,
        "lat": 40.81, "lon": -72.99,
        "camera_box": (38, 112, 464, 432),
        "lanes": [(238, 215), (252, 215), (464, 355), (464, 432), (345, 432)],
        "snow_reference": [(200, 385), (318, 385), (330, 432), (185, 432)],
        "story_order": 2,
    },
}
