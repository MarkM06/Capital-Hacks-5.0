from types import SimpleNamespace

from app import ai
from app.models import ProjectParams, ReviewResult
from app.zoning import find_parcel, review


def test_heuristic_extracts_adu_description():
    p = ai.heuristic_extract(
        "Detached ADU in the backyard: one-story, 600 sq ft, 16 ft tall, 6 ft from the side property line and "
        "8 ft from the rear property line. Site plan, floor plans, elevations and utility plan attached.")
    assert p.project_type == "adu" and p.use == "adu"
    assert p.height_ft == 16 and p.floor_area_sqft == 600 and p.stories == 1
    assert p.side_setback_ft == 6 and p.rear_setback_ft == 8
    assert set(p.submittals) == {"site_plan", "floor_plans", "elevations", "utility_plan"}


def test_heuristic_change_of_use_and_parking():
    p = ai.heuristic_extract("Convert the existing 2,000 sq ft retail space into a coffee shop. We have 6 parking spaces.")
    assert p.project_type == "change_of_use" and p.use == "restaurant"
    assert p.floor_area_sqft == 2000 and p.parking_spaces == 6


def test_heuristic_dimensions_and_units():
    p = ai.heuristic_extract("Build an addition: one-story 20 ft by 30 ft sunroom, 14 ft tall.")
    assert p.project_type == "addition" and p.footprint_sqft == 600
    q = ai.heuristic_extract("New 5-story building with 20 residential units over ground floor retail.")
    assert q.new_dwelling_units == 20 and q.use == "multifamily" and q.stories == 5


def test_template_letter_lists_issues_and_what_complies():
    parcel = find_parcel("88 Birch Ave")
    p = ProjectParams(project_type="addition", use="single_family", height_ft=40, footprint_sqft=100,
                      floor_area_sqft=100, side_setback_ft=5, rear_setback_ft=25)
    r = review(p, parcel)
    text = ai.template_letter({"id": 7, "applicant_name": "Luis", "address": parcel.address}, r)
    assert "#7" in text and "Building height" in text and "UDC 4.3" in text
    assert "already comply" in text


def test_keyword_answer_cites_adu_section():
    answer, cites, source = ai.keyword_answer("How big can an ADU be?")
    assert source == "keyword" and "UDC 6.3" in cites
    assert "UDC 6.3" in ai.keyword_answer("How big can a backyard cottage be?")[1]


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return self.response

    parse = create


def fake_client(monkeypatch, response):
    msgs = FakeMessages(response)
    monkeypatch.setattr(ai, "_get_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=msgs)))
    return msgs


def test_claude_extraction_request_shape(monkeypatch):
    parsed = ProjectParams(project_type="adu", use="adu", height_ft=15)
    msgs = fake_client(monkeypatch, SimpleNamespace(stop_reason="end_turn", parsed_output=parsed, content=[]))
    params, source = ai.extract_params("an adu", find_parcel("412 Maple St"))
    assert source == "claude" and params.height_ft == 15
    call = msgs.calls[0]
    assert call["model"] == ai.MODEL
    assert call["output_format"] is ProjectParams
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in call and "temperature" not in call
    assert "R-1" in call["messages"][0]["content"]


def test_claude_refusal_falls_back_to_heuristics(monkeypatch):
    fake_client(monkeypatch, SimpleNamespace(stop_reason="refusal", stop_details=None, parsed_output=None, content=[]))
    params, source = ai.extract_params("Detached ADU, 16 ft tall")
    assert source == "heuristic" and params.project_type == "adu"


def test_claude_error_falls_back_to_template(monkeypatch):
    class Boom:
        def create(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr(ai, "_get_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=Boom())))
    r = ReviewResult(outcome="approvable", outcome_label="ok", findings=[], counts={})
    text, source = ai.draft_letter({"id": 1, "applicant_name": "A", "address": "x"}, r)
    assert source == "template" and "Dear A" in text


def test_ask_code_caches_code_corpus(monkeypatch):
    block = SimpleNamespace(type="text", text="ADUs are capped at 800 sq ft [UDC 6.3].")
    msgs = fake_client(monkeypatch, SimpleNamespace(stop_reason="end_turn", content=[block]))
    answer, cites, source = ai.ask_code("adu size?")
    assert source == "claude" and cites == ["UDC 6.3"]
    system = msgs.calls[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"} and "UDC 9.1" in system[0]["text"]
