"""
Recovery Manager — Implements the architecture's recovery strategy:

1. Retry
2. Browser Escalation
3. Site Search
4. Related Links
5. Document / PDF
6. Re-plan
7. Unable to Verify

Every failure produces structured state. No infinite retries.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RecoveryStrategy(str, Enum):
    RETRY = "retry"
    BROWSER_ESCALATION = "browser_escalation"
    SITE_SEARCH = "site_search"
    RELATED_LINKS = "related_links"
    DOCUMENT_PDF = "document_pdf"
    REPLAN = "replan"
    UNABLE_TO_VERIFY = "unable_to_verify"


# Maximum attempts per strategy
MAX_RETRIES = 2
MAX_ESCALATION = 1
MAX_SEARCH = 1
MAX_RELATED = 1
MAX_REPLAN = 1


@dataclass
class RecoveryState:
    """Tracks which recovery strategies have been used."""
    retries: int = 0
    browser_escalation: int = 0
    site_search: int = 0
    related_links: int = 0
    document_pdf: int = 0
    replan: int = 0


class RecoveryManager:
    """
    Manages recovery strategies for failed investigation actions.

    Follows the ordered escalation path from the architecture:
    Retry → Browser Escalation → Site Search → Related Links → Document/PDF → Re-plan → Unable to Verify
    """

    def __init__(self):
        self.states: dict[str, RecoveryState] = {}  # scan_id -> RecoveryState

    def get_state(self, scan_id: str) -> RecoveryState:
        if scan_id not in self.states:
            self.states[scan_id] = RecoveryState()
        return self.states[scan_id]

    def next_strategy(
        self, scan_id: str, failure_type: str, context: dict = None
    ) -> RecoveryStrategy:
        """
        Determine the next recovery strategy based on failure type and
        what has already been tried.
        """
        state = self.get_state(scan_id)
        context = context or {}

        # Retry for transient failures
        if state.retries < MAX_RETRIES and failure_type in (
            "timeout", "network_error", "session_error", "transient"
        ):
            state.retries += 1
            logger.info(f"[{scan_id}] Recovery: RETRY ({state.retries}/{MAX_RETRIES})")
            return RecoveryStrategy.RETRY

        # Browser escalation when HTTP fetch failed
        if state.browser_escalation < MAX_ESCALATION and failure_type in (
            "fetch_blocked", "fetch_requires_browser", "content_not_extracted"
        ):
            state.browser_escalation += 1
            logger.info(f"[{scan_id}] Recovery: BROWSER_ESCALATION")
            return RecoveryStrategy.BROWSER_ESCALATION

        # Site search when policy page not found
        if state.site_search < MAX_SEARCH and failure_type in (
            "policy_not_found", "page_not_found", "404"
        ):
            state.site_search += 1
            logger.info(f"[{scan_id}] Recovery: SITE_SEARCH")
            return RecoveryStrategy.SITE_SEARCH

        # Related links when specific page not found
        if state.related_links < MAX_RELATED and failure_type in (
            "policy_not_found", "insufficient_content"
        ):
            state.related_links += 1
            logger.info(f"[{scan_id}] Recovery: RELATED_LINKS")
            return RecoveryStrategy.RELATED_LINKS

        # Re-plan when approach isn't working
        if state.replan < MAX_REPLAN and failure_type in (
            "consent_not_found", "interaction_failed", "unexpected_state"
        ):
            state.replan += 1
            logger.info(f"[{scan_id}] Recovery: REPLAN")
            return RecoveryStrategy.REPLAN

        # Final fallback
        logger.info(f"[{scan_id}] Recovery: UNABLE_TO_VERIFY (all strategies exhausted)")
        return RecoveryStrategy.UNABLE_TO_VERIFY

    def reset(self, scan_id: str):
        """Reset recovery state for a scan."""
        if scan_id in self.states:
            del self.states[scan_id]
