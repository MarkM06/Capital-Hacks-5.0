"""Deterministic plan-review rule engine.

The AI never decides whether a project complies. It turns messy applicant
input into ``ProjectParams``; this module checks those numbers against the
city's objective standards and cites the code section for every finding.
That keeps decisions explainable, reproducible and auditable.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from .models import Finding, Parcel, ProjectParams, ReviewResult

DATA_DIR = Path(__file__).parent / "data"

# Project types that put new structure on the ground and so need dimensional checks.
EXTERIOR_TYPES = {"new_construction", "addition", "adu", "accessory_structure"}

OUTCOME_LABELS = {
    "approvable": "Eligible for expedited ministerial approval (UDC 2.7)",
    "corrections_required": "Corrections required before approval",
    "incomplete": "Incomplete - more information needed",
    "hearing_required": "Complies, but requires a public hearing (UDC 2.8)",
}


@lru_cache(maxsize=1)
def load_code() -> dict:
    return json.loads((DATA_DIR / "zoning_code.json").read_text())


@lru_cache(maxsize=1)
def _parcels() -> dict:
    raw = json.loads((DATA_DIR / "parcels.json").read_text())["parcels"]
    return {p["address"].lower(): Parcel(**p) for p in raw}


def all_parcels() -> List[Parcel]:
    return list(_parcels().values())


def find_parcel(address: str) -> Optional[Parcel]:
    key = address.strip().lower()
    parcels = _parcels()
    if key in parcels:
        return parcels[key]
    for addr, parcel in parcels.items():  # forgiving match: "412 maple" -> "412 Maple St"
        if key and (key in addr or addr in key):
            return parcel
    return None


def _fmt(n: float) -> str:
    return f"{n:,.2f}".rstrip("0").rstrip(".")


def _q(n: float, unit: str) -> str:
    """Format a quantity with its unit: 45%, 20 ft, 0.53 FAR."""
    return f"{_fmt(n)}{unit}" if unit == "%" else f"{_fmt(n)} {unit}"


class _Review:
    def __init__(self) -> None:
        self.findings: List[Finding] = []

    def add(self, rule, section, status, title, detail, required=None, proposed=None):
        self.findings.append(
            Finding(rule=rule, section=section, status=status, title=title, detail=detail,
                    required=required, proposed=proposed)
        )

    def max_check(self, rule, section, title, value, limit, unit, missing_detail):
        if value is None:
            self.add(rule, section, "info_needed", title, missing_detail, required=f"<= {_q(limit, unit)}")
        elif value <= limit:
            self.add(rule, section, "pass", title, f"{_q(value, unit)} is within the {_q(limit, unit)} limit.",
                     required=f"<= {_q(limit, unit)}", proposed=f"{_q(value, unit)}")
        else:
            self.add(rule, section, "fail", title,
                     f"{_q(value, unit)} exceeds the {_q(limit, unit)} maximum by {_q(value - limit, unit)}. "
                     f"Revise the design or apply for a variance (UDC 2.9).",
                     required=f"<= {_q(limit, unit)}", proposed=f"{_q(value, unit)}")

    def min_check(self, rule, section, title, value, minimum, unit, missing_detail):
        if value is None and minimum == 0:
            self.add(rule, section, "pass", title, "No minimum applies in this district.", required="none")
        elif value is None:
            self.add(rule, section, "info_needed", title, missing_detail, required=f">= {_q(minimum, unit)}")
        elif value >= minimum:
            self.add(rule, section, "pass", title, f"{_q(value, unit)} meets the {_q(minimum, unit)} minimum.",
                     required=f">= {_q(minimum, unit)}", proposed=f"{_q(value, unit)}")
        else:
            self.add(rule, section, "fail", title,
                     f"{_q(value, unit)} is short of the {_q(minimum, unit)} minimum by {_q(minimum - value, unit)}.",
                     required=f">= {_q(minimum, unit)}", proposed=f"{_q(value, unit)}")


def review(params: ProjectParams, parcel: Parcel, code: Optional[dict] = None) -> ReviewResult:
    code = code or load_code()
    district = code["districts"].get(parcel.district)
    if district is None:
        raise ValueError(f"Unknown zoning district {parcel.district!r}")
    sec = district["section"]
    adu_rules = code["adu"]
    r = _Review()
    ptype = params.project_type
    use = "adu" if ptype == "adu" else params.use
    inferred_use = False
    if use is None and ptype in ("addition", "accessory_structure") and parcel.existing_units:
        # Expanding an existing home: the use doesn't change.
        use = "single_family" if parcel.existing_units == 1 else "multifamily"
        inferred_use = True
    is_adu = use == "adu"

    # 1. Project type -----------------------------------------------------------
    if ptype is None:
        r.add("project_type", "UDC 2.4", "info_needed", "Project type",
              "State what kind of work this is (new building, addition, ADU, change of use, tenant improvement).")

    # 2. Land use ---------------------------------------------------------------
    use_section = adu_rules["section"] if is_adu else sec
    if use is None:
        r.add("use", sec, "info_needed", "Land use", "State the proposed use of the space (e.g. single-family home, retail, office).")
    elif use in district["permitted_uses"]:
        r.add("use", use_section, "pass", "Land use",
              f"'{use.replace('_', ' ')}' is permitted by right in {parcel.district} ({district['name']})."
              + (" (Use carried over from the existing home.)" if inferred_use else ""))
    elif use in district["conditional_uses"]:
        r.add("use", "UDC 2.8", "discretionary", "Land use",
              f"'{use.replace('_', ' ')}' is a conditional use in {parcel.district}. A Conditional Use Permit and "
              f"Planning Commission hearing are required.")
    else:
        r.add("use", sec, "fail", "Land use",
              f"'{use.replace('_', ' ')}' is not allowed in {parcel.district} ({district['name']}). "
              f"A rezoning would be required.")

    # 3. Density ----------------------------------------------------------------
    per_unit = district.get("lot_area_per_unit_sqft")
    if params.new_dwelling_units and not is_adu:
        total_units = parcel.existing_units + params.new_dwelling_units
        if ptype == "new_construction":
            total_units = params.new_dwelling_units
        if per_unit:
            allowed = math.floor(parcel.lot_area_sqft / per_unit)
            r.max_check("density", sec, "Density (dwelling units)", total_units, allowed, "units", "")
        else:
            r.add("density", sec, "discretionary", "Density (dwelling units)",
                  f"{parcel.district} sets no by-right residential density; units are reviewed through the CUP.")

    exterior = ptype in EXTERIOR_TYPES
    if exterior:
        # 4. Minimum lot size for new buildings -------------------------------
        if ptype == "new_construction":
            r.min_check("min_lot_area", sec, "Minimum lot area", parcel.lot_area_sqft,
                        district["min_lot_area_sqft"], "sq ft", "")

        # 5. Height & stories -------------------------------------------------
        height_limit = adu_rules["max_height_ft"] if is_adu else district["max_height_ft"]
        r.max_check("height", adu_rules["section"] if is_adu else sec, "Building height", params.height_ft,
                    height_limit, "ft", "Provide the building height (grade to highest point) on the elevations.")
        if params.stories is not None and not is_adu:
            r.max_check("stories", sec, "Stories", params.stories, district["max_stories"], "stories", "")

        # 6. Setbacks ---------------------------------------------------------
        sb = district["setbacks_ft"]
        side_req, rear_req = sb["side"], sb["rear"]
        if is_adu or ptype == "accessory_structure":
            side_req = rear_req = adu_rules["min_side_rear_setback_ft"]
        sb_section = adu_rules["section"] if is_adu else sec
        missing = "Dimension this setback on the site plan."
        # Rear additions / backyard ADUs rarely move the front wall, so only demand it for new buildings.
        if params.front_setback_ft is not None or ptype == "new_construction":
            r.min_check("setback_front", sec, "Front setback", params.front_setback_ft, sb["front"], "ft", missing)
        r.min_check("setback_side", sb_section, "Side setback", params.side_setback_ft, side_req, "ft", missing)
        r.min_check("setback_rear", sb_section, "Rear setback", params.rear_setback_ft, rear_req, "ft", missing)

        # 7. Lot coverage -----------------------------------------------------
        base_fp = 0 if ptype == "new_construction" else parcel.existing_footprint_sqft
        if params.footprint_sqft is None:
            r.add("lot_coverage", sec, "info_needed", "Lot coverage",
                  "Provide the building footprint of the new work in square feet.",
                  required=f"<= {district['max_lot_coverage_pct']}%")
        else:
            pct = (base_fp + params.footprint_sqft) / parcel.lot_area_sqft * 100
            r.max_check("lot_coverage", sec, "Lot coverage", round(pct, 1), district["max_lot_coverage_pct"], "%", "")
            r.findings[-1].detail += (f" ({_fmt(base_fp)} existing + {_fmt(params.footprint_sqft)} new sq ft on a "
                                      f"{_fmt(parcel.lot_area_sqft)} sq ft lot.)")

    # 8. Floor area ratio -------------------------------------------------------
    if exterior and params.floor_area_sqft is not None:
        base_fa = 0 if ptype == "new_construction" else parcel.existing_floor_area_sqft
        far = (base_fa + params.floor_area_sqft) / parcel.lot_area_sqft
        r.max_check("far", sec, "Floor area ratio (FAR)", round(far, 2), district["max_far"], "FAR", "")
    elif exterior and not is_adu:
        r.add("far", sec, "info_needed", "Floor area ratio (FAR)", "Provide the gross floor area of the new work.",
              required=f"<= {district['max_far']} FAR")

    # 9. ADU-specific standards -------------------------------------------------
    if is_adu:
        cap = min(adu_rules["max_floor_area_sqft"], parcel.existing_floor_area_sqft * adu_rules["max_pct_of_primary"] / 100)
        r.max_check("adu_size", adu_rules["section"], "ADU floor area", params.floor_area_sqft, cap, "sq ft",
                    "Provide the ADU's floor area.")
        r.findings[-1].detail += (f" (Cap is the lesser of {adu_rules['max_floor_area_sqft']} sq ft or "
                                  f"{adu_rules['max_pct_of_primary']}% of the {_fmt(parcel.existing_floor_area_sqft)} sq ft primary home.)")

    # 10. Parking ---------------------------------------------------------------
    pk = code["parking"]
    required_spaces = 0.0
    if use in pk["per_unit"] and params.new_dwelling_units:
        required_spaces = pk["per_unit"][use] * params.new_dwelling_units
    elif use in pk["per_1000_sqft"] and params.floor_area_sqft:
        required_spaces = pk["per_1000_sqft"][use] * params.floor_area_sqft / 1000
    if parcel.district == "MU":
        required_spaces *= (100 - pk["mu_reduction_pct"]) / 100
    required_spaces = math.ceil(required_spaces - 1e-9)
    if required_spaces > 0:
        r.min_check("parking", pk["section"], "Off-street parking", params.parking_spaces, required_spaces, "spaces",
                    f"Show the off-street parking provided; {required_spaces} spaces are required.")
    elif is_adu:
        r.add("parking", adu_rules["section"], "pass", "Off-street parking", "No off-street parking is required for an ADU.")

    # 11. Submittal completeness ------------------------------------------------
    sub = code["submittals"]
    if ptype in sub["by_project_type"]:
        needed = sub["by_project_type"][ptype]
        missing_docs = [d for d in needed if d not in params.submittals]
        if missing_docs:
            r.add("submittals", sub["section"], "info_needed", "Required documents",
                  "Missing: " + "; ".join(sub["labels"][d] for d in missing_docs) + ".",
                  required=", ".join(needed), proposed=", ".join(params.submittals) or "none")
        else:
            r.add("submittals", sub["section"], "pass", "Required documents", "All required submittals are attached.")

    statuses = [f.status for f in r.findings]
    counts = {s: statuses.count(s) for s in ("pass", "fail", "info_needed", "discretionary")}
    if counts["fail"]:
        outcome = "corrections_required"
    elif counts["info_needed"]:
        outcome = "incomplete"
    elif counts["discretionary"]:
        outcome = "hearing_required"
    else:
        outcome = "approvable"
    return ReviewResult(outcome=outcome, outcome_label=OUTCOME_LABELS[outcome], findings=r.findings, counts=counts)
