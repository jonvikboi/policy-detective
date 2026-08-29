"""
Investigation State — Tracks the current state of a scan investigation.

Represents the state machine:
  INIT → DISCOVERING → EXTRACTING → INVESTIGATING → ANALYZING → COMPLETED
                                                                → FAILED

Each transition emits a ScanEvent for frontend progress tracking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class InvestigationStage(str, Enum):
    INITIALIZING = "initializing"
    DISCOVERING_POLICIES = "discovering_policies"
    EXTRACTING_CLAIMS = "extracting_claims"
    PRE_CONSENT_EXPERIMENT = "pre_consent_experiment"
    ACCEPT_EXPERIMENT = "accept_experiment"
    REJECT_EXPERIMENT = "reject_experiment"
    ANALYZING_EVIDENCE = "analyzing_evidence"
    GENERATING_VERDICTS = "generating_verdicts"
    COMPLETED = "completed"
    FAILED = "failed"


# Stage progress percentages
STAGE_PROGRESS = {
    InvestigationStage.INITIALIZING: 0.0,
    InvestigationStage.DISCOVERING_POLICIES: 10.0,
    InvestigationStage.EXTRACTING_CLAIMS: 25.0,
    InvestigationStage.PRE_CONSENT_EXPERIMENT: 40.0,
    InvestigationStage.ACCEPT_EXPERIMENT: 55.0,
    InvestigationStage.REJECT_EXPERIMENT: 70.0,
    InvestigationStage.ANALYZING_EVIDENCE: 85.0,
    InvestigationStage.GENERATING_VERDICTS: 92.0,
    InvestigationStage.COMPLETED: 100.0,
    InvestigationStage.FAILED: -1.0,
}


@dataclass
class InvestigationState:
    """Mutable state object tracking an investigation's progress."""

    scan_id: str
    url: str
    domain: str
    stage: InvestigationStage = InvestigationStage.INITIALIZING
    progress: float = 0.0
    stage_details: str = ""
    error: Optional[str] = None

    # Discovered data
    policy_urls: list[dict] = field(default_factory=list)
    policies: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)

    # Active WebCMD sessions
    sessions: dict[str, str] = field(default_factory=dict)  # state -> session_id

    # Evidence collected per experiment state
    evidence: dict[str, dict] = field(default_factory=dict)  # state -> evidence

    # Verdicts
    verdicts: list[dict] = field(default_factory=list)

    # Events log
    events: list[dict] = field(default_factory=list)

    # Recovery tracking
    retry_count: int = 0
    max_retries: int = 3
    recovery_strategies_used: list[str] = field(default_factory=list)

    def advance_stage(self, new_stage: InvestigationStage, details: str = ""):
        """Advance to the next investigation stage."""
        old_stage = self.stage
        self.stage = new_stage
        self.progress = STAGE_PROGRESS.get(new_stage, self.progress)
        self.stage_details = details

        event = {
            "type": "stage_change",
            "from": old_stage.value,
            "to": new_stage.value,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(event)
        logger.info(f"[{self.scan_id}] {old_stage.value} → {new_stage.value}: {details}")

    def add_event(self, event_type: str, data: dict = None):
        """Record an investigation event."""
        event = {
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(event)

    def fail(self, error: str):
        """Mark investigation as failed."""
        self.error = error
        self.advance_stage(InvestigationStage.FAILED, error)
