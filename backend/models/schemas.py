"""Pydantic schemas for API request/response models."""

from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional


# --- Request ---

class ScanRequest(BaseModel):
    url: str = Field(..., description="Website URL to investigate")


# --- Response ---

class ScanResponse(BaseModel):
    id: str
    url: str
    domain: str
    status: str
    progress: float
    current_stage: str
    stage_details: str
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PolicyResponse(BaseModel):
    id: str
    url: str
    title: str
    policy_type: str
    content: str
    discovered_via: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimResponse(BaseModel):
    id: str
    policy_id: str
    category: str
    claim_text: str
    testability: str
    test_type: str
    expected_behavior: dict
    source_section: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CookieEvidenceResponse(BaseModel):
    id: str
    name: str
    domain: str
    path: str
    expires: Optional[float] = None
    secure: bool
    http_only: bool
    same_site: str
    is_third_party: bool
    category: str
    classification_source: str

    model_config = {"from_attributes": True}


class NetworkEvidenceResponse(BaseModel):
    id: str
    url: str
    domain: str
    method: str
    resource_type: str
    status_code: Optional[int] = None
    is_third_party: bool
    category: str
    classification_source: str

    model_config = {"from_attributes": True}


class ExperimentResponse(BaseModel):
    id: str
    state: str
    status: str
    page_url: str
    page_title: str
    cookies: list[CookieEvidenceResponse] = []
    network_requests: list[NetworkEvidenceResponse] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = {"from_attributes": True}


class VerdictResponse(BaseModel):
    id: str
    claim_id: str
    verdict_type: str
    confidence: float
    confidence_reasoning: str
    explanation: str
    expected_behavior: dict | str = {}
    observed_behavior: dict | str = {}
    evidence_summary: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanEventResponse(BaseModel):
    id: str
    event_type: str
    data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Report ---

class ScanReportResponse(BaseModel):
    scan: ScanResponse
    policies: list[PolicyResponse]
    claims: list[ClaimResponse]
    experiments: list[ExperimentResponse]
    verdicts: list[VerdictResponse]
    summary: dict
