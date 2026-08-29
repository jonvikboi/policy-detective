"""Database models for Policy Detective."""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, JSON, Enum, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid.uuid4())


# --- Enums ---

class ScanStatus(str, PyEnum):
    PENDING = "pending"
    DISCOVERING = "discovering"
    EXTRACTING = "extracting"
    INVESTIGATING = "investigating"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class VerdictType(str, PyEnum):
    CONSISTENT = "consistent"
    POTENTIAL_INCONSISTENCY = "potential_inconsistency"
    STRONG_INCONSISTENCY = "strong_inconsistency"
    UNABLE_TO_VERIFY = "unable_to_verify"
    TEST_FAILED = "test_failed"


class ClaimCategory(str, PyEnum):
    COOKIES = "cookies"
    TRACKING = "tracking"
    ANALYTICS = "analytics"
    ADVERTISING = "advertising"
    THIRD_PARTY = "third_party"
    CONSENT = "consent"
    OPT_OUT = "opt_out"
    DATA_COLLECTION = "data_collection"
    LOCATION = "location"
    FINGERPRINTING = "fingerprinting"
    DATA_DELETION = "data_deletion"
    DATA_ACCESS = "data_access"
    DATA_RETENTION = "data_retention"


class Testability(str, PyEnum):
    AUTOMATABLE = "automatable"
    PARTIALLY_AUTOMATABLE = "partially_automatable"
    MANUAL_ONLY = "manual_only"
    NOT_TESTABLE = "not_testable"


class TrackerCategory(str, PyEnum):
    ANALYTICS = "analytics"
    ADVERTISING = "advertising"
    SOCIAL_TRACKING = "social_tracking"
    FUNCTIONAL = "functional"
    AUTHENTICATION = "authentication"
    PAYMENT = "payment"
    CDN = "cdn"
    FIRST_PARTY = "first_party"
    UNKNOWN = "unknown"


class ExperimentState(str, PyEnum):
    PRE_CONSENT = "pre_consent"
    ACCEPT_ALL = "accept_all"
    REJECT_ALL = "reject_all"


# --- Base ---

class Base(DeclarativeBase):
    pass


# --- Models ---

class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, default=new_id)
    url = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    status = Column(Enum(ScanStatus), default=ScanStatus.PENDING, nullable=False)
    progress = Column(Float, default=0.0)
    current_stage = Column(String, default="initializing")
    stage_details = Column(Text, default="")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    policies = relationship("Policy", back_populates="scan", cascade="all, delete-orphan")
    claims = relationship("PolicyClaim", back_populates="scan", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="scan", cascade="all, delete-orphan")
    verdicts = relationship("Verdict", back_populates="scan", cascade="all, delete-orphan")
    events = relationship("ScanEvent", back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_scans_status", "status"),)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=new_id)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, default="")
    policy_type = Column(String, nullable=False)  # privacy, cookies, terms, etc.
    content = Column(Text, nullable=False)
    content_hash = Column(String, default="")
    discovered_via = Column(String, default="")  # footer_link, search, sitemap, etc.
    created_at = Column(DateTime, default=utcnow, nullable=False)

    scan = relationship("Scan", back_populates="policies")
    claims = relationship("PolicyClaim", back_populates="policy", cascade="all, delete-orphan")


class PolicyClaim(Base):
    __tablename__ = "policy_claims"

    id = Column(String, primary_key=True, default=new_id)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    policy_id = Column(String, ForeignKey("policies.id"), nullable=False)
    category = Column(Enum(ClaimCategory), nullable=False)
    claim_text = Column(Text, nullable=False)
    testability = Column(Enum(Testability), nullable=False)
    test_type = Column(String, default="")
    expected_behavior = Column(JSON, default=dict)
    source_section = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    scan = relationship("Scan", back_populates="claims")
    policy = relationship("Policy", back_populates="claims")
    verdicts = relationship("Verdict", back_populates="claim", cascade="all, delete-orphan")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True, default=new_id)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    state = Column(Enum(ExperimentState), nullable=False)
    webcmd_session_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    page_url = Column(String, default="")
    page_title = Column(String, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    scan = relationship("Scan", back_populates="experiments")
    cookies = relationship("CookieEvidence", back_populates="experiment", cascade="all, delete-orphan")
    network_requests = relationship("NetworkEvidence", back_populates="experiment", cascade="all, delete-orphan")


class CookieEvidence(Base):
    __tablename__ = "cookie_evidence"

    id = Column(String, primary_key=True, default=new_id)
    experiment_id = Column(String, ForeignKey("experiments.id"), nullable=False)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    path = Column(String, default="/")
    expires = Column(Float, nullable=True)  # epoch seconds
    secure = Column(Boolean, default=False)
    http_only = Column(Boolean, default=False)
    same_site = Column(String, default="")
    is_third_party = Column(Boolean, default=False)
    category = Column(Enum(TrackerCategory), default=TrackerCategory.UNKNOWN)
    classification_source = Column(String, default="")  # known_list, heuristic, llm
    created_at = Column(DateTime, default=utcnow, nullable=False)

    experiment = relationship("Experiment", back_populates="cookies")


class NetworkEvidence(Base):
    __tablename__ = "network_evidence"

    id = Column(String, primary_key=True, default=new_id)
    experiment_id = Column(String, ForeignKey("experiments.id"), nullable=False)
    url = Column(Text, nullable=False)
    domain = Column(String, nullable=False)
    method = Column(String, default="GET")
    resource_type = Column(String, default="")
    status_code = Column(Integer, nullable=True)
    initiator = Column(String, default="")
    is_third_party = Column(Boolean, default=False)
    category = Column(Enum(TrackerCategory), default=TrackerCategory.UNKNOWN)
    classification_source = Column(String, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    experiment = relationship("Experiment", back_populates="network_requests")


class Verdict(Base):
    __tablename__ = "verdicts"

    id = Column(String, primary_key=True, default=new_id)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    claim_id = Column(String, ForeignKey("policy_claims.id"), nullable=False)
    verdict_type = Column(Enum(VerdictType), nullable=False)
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    confidence_reasoning = Column(Text, default="")
    explanation = Column(Text, nullable=False)
    expected_behavior = Column(JSON, default=dict)
    observed_behavior = Column(JSON, default=dict)
    evidence_summary = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    scan = relationship("Scan", back_populates="verdicts")
    claim = relationship("PolicyClaim", back_populates="verdicts")


class ScanEvent(Base):
    """Stores progress events for real-time frontend updates."""
    __tablename__ = "scan_events"

    id = Column(String, primary_key=True, default=new_id)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    event_type = Column(String, nullable=False)  # stage_change, evidence_found, etc.
    data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    scan = relationship("Scan", back_populates="events")

    __table_args__ = (Index("ix_scan_events_scan_id", "scan_id"),)


class WorkflowRecord(Base):
    """Application-level workflow metadata for the Explore→Learn→Reuse loop."""
    __tablename__ = "workflow_records"

    id = Column(String, primary_key=True, default=new_id)
    domain = Column(String, nullable=False, index=True)
    workflow_type = Column(String, nullable=False)  # policy_discovery, consent_interaction, etc.
    navigation_path = Column(JSON, default=list)  # ordered list of steps that worked
    consent_ui_selector = Column(JSON, default=dict)  # learned consent button selectors
    policy_links = Column(JSON, default=dict)  # known policy page URLs
    last_verified_at = Column(DateTime, nullable=True)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
