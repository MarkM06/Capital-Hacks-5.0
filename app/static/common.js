// Shared helpers for the resident portal and the staff console.

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(msg) {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("show");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2600);
}

async function busy(btn, fn) {
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = "Working…";
  try { return await fn(); } catch (e) { toast(e.message); } finally { btn.disabled = false; btn.textContent = label; }
}

async function loadStatusBadge() {
  const el = document.getElementById("ai-badge");
  if (!el) return;
  try {
    const s = await api("/api/status");
    el.textContent = s.mode === "claude" ? `AI: Claude (${s.model})` : "AI: offline heuristics";
    el.classList.toggle("claude", s.mode === "claude");
    el.title = s.mode === "claude" ? "Language tasks run on Claude" : "Set ANTHROPIC_API_KEY to enable Claude";
  } catch { el.textContent = "AI: unknown"; }
}

const STATUS_LABEL = { pass: "Complies", fail: "Fix needed", info_needed: "Missing info", discretionary: "Hearing" };

function renderReview(review) {
  const items = review.findings
    .slice()
    .sort((a, b) => order(a.status) - order(b.status))
    .map((f) => `<li><span class="pill ${f.status}">${STATUS_LABEL[f.status]}</span>
        <div><span class="title">${esc(f.title)}</span><span class="cite">${esc(f.section)}</span>
        <div class="small">${esc(f.detail)}</div></div></li>`).join("");
  return `<div class="outcome ${review.outcome}">${esc(review.outcome_label)}</div><ul class="findings">${items}</ul>`;
  function order(s) { return { fail: 0, info_needed: 1, discretionary: 2, pass: 3 }[s]; }
}

const PROJECT_TYPES = ["new_construction", "addition", "adu", "change_of_use", "tenant_improvement", "accessory_structure"];
const USES = ["single_family", "duplex", "triplex", "multifamily", "adu", "home_occupation", "accessory_structure", "retail",
  "restaurant", "office", "personal_services", "daycare", "place_of_worship", "bar", "light_manufacturing", "drive_through"];
const SUBMITTALS = {
  site_plan: "Site plan", floor_plans: "Floor plans", elevations: "Elevations", structural_calcs: "Structural calcs",
  energy_compliance: "Energy compliance", survey: "Survey", utility_plan: "Utility plan",
  occupancy_letter: "Occupancy letter", parking_plan: "Parking plan",
};
const NUM_FIELDS = [
  ["new_dwelling_units", "New dwelling units"], ["height_ft", "Height (ft)"], ["stories", "Stories"],
  ["footprint_sqft", "New footprint (sq ft)"], ["floor_area_sqft", "New floor area (sq ft)"],
  ["front_setback_ft", "Front setback (ft)"], ["side_setback_ft", "Side setback (ft)"],
  ["rear_setback_ft", "Rear setback (ft)"], ["parking_spaces", "Parking spaces"],
];
const pretty = (s) => s.replace(/_/g, " ");

// Editable form for the extracted project facts. Empty = "not stated".
function renderParamsForm(container, params) {
  const sel = (name, opts, val) => `<select name="${name}"><option value="">— not stated —</option>${
    opts.map((o) => `<option value="${o}" ${o === val ? "selected" : ""}>${pretty(o)}</option>`).join("")}</select>`;
  container.innerHTML = `
    <div class="params">
      <div><label>Project type</label>${sel("project_type", PROJECT_TYPES, params.project_type)}</div>
      <div><label>Use</label>${sel("use", USES, params.use)}</div>
      ${NUM_FIELDS.map(([k, l]) => `<div><label>${l}</label><input type="number" step="any" name="${k}" value="${params[k] ?? ""}" placeholder="not stated"></div>`).join("")}
    </div>
    <label>Documents attached</label>
    <div class="checks">${Object.entries(SUBMITTALS).map(([k, l]) =>
      `<label><input type="checkbox" name="submittals" value="${k}" ${params.submittals.includes(k) ? "checked" : ""}>${l}</label>`).join("")}</div>
    <input type="hidden" name="summary" value="${esc(params.summary || "")}">`;
}

function readParamsForm(container) {
  const get = (n) => container.querySelector(`[name="${n}"]`).value;
  const p = { project_type: get("project_type") || null, use: get("use") || null, summary: get("summary") };
  for (const [k] of NUM_FIELDS) {
    const v = get(k);
    p[k] = v === "" ? null : (k === "new_dwelling_units" || k === "parking_spaces" ? parseInt(v, 10) : parseFloat(v));
  }
  p.submittals = [...container.querySelectorAll('[name="submittals"]:checked')].map((c) => c.value);
  return p;
}

function renderParcel(p) {
  return `<div class="parcel">
    <div><b>Parcel</b>${esc(p.parcel_id)}</div><div><b>Zoning</b>${esc(p.district)}</div>
    <div><b>Lot area</b>${p.lot_area_sqft.toLocaleString()} sq ft</div>
    <div><b>Existing floor area</b>${p.existing_floor_area_sqft.toLocaleString()} sq ft</div>
    <div><b>Existing footprint</b>${p.existing_footprint_sqft.toLocaleString()} sq ft</div>
    <div><b>Existing units</b>${p.existing_units}</div></div>`;
}
