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
    # Snow building up. Hiroshi: fill in once the images are in Images_growth/
    "growth": {
        "name": "TODO: road + location of the snow-growth camera",
        "short": "TODO SHORT NAME",
        "folder": "Images_growth",
        "readings": "",
        "utc_offset_hours": -5,
        "lat": 0.0, "lon": 0.0,
        "camera_box": None,        # None = use the whole image
        "lanes": None,             # REQUIRED: list of (x, y) points
        "snow_reference": None,    # list of (x, y) points, OR set snow_threshold
        "snow_threshold": None,    # e.g. 170 (only if no snow_reference)
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
