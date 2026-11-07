from app.models import ProjectParams
from app.zoning import find_parcel, review


def statuses(result):
    return {f.rule: f.status for f in result.findings}


ADU_DOCS = ["site_plan", "floor_plans", "elevations", "utility_plan"]


def test_compliant_adu_is_approvable():
    p = ProjectParams(project_type="adu", height_ft=16, footprint_sqft=600, floor_area_sqft=600,
                      side_setback_ft=5, rear_setback_ft=8, submittals=ADU_DOCS)
    r = review(p, find_parcel("412 Maple St"))
    assert r.outcome == "approvable", r.findings
    s = statuses(r)
    assert s["use"] == "pass" and s["adu_size"] == "pass" and s["parking"] == "pass"


def test_adu_size_cap_is_lesser_of_800_or_half_primary():
    # 88 Birch Ave primary home is 1,400 sq ft -> cap is 700, not 800.
    p = ProjectParams(project_type="adu", height_ft=16, footprint_sqft=750, floor_area_sqft=750,
                      side_setback_ft=5, rear_setback_ft=8, submittals=ADU_DOCS)
    r = review(p, find_parcel("88 Birch Ave"))
    assert statuses(r)["adu_size"] == "fail"
    assert r.outcome == "corrections_required"


def test_adu_height_uses_adu_limit_not_district_limit():
    p = ProjectParams(project_type="adu", height_ft=24, footprint_sqft=500, floor_area_sqft=500,
                      side_setback_ft=5, rear_setback_ft=8, submittals=ADU_DOCS)
    assert statuses(review(p, find_parcel("412 Maple St")))["height"] == "fail"


def test_rear_setback_violation_cites_district_section():
    p = ProjectParams(project_type="addition", use="single_family", height_ft=20, footprint_sqft=300,
                      floor_area_sqft=300, side_setback_ft=8, rear_setback_ft=10,
                      submittals=["site_plan", "floor_plans", "elevations", "structural_calcs"])
    r = review(p, find_parcel("412 Maple St"))
    rear = next(f for f in r.findings if f.rule == "setback_rear")
    assert rear.status == "fail" and rear.section == "UDC 4.2"
    assert "15 ft" in rear.detail  # short by 15 ft (25 required)


def test_lot_coverage_counts_existing_footprint():
    # 19 Oak Ct: 2,100 existing + 400 new on 6,000 = 41.7% > 40%.
    p = ProjectParams(project_type="addition", use="single_family", height_ft=14, footprint_sqft=400,
                      floor_area_sqft=0, side_setback_ft=8, rear_setback_ft=30)
    assert statuses(review(p, find_parcel("19 Oak Ct")))["lot_coverage"] == "fail"


def test_conditional_use_requires_hearing():
    p = ProjectParams(project_type="change_of_use", use="bar", floor_area_sqft=1000, parking_spaces=10,
                      submittals=["floor_plans", "occupancy_letter", "parking_plan"])
    r = review(p, find_parcel("230 Main St"))
    assert r.outcome == "hearing_required"
    assert statuses(r)["use"] == "discretionary"


def test_prohibited_use_fails():
    p = ProjectParams(project_type="change_of_use", use="light_manufacturing", floor_area_sqft=1000)
    assert statuses(review(p, find_parcel("412 Maple St")))["use"] == "fail"


def test_missing_values_are_flagged_not_guessed():
    r = review(ProjectParams(project_type="new_construction", use="single_family", new_dwelling_units=1),
               find_parcel("77 Riverside Dr"))
    assert r.outcome == "incomplete"
    s = statuses(r)
    assert s["height"] == "info_needed" and s["setback_side"] == "info_needed" and s["submittals"] == "info_needed"


def test_mu_parking_reduction_and_zero_setbacks():
    # 20 units * 1 space * 50% MU reduction = 10 spaces; MU has no front/side setback.
    p = ProjectParams(project_type="new_construction", use="multifamily", new_dwelling_units=20, height_ft=60,
                      stories=5, footprint_sqft=6000, floor_area_sqft=30000, rear_setback_ft=12, parking_spaces=10,
                      submittals=["site_plan", "floor_plans", "elevations", "structural_calcs", "energy_compliance", "survey"])
    r = review(p, find_parcel("1500 Commerce Blvd"))
    assert r.outcome == "approvable", [f for f in r.findings if f.status != "pass"]


def test_density_limit():
    # 9,000 sq ft R-3 lot / 1,000 per unit = 9 units max.
    p = ProjectParams(project_type="new_construction", use="multifamily", new_dwelling_units=12)
    assert statuses(review(p, find_parcel("77 Riverside Dr")))["density"] == "fail"


def test_addition_inherits_existing_residential_use():
    p = ProjectParams(project_type="addition", height_ft=14)
    s = statuses(review(p, find_parcel("19 Oak Ct")))
    assert s["use"] == "pass"


def test_parcel_lookup_is_forgiving():
    assert find_parcel("412 maple").parcel_id == "014-220-07"
    assert find_parcel("nowhere") is None
