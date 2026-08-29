"""
Policy Verdict Engine — Deterministic comparison component.

While the LLM generates the final verdict explanation, this module provides
deterministic evidence analysis that the LLM's verdict is based on.

Supported verdicts:
  CONSISTENT               — Policy claim matches observed behavior
  POTENTIAL_INCONSISTENCY   — Minor deviation or ambiguous evidence
  STRONG_INCONSISTENCY      — Clear contradiction between policy and behavior
  UNABLE_TO_VERIFY          — Evidence insufficient for a determination
  TEST_FAILED               — Technical failure prevented testing
"""

import logging
from typing import Optional

from backend.models.database import TrackerCategory

logger = logging.getLogger(__name__)


def compute_cookie_verdict_signals(
    claim_category: str,
    pre_consent_evidence: dict,
    accept_evidence: dict,
    reject_evidence: dict,
) -> dict:
    """
    Compute deterministic signals for cookie-related claims.

    Returns a dict of signals the LLM can use for verdict generation.
    """
    signals = {
        "pre_consent": _analyze_experiment_cookies(pre_consent_evidence),
        "accept_all": _analyze_experiment_cookies(accept_evidence),
        "reject_all": _analyze_experiment_cookies(reject_evidence),
    }

    # Cross-experiment analysis
    pre = signals["pre_consent"]
    accept = signals["accept_all"]
    reject = signals["reject_all"]

    # Key comparisons
    signals["cookies_before_consent"] = pre["non_essential_cookies"]
    signals["cookies_increased_after_accept"] = (
        accept["total_cookies"] > pre["total_cookies"]
    )
    signals["cookies_after_reject_same_as_pre"] = (
        reject["non_essential_cookies"] <= pre["non_essential_cookies"]
    )
    signals["tracking_before_consent"] = pre["tracking_cookies"] > 0
    signals["advertising_before_consent"] = pre["advertising_cookies"] > 0
    signals["third_party_before_consent"] = pre["third_party_count"] > 0

    # If claim is about consent being required for non-essential cookies
    if claim_category in ("cookies", "consent"):
        if pre["non_essential_cookies"] > 0:
            signals["consent_violation_signal"] = True
            signals["severity"] = (
                "strong" if pre["non_essential_cookies"] >= 3 else "potential"
            )
        else:
            signals["consent_violation_signal"] = False
            signals["severity"] = "none"

    return signals


def compute_tracking_verdict_signals(
    pre_consent_evidence: dict,
    accept_evidence: dict,
    reject_evidence: dict,
) -> dict:
    """Compute deterministic signals for tracking-related claims."""
    signals = {
        "pre_consent": _analyze_experiment_requests(pre_consent_evidence),
        "accept_all": _analyze_experiment_requests(accept_evidence),
        "reject_all": _analyze_experiment_requests(reject_evidence),
    }

    pre = signals["pre_consent"]
    reject = signals["reject_all"]

    signals["tracking_before_consent"] = pre["tracking_requests"] > 0
    signals["advertising_before_consent"] = pre["advertising_requests"] > 0
    signals["tracking_after_reject"] = reject["tracking_requests"] > 0
    signals["advertising_after_reject"] = reject["advertising_requests"] > 0

    return signals


def compute_confidence(
    evidence_counts: dict,
    experiment_states_completed: int = 3,
) -> tuple[float, str]:
    """
    Compute evidence-backed confidence score.

    Confidence is based on evidence quality, not LLM certainty.
    """
    factors = []
    reasoning_parts = []

    # Factor 1: Number of experiments completed
    exp_factor = experiment_states_completed / 3.0
    factors.append(exp_factor)
    reasoning_parts.append(f"{experiment_states_completed}/3 experiment states completed")

    # Factor 2: Evidence volume
    total_observations = (
        evidence_counts.get("total_cookies", 0) +
        evidence_counts.get("total_requests", 0)
    )
    if total_observations > 50:
        vol_factor = 1.0
    elif total_observations > 20:
        vol_factor = 0.8
    elif total_observations > 5:
        vol_factor = 0.6
    else:
        vol_factor = 0.3
    factors.append(vol_factor)
    reasoning_parts.append(f"{total_observations} total observations")

    # Factor 3: Classification coverage
    classified = evidence_counts.get("classified_count", 0)
    total = evidence_counts.get("total_items", 1)
    class_factor = classified / max(total, 1)
    factors.append(class_factor)
    reasoning_parts.append(f"{classified}/{total} items classified")

    # Weighted average
    confidence = sum(factors) / len(factors)
    reasoning = "; ".join(reasoning_parts)

    return round(confidence, 2), reasoning


def _analyze_experiment_cookies(evidence: dict) -> dict:
    """Analyze cookie evidence from a single experiment."""
    cookies = evidence.get("cookies", [])

    total = len(cookies)
    third_party = sum(1 for c in cookies if c.get("is_third_party"))

    categories = {}
    for c in cookies:
        cat = c.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    non_essential = (
        categories.get("analytics", 0) +
        categories.get("advertising", 0) +
        categories.get("social_tracking", 0)
    )

    return {
        "total_cookies": total,
        "third_party_count": third_party,
        "categories": categories,
        "non_essential_cookies": non_essential,
        "tracking_cookies": categories.get("analytics", 0) + categories.get("social_tracking", 0),
        "advertising_cookies": categories.get("advertising", 0),
        "functional_cookies": categories.get("functional", 0),
    }


def _analyze_experiment_requests(evidence: dict) -> dict:
    """Analyze network request evidence from a single experiment."""
    requests = evidence.get("cookies", [])  # Uses the summary format
    third_party_requests = evidence.get("third_party_requests", 0)

    req_categories = evidence.get("request_categories", {})

    return {
        "total_requests": evidence.get("total_requests", 0),
        "third_party_requests": third_party_requests,
        "request_categories": req_categories,
        "tracking_requests": req_categories.get("analytics", 0) + req_categories.get("social_tracking", 0),
        "advertising_requests": req_categories.get("advertising", 0),
    }
