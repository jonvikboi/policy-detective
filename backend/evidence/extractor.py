"""
Evidence Extractor — Normalizes raw WebCMD browser evidence into
structured database records.

Takes raw cookie lists, network request lists, and page metadata from
the WebCMD adapter and produces classified, normalized evidence objects.
"""

import logging
from urllib.parse import urlparse

from backend.evidence.classifier import (
    classify_cookie,
    classify_network_request,
    is_third_party,
)

logger = logging.getLogger(__name__)


def normalize_cookies(
    raw_cookies: list, site_domain: str
) -> list[dict]:
    """
    Normalize raw cookie data from WebCMD into classified evidence records.
    Does NOT store raw cookie values (security requirement).
    """
    normalized = []
    for c in raw_cookies:
        if isinstance(c, str):
            # Parse simple cookie string like "name=value; domain=..."
            parts = c.split(";")
            name = parts[0].split("=")[0].strip() if parts else c
            domain = site_domain
            c_dict = {"name": name, "domain": domain}
        elif isinstance(c, dict):
            c_dict = c
        else:
            continue

        domain = c_dict.get("domain", "") or site_domain
        name = c_dict.get("name", "")

        category, source = classify_cookie(name, domain, site_domain)
        third_party = is_third_party(domain, site_domain)

        normalized.append({
            "name": name,
            "domain": domain,
            "path": c_dict.get("path", "/"),
            "expires": str(c_dict.get("expires", "")) if c_dict.get("expires") else None,
            "secure": bool(c_dict.get("secure", False)),
            "http_only": bool(c_dict.get("httpOnly", False) or c_dict.get("http_only", False)),
            "same_site": str(c_dict.get("sameSite", "") or c_dict.get("same_site", "")),
            "is_third_party": third_party,
            "category": category.value,
            "classification_source": source,
        })

    return normalized


def normalize_network_requests(
    raw_requests: list, site_domain: str
) -> list[dict]:
    """
    Normalize raw network request data from WebCMD into classified evidence.
    """
    normalized = []
    seen_urls = set()

    for r in raw_requests:
        if isinstance(r, str):
            url = r
            method = "GET"
            r_dict = {"url": url, "method": method}
        elif isinstance(r, dict):
            r_dict = r
            url = r_dict.get("url", "")
            method = r_dict.get("method", "GET")
        else:
            continue

        if not url:
            continue

        # Deduplicate by URL
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Skip data: and blob: URLs
        if url.startswith("data:") or url.startswith("blob:"):
            continue

        classification = classify_network_request(url, site_domain)

        normalized.append({
            "url": url[:2000],  # Cap URL length
            "domain": classification["domain"],
            "method": method,
            "resource_type": r_dict.get("resourceType", "") or r_dict.get("resource_type", ""),
            "status_code": r_dict.get("status") or r_dict.get("status_code"),
            "initiator": r_dict.get("initiator", ""),
            "is_third_party": classification["is_third_party"],
            "category": classification["category"],
            "classification_source": classification["classification_source"],
        })

    return normalized


def build_evidence_summary(
    cookies: list[dict], network_requests: list[dict]
) -> dict:
    """Build a summary of evidence for verdict generation."""
    third_party_cookies = [c for c in cookies if c["is_third_party"]]
    third_party_requests = [r for r in network_requests if r["is_third_party"]]

    # Count by category
    cookie_categories = {}
    for c in cookies:
        cat = c["category"]
        cookie_categories[cat] = cookie_categories.get(cat, 0) + 1

    request_categories = {}
    for r in third_party_requests:
        cat = r["category"]
        request_categories[cat] = request_categories.get(cat, 0) + 1

    # Unique third-party domains
    third_party_domains = sorted(set(
        r["domain"] for r in third_party_requests if r["domain"]
    ))

    return {
        "total_cookies": len(cookies),
        "third_party_cookies": len(third_party_cookies),
        "cookie_categories": cookie_categories,
        "total_requests": len(network_requests),
        "third_party_requests": len(third_party_requests),
        "request_categories": request_categories,
        "third_party_domains": third_party_domains[:50],
        "cookies": cookies[:30],  # Include top cookies for LLM analysis
    }
