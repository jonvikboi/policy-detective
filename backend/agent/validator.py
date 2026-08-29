"""
Action Validator — Explicit allowlist for all browser actions.

The LLM proposes actions → Validator checks them → Only valid actions
reach WebCMD. This is a security boundary.

Flow:
  LLM → Proposed Action → Action Validator → VALID → WebCMD
                                            → INVALID → Reject + Re-plan
"""

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Allowed action types for the investigation agent."""
    FETCH_URL = "fetch_url"          # HTTP fetch via webcmd web fetch
    NAVIGATE = "navigate"            # Browser navigation to URL
    SNAPSHOT = "snapshot"            # Take page snapshot
    CLICK = "click"                  # Click consent button
    EXTRACT_LINKS = "extract_links"  # Extract page links
    EXTRACT_CONTENT = "extract_content"  # Extract page text
    GET_COOKIES = "get_cookies"      # Capture cookies
    CAPTURE_EVIDENCE = "capture_evidence"  # Full network+cookie capture
    INTERACT_CONSENT = "interact_consent"  # Interact with consent UI
    CONCLUDE = "conclude"            # End investigation


class ProposedAction(BaseModel):
    """An action proposed by the LLM or planner."""
    action_type: str
    url: Optional[str] = None
    session_id: Optional[str] = None
    parameters: dict = {}
    reasoning: str = ""


class ValidationResult(BaseModel):
    """Result of validating a proposed action."""
    valid: bool
    action_type: Optional[ActionType] = None
    rejection_reason: str = ""
    sanitized_url: Optional[str] = None


# --- URL allowlist/blocklist ---

BLOCKED_URL_SCHEMES = {"file", "ftp", "javascript", "data", "blob"}
BLOCKED_URL_PATTERNS = [
    "127.0.0.1", "localhost", "0.0.0.0",
    "169.254.", "10.", "192.168.", "172.16.",  # Private ranges
    "metadata.google", "metadata.aws",  # Cloud metadata (SSRF)
]
MAX_URL_LENGTH = 2000


def validate_url(url: str) -> tuple[bool, str]:
    """Validate a URL against security rules."""
    if not url:
        return False, "URL is empty"

    if len(url) > MAX_URL_LENGTH:
        return False, f"URL too long ({len(url)} > {MAX_URL_LENGTH})"

    from urllib.parse import urlparse
    parsed = urlparse(url)

    if not parsed.scheme:
        return False, "URL has no scheme"

    if parsed.scheme.lower() in BLOCKED_URL_SCHEMES:
        return False, f"Blocked URL scheme: {parsed.scheme}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Only HTTP(S) URLs allowed, got: {parsed.scheme}"

    hostname = (parsed.hostname or "").lower()
    for pattern in BLOCKED_URL_PATTERNS:
        if pattern in hostname:
            return False, f"Blocked URL target: {pattern}"

    return True, ""


def validate_action(proposed: ProposedAction) -> ValidationResult:
    """
    Validate a proposed action against the allowlist.

    Returns a ValidationResult indicating whether the action can proceed.
    """
    # Check action type is in allowlist
    try:
        action_type = ActionType(proposed.action_type)
    except ValueError:
        logger.warning(f"Rejected unknown action type: {proposed.action_type}")
        return ValidationResult(
            valid=False,
            rejection_reason=f"Unknown action type: {proposed.action_type}. "
                           f"Allowed: {[a.value for a in ActionType]}",
        )

    # Validate URLs for actions that use them
    url_actions = {ActionType.FETCH_URL, ActionType.NAVIGATE, ActionType.CAPTURE_EVIDENCE}
    sanitized_url = proposed.url

    if action_type in url_actions:
        if not proposed.url:
            return ValidationResult(
                valid=False,
                action_type=action_type,
                rejection_reason=f"Action {action_type.value} requires a URL",
            )
        valid, reason = validate_url(proposed.url)
        if not valid:
            logger.warning(f"Rejected URL: {proposed.url} — {reason}")
            return ValidationResult(
                valid=False,
                action_type=action_type,
                rejection_reason=reason,
            )
        sanitized_url = proposed.url

    # Session-required actions
    session_actions = {
        ActionType.NAVIGATE, ActionType.SNAPSHOT, ActionType.CLICK,
        ActionType.EXTRACT_LINKS, ActionType.EXTRACT_CONTENT,
        ActionType.GET_COOKIES, ActionType.CAPTURE_EVIDENCE,
        ActionType.INTERACT_CONSENT,
    }
    if action_type in session_actions and not proposed.session_id:
        return ValidationResult(
            valid=False,
            action_type=action_type,
            rejection_reason=f"Action {action_type.value} requires a session_id",
        )

    # Consent interaction validation
    if action_type == ActionType.INTERACT_CONSENT:
        consent_action = proposed.parameters.get("action", "")
        if consent_action not in ("accept", "reject"):
            return ValidationResult(
                valid=False,
                action_type=action_type,
                rejection_reason=f"Consent action must be 'accept' or 'reject', got: {consent_action}",
            )

    logger.info(f"Validated action: {action_type.value}")
    return ValidationResult(
        valid=True,
        action_type=action_type,
        sanitized_url=sanitized_url,
    )
