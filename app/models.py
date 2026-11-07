"""Data models shared by the rule engine, the AI layer and the API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ProjectType = Literal[
    "new_construction",
    "addition",
    "adu",
    "change_of_use",
    "tenant_improvement",
    "accessory_structure",
]

UseType = Literal[
    "single_family",
    "duplex",
    "triplex",
    "multifamily",
    "adu",
    "home_occupation",
    "accessory_structure",
    "retail",
    "restaurant",
    "office",
    "personal_services",
    "daycare",
    "place_of_worship",
    "bar",
    "light_manufacturing",
    "drive_through",
]

SubmittalType = Literal[
    "site_plan",
    "floor_plans",
    "elevations",
    "structural_calcs",
    "energy_compliance",
    "survey",
    "utility_plan",
    "occupancy_letter",
    "parking_plan",
]


class ProjectParams(BaseModel):
    """Objective facts about a proposed project.

    Every dimensional field is optional: the AI extracts what the applicant
    actually stated and leaves the rest null so the rule engine can flag it as
    missing information instead of guessing.
    """

    project_type: Optional[ProjectType] = Field(None, description="Kind of permit being requested")
    use: Optional[UseType] = Field(None, description="Proposed land use of the new/changed space")
    new_dwelling_units: Optional[int] = Field(None, description="Dwelling units ADDED by this project (an ADU is not counted here)")
    height_ft: Optional[float] = Field(None, description="Height of the new structure in feet")
    stories: Optional[float] = Field(None, description="Number of stories of the new structure")
    footprint_sqft: Optional[float] = Field(None, description="Ground footprint ADDED by this project, sq ft")
    floor_area_sqft: Optional[float] = Field(None, description="Gross floor area ADDED or changed by this project, sq ft")
    front_setback_ft: Optional[float] = Field(None, description="Distance from new structure to front property line, ft")
    side_setback_ft: Optional[float] = Field(None, description="Smallest distance from new structure to a side property line, ft")
    rear_setback_ft: Optional[float] = Field(None, description="Distance from new structure to rear property line, ft")
    parking_spaces: Optional[int] = Field(None, description="Off-street parking spaces provided by the project")
    submittals: List[SubmittalType] = Field(default_factory=list, description="Documents the applicant says are attached")
    summary: str = Field("", description="One-sentence plain-English summary of the project")


class Parcel(BaseModel):
    parcel_id: str
    address: str
    district: str
    lot_area_sqft: float
    lot_width_ft: float
    existing_footprint_sqft: float = 0
    existing_floor_area_sqft: float = 0
    existing_units: int = 0


FindingStatus = Literal["pass", "fail", "info_needed", "discretionary"]


class Finding(BaseModel):
    rule: str
    section: str
    status: FindingStatus
    title: str
    detail: str
    required: Optional[str] = None
    proposed: Optional[str] = None


Outcome = Literal["approvable", "corrections_required", "incomplete", "hearing_required"]


class ReviewResult(BaseModel):
    outcome: Outcome
    outcome_label: str
    findings: List[Finding]
    counts: dict


class ApplicationIn(BaseModel):
    address: str
    applicant_name: str = "Applicant"
    applicant_email: str = ""
    description: str = ""
    params: Optional[ProjectParams] = None


class AskIn(BaseModel):
    question: str


class LetterIn(BaseModel):
    letter: str
