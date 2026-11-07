ADU = ("Detached ADU in the backyard: one-story, 600 sq ft, 16 ft tall, 6 ft from the side property line and "
       "8 ft from the rear property line. Site plan, floor plans, elevations and utility plan attached.")


def test_pages_and_status(client):
    assert client.get("/").status_code == 200
    assert client.get("/staff").status_code == 200
    s = client.get("/api/status").json()
    assert s["mode"] == "offline" and "Capitol Falls" in s["jurisdiction"]


def test_demo_queue_is_seeded_with_mixed_outcomes(client):
    apps = client.get("/api/applications").json()
    assert len(apps) == 6
    outcomes = {a["review"]["outcome"] for a in apps}
    assert {"approvable", "corrections_required", "hearing_required"} <= outcomes


def test_precheck_does_not_save(client):
    before = len(client.get("/api/applications").json())
    r = client.post("/api/precheck", json={"address": "412 Maple St", "description": ADU})
    assert r.status_code == 200
    assert r.json()["review"]["outcome"] == "approvable"
    assert len(client.get("/api/applications").json()) == before


def test_unknown_address_404(client):
    r = client.post("/api/precheck", json={"address": "1 Nowhere Ln", "description": "x"})
    assert r.status_code == 404 and "Maple" in r.json()["detail"]


def test_applicant_edited_params_override_extraction(client):
    params = {"project_type": "adu", "use": "adu", "height_ft": 30, "floor_area_sqft": 500, "footprint_sqft": 500,
              "side_setback_ft": 5, "rear_setback_ft": 5, "submittals": []}
    r = client.post("/api/precheck", json={"address": "412 Maple St", "description": ADU, "params": params}).json()
    assert r["extraction_source"] == "applicant" and r["review"]["outcome"] == "corrections_required"


def test_full_staff_workflow(client):
    a = client.post("/api/applications", json={"address": "88 Birch Ave", "applicant_name": "Luis",
                                               "description": "Rear addition, 400 sq ft footprint and floor area, "
                                                              "24 ft tall, 15 ft from the rear and 5 ft from the side."}).json()
    assert a["status"] in ("needs_corrections", "needs_info")

    # Approving with open findings is blocked.
    assert client.post(f"/api/applications/{a['id']}/decision", json={"action": "approve"}).status_code == 409

    letter = client.post(f"/api/applications/{a['id']}/letter").json()
    assert letter["letter_source"] == "template" and "Rear setback" in letter["letter"]

    edited = client.put(f"/api/applications/{a['id']}/letter", json={"letter": "Edited by reviewer"}).json()
    assert edited["letter"] == "Edited by reviewer" and edited["letter_source"] == "staff"

    # Reviewer corrects the data after a revised plan: now fully compliant.
    fixed = dict(a["params"], rear_setback_ft=20,
                 submittals=["site_plan", "floor_plans", "elevations", "structural_calcs"])
    rerun = client.put(f"/api/applications/{a['id']}/params", json=fixed).json()
    assert rerun["review"]["outcome"] == "approvable" and rerun["status"] == "ready_to_approve"

    done = client.post(f"/api/applications/{a['id']}/decision", json={"action": "approve"}).json()
    assert done["status"] == "approved" and done["decided_at"]
    assert [h["event"] for h in done["history"]][-1] == "Permit approved"


def test_ask_and_metrics(client):
    r = client.post("/api/ask", json={"question": "Do I need a permit for a fence?"}).json()
    assert "UDC 6.5" in r["citations"]
    assert client.post("/api/ask", json={"question": "  "}).status_code == 400
    m = client.get("/api/metrics").json()
    assert m["total"] == 6 and m["avg_days_to_decision"] is not None and m["staff_hours_saved"] == 9.0
