"""
Frostline demo dashboard. OWNER: Samay.

Run (after python frostline.py):
    python -m streamlit run dashboard.py
Reads every output/<camera_id>/results.json written by frostline.py.
"""
import json
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from PIL import Image

HERE = Path(__file__).resolve().parent

st.set_page_config(page_title="Frostline", page_icon="❄️", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem;}
      .pill {display:inline-block;padding:6px 18px;border-radius:999px;font-weight:800;color:white;font-size:1.5rem;}
      .prio {font-size:1.5rem;font-weight:700;}
      /* Projector-friendly: bigger metric labels and numbers, no "..." cut-off */
      [data-testid="stMetricLabel"] p {font-size:1.3rem !important;font-weight:600;}
      [data-testid="stMetricValue"] {font-size:2.8rem !important;font-weight:700;line-height:1.15;}
      [data-testid="stMetricValue"] p {font-size:2.8rem !important;font-weight:700;line-height:1.15;}
      [data-testid="stMetricValue"] div, [data-testid="stMetricValue"] p {white-space:normal !important;
             overflow:visible !important;text-overflow:clip !important;}
      [data-testid="stMarkdownContainer"] p {font-size:1.15rem;}
      [data-testid="stSlider"] [data-testid="stSliderThumbValue"],
      [data-testid="stSlider"] [data-testid="stSliderTickBarMin"],
      [data-testid="stSlider"] [data-testid="stSliderTickBarMax"] {font-size:1.1rem;}
      .HIGH {background:#d62828;} .MEDIUM {background:#f77f00;} .LOW {background:#2a9d8f;}
      .story {font-size:2rem;font-weight:800;color:white;padding:14px 22px;border-radius:10px;margin:6px 0 10px 0;}
      .part1 {background:#1d4e89;} .part2 {background:#7b2cbf;}
      .sign {background:#111;color:#ffb703;font-family:monospace;font-size:1.8rem;
             padding:16px 20px;border-radius:8px;letter-spacing:1px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("❄️ Frostline")
st.caption("States already own thousands of eyes on the road. Frostline teaches them to read the road.")

# --- Load every camera's results ------------------------------------------
cams = []
for f in sorted((HERE / "output").glob("*/results.json")):
    cams.append(json.loads(f.read_text(encoding="utf-8")))
if not cams:
    st.error("No results yet. Run `python frostline.py` first, then refresh this page.")
    st.stop()
cams.sort(key=lambda c: c.get("story_order", 99))

# Flatten into one timeline: (camera, snapshot)
STORY = "▶ Full storm story (all cameras)"
choice = st.radio("View", [STORY] + [c["name"] for c in cams], horizontal=True)
chosen = cams if choice == STORY else [c for c in cams if c["name"] == choice]
frames = [(c, s) for c in chosen for s in c["snapshots"]]

labels = [f"{s['time_local']}  ·  {c['short']}" for c, s in frames]

# --- Play button: steps the slider forward every 2 s ----------------------
ss = st.session_state
if ss.get("view") != choice:          # new view -> start from the beginning
    ss.view, ss.idx, ss.playing = choice, 0, False
if "next_idx" in ss:                  # Play advanced one step on the last run
    ss.idx = ss.pop("next_idx")
ss.idx = min(ss.get("idx", 0), len(frames) - 1)


def toggle_play():
    ss.playing = not ss.get("playing", False)
    if ss.playing and ss.idx >= len(frames) - 1:
        ss.idx = 0                    # at the end -> replay from the start


b_col, s_col = st.columns([1, 9])
with b_col:
    st.write("")
    st.button("⏸ Pause" if ss.get("playing") else "▶ Play", on_click=toggle_play, width="stretch")
with s_col:
    i = st.select_slider("Drag to play the storm", options=list(range(len(frames))), key="idx",
                         format_func=lambda k: labels[k])
cam, s = frames[i]

# --- Story banner (Full storm story view only) -----------------------------
STORY_BANNERS = {
    1: "Part 1: Snow builds up on the road",
    2: "Part 2: Plows clear the lanes, but it's still below freezing",
}
if choice == STORY and cam.get("story_order") in STORY_BANNERS:
    part = cam["story_order"]
    st.markdown(f"<div class='story part{part}'>{STORY_BANNERS[part]}</div>", unsafe_allow_html=True)

st.subheader(cam["name"])

# --- Camera vs what Frostline sees ----------------------------------------
left, right = st.columns(2)
with left:
    st.markdown("**Live camera**")
    img = Image.open(HERE / cam["image_folder"] / s["image"])
    if cam.get("camera_box"):
        img = img.crop(tuple(cam["camera_box"]))
    st.image(img, width="stretch")
with right:
    st.markdown("**What Frostline sees** (blue = snow on the travel lanes)")
    st.image(str(HERE / "output" / cam["camera_id"] / "overlays" / s["overlay"]), width="stretch")

# --- Key numbers -----------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Condition", s["condition"].title())
c2.metric("Lane snow cover", f"{s['lane_snow_cover_pct']:.0f}%")
c3.metric("Air temp", f"{s['air_temp_f']}°F" if s["air_temp_f"] != "" else "—")
c4.metric("Ground snow", f"{s['ground_snow_in']} in" if s["ground_snow_in"] != "" else "—")
c5.metric("Hazard score", f"{s['hazard_score']}/100")

st.markdown(
    f"<span class='prio'>Priority:</span> <span class='pill {s['priority']}'>{s['priority']}</span>"
    + ("&nbsp;&nbsp;<span class='pill HIGH'>⚠ ICE RISK: lanes clear but below freezing, pre-treat</span>"
       if s["ice_risk"] else ""),
    unsafe_allow_html=True,
)
if s["clip_label"]:
    st.markdown(
        f"**AI check (CLIP):** {s['clip_label']} ({float(s['clip_confidence']):.0%}) · "
        f"snow score {float(s['clip_snow_score']):.2f} · "
        + ("✅ both methods agree" if s["agreement"] == "agree" else "🟡 methods disagree: needs human review")
    )
else:
    st.caption("AI check (CLIP) not run. Run `python frostline.py` without --no-clip.")

# --- Suggested sign message ------------------------------------------------
st.markdown("#### Suggested 511 / message-sign text")
if s["sign_message"]:
    st.markdown(f"<div class='sign'>{s['sign_message']}</div>", unsafe_allow_html=True)
    if st.button("✅ Operator approves → send to 511", key=f"approve_{i}"):
        st.success(f"Sent at {s['time_local'][11:]} (demo). Nothing is posted without a human approving it.")
else:
    st.write("No message needed.")

st.divider()

# --- Chart for the current camera -----------------------------------------
df = pd.DataFrame(cam["snapshots"])
df["time"] = pd.to_datetime(df["time_local"], errors="coerce")
st.markdown("#### Lane snow cover over time")
base = alt.Chart(df).encode(x=alt.X("time:T", title="Local time", axis=alt.Axis(format="%b %d %H:%M", labelAngle=0, labelFontSize=15, titleFontSize=17)))
layers = [base.mark_line(point=True, color="#1f77b4", strokeWidth=3).encode(
    y=alt.Y("lane_snow_cover_pct:Q", title="Lane snow cover (%)", axis=alt.Axis(labelFontSize=15, titleFontSize=17), scale=alt.Scale(domain=[0, 100])),
    tooltip=["time_local", "lane_snow_cover_pct", "condition"])]
has_depth = pd.to_numeric(df["ground_snow_in"], errors="coerce").notna().any()
if has_depth:
    df["ground_snow_in"] = pd.to_numeric(df["ground_snow_in"], errors="coerce")
    layers.append(base.mark_line(point=alt.OverlayMarkDef(color="#999"), color="#999", strokeDash=[6, 4]).encode(
        y=alt.Y("ground_snow_in:Q", title="Ground snow depth (in)", axis=alt.Axis(labelFontSize=15, titleFontSize=17)), tooltip=["time_local", "ground_snow_in"]))
now_row = df[df["image"] == s["image"]]
layers.append(alt.Chart(now_row).mark_rule(color="#d62828").encode(x="time:T"))
chart = (alt.layer(*layers).resolve_scale(y="independent").properties(height=340))
st.altair_chart(chart, width="stretch")
if has_depth:
    st.caption("Blue: lane snow cover (left axis). Grey dashed: ground snow depth from the nearby weather station (right axis).")

first, last = cam["snapshots"][0], cam["snapshots"][-1]
hours = (df["time"].iloc[-1] - df["time"].iloc[0]).total_seconds() / 3600 if df["time"].notna().all() else 0
direction = "rose" if last["lane_snow_cover_pct"] > first["lane_snow_cover_pct"] else "fell"
report = (f"**Storm report ({cam['short']}):** lane snow cover {direction} from "
          f"{first['lane_snow_cover_pct']:.0f}% to {last['lane_snow_cover_pct']:.0f}% in {hours:.1f} hours.")
if last["ice_risk"]:
    report += f" Lanes are open, but it is {last['air_temp_f']}°F, so Frostline keeps an ice-risk warning here."
st.info(report)

# --- Treat-first list + map ------------------------------------------------
m1, m2 = st.columns([3, 2])
with m1:
    st.markdown("#### Treat-first list (latest snapshot per camera)")
    latest = pd.DataFrame([{**c["snapshots"][-1], "camera": c["short"]} for c in cams])
    cols = ["camera", "time_local", "condition", "lane_snow_cover_pct", "clip_label", "hazard_score", "priority", "ice_risk"]
    st.dataframe(latest.sort_values("hazard_score", ascending=False)[cols], hide_index=True, width="stretch")
with m2:
    st.markdown("#### Cameras")
    pts = pd.DataFrame([{"lat": c["lat"], "lon": c["lon"]} for c in cams if c.get("lat")])
    if not pts.empty:
        st.map(pts, zoom=6)

# --- Play: wait 2 s, then move to the next snapshot -----------------------
if ss.get("playing"):
    if i < len(frames) - 1:
        time.sleep(2)
        ss.next_idx = i + 1
    else:
        ss.playing = False            # reached the end
    st.rerun()
