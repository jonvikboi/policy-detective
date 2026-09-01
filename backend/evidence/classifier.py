"""
Tracker Classification — Layered, evidence-backed classification of network
requests and cookies.

Classification layers (in priority order):
1. Known domain/service lists (deterministic)
2. First-party vs third-party analysis (deterministic)
3. URL/path heuristics (deterministic)
4. Request metadata analysis (deterministic)
5. Optional LLM classification for ambiguous cases

The LLM never arbitrarily decides a request is a tracker.
"""

import logging
from urllib.parse import urlparse

from backend.models.database import TrackerCategory

logger = logging.getLogger(__name__)


# --- Known tracker domains (condensed, extensible) ---

KNOWN_ANALYTICS: set[str] = {
    "google-analytics.com", "analytics.google.com", "www.google-analytics.com",
    "ssl.google-analytics.com", "stats.g.doubleclick.net",
    "hotjar.com", "static.hotjar.com", "script.hotjar.com",
    "mixpanel.com", "api.mixpanel.com", "cdn.mxpnl.com",
    "segment.com", "cdn.segment.com", "api.segment.io",
    "amplitude.com", "api.amplitude.com", "cdn.amplitude.com",
    "heap.io", "heapanalytics.com", "cdn.heapanalytics.com",
    "plausible.io", "matomo.cloud",
    "clarity.ms", "www.clarity.ms", "c.clarity.ms",
    "fullstory.com", "rs.fullstory.com",
    "mouseflow.com", "go-mpulse.net", "s.go-mpulse.net", "s2.go-mpulse.net",
    "newrelic.com", "js-agent.newrelic.com", "bam.nr-data.net",
    "sentry.io", "browser.sentry-cdn.com",
    "moengage.com", "cdn.moengage.com", "api.moengage.com",
    "clevertap.com", "wzrk.clevertap.com",
    "branch.io", "app.link", "onelink.me", "myntra.onelink.me",
    "appsflyer.com", "app.appsflyer.com",
    "adjust.com", "app.adjust.com",
    "singular.net", "measurementapi.com", "335741.measurementapi.com",
    "apsalar.com", "ad.apsalar.com", "galleri5.com", "studio.galleri5.com",
}

KNOWN_ADVERTISING: set[str] = {
    "doubleclick.net", "ad.doubleclick.net", "pagead2.googlesyndication.com",
    "googleads.g.doubleclick.net", "www.googleadservices.com",
    "googletagmanager.com", "www.googletagmanager.com",
    "googlesyndication.com",
    "facebook.net", "connect.facebook.net", "pixel.facebook.com",
    "ads.linkedin.com", "px.ads.linkedin.com",
    "ads.twitter.com", "analytics.twitter.com", "t.co",
    "adsymptotic.com",
    "criteo.com", "static.criteo.net", "dynamic.criteo.com",
    "taboola.com", "cdn.taboola.com",
    "outbrain.com", "tr.outbrain.com",
    "amazon-adsystem.com", "aax.amazon-adsystem.com",
    "adnxs.com", "ib.adnxs.com",
    "rubiconproject.com", "fastlane.rubiconproject.com",
    "pubmatic.com", "image2.pubmatic.com",
    "casalemedia.com",
    "bidswitch.net",
    "demdex.net", "dpm.demdex.net",
    "krxd.net", "cdn.krxd.net",
    "bluekai.com", "tags.bluekai.com",
    "quantserve.com", "pixel.quantserve.com",
    "scorecardresearch.com", "sb.scorecardresearch.com",
    "rlcdn.com",
    "exelator.com",
    "tiktok.com", "analytics.tiktok.com",
    "bing.com", "bat.bing.com",
}

KNOWN_SOCIAL: set[str] = {
    "platform.twitter.com", "platform.linkedin.com",
    "apis.google.com", "accounts.google.com",
    "graph.facebook.com", "www.facebook.com",
    "connect.facebook.net",
    "platform.instagram.com",
    "static.addtoany.com",
    "disqus.com",
    "sharethis.com",
}

KNOWN_CDN: set[str] = {
    "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "unpkg.com",
    "ajax.googleapis.com", "fonts.googleapis.com", "fonts.gstatic.com",
    "maxcdn.bootstrapcdn.com", "stackpath.bootstrapcdn.com",
    "cdn.cloudflare.com",
    "use.fontawesome.com", "kit.fontawesome.com",
    "code.jquery.com", "myntassets.com", "assets.myntassets.com",
    "cdn.myntassets.com", "constant.myntassets.com",
}

KNOWN_FUNCTIONAL: set[str] = {
    "cdn.cookielaw.org", "geolocation.onetrust.com",  # Consent managers
    "consent.cookiebot.com", "consentcdn.cookiebot.com",
    "recaptcha.net", "www.recaptcha.net",
    "hcaptcha.com", "js.hcaptcha.com",
    "challenges.cloudflare.com",
    "maps.googleapis.com", "maps.google.com",
}

KNOWN_PAYMENT: set[str] = {
    "js.stripe.com", "api.stripe.com",
    "www.paypal.com", "www.paypalobjects.com",
    "checkout.shopify.com",
    "js.braintreegateway.com",
    "getsimpl.com", "api.razorpay.com", "checkout.razorpay.com",
}

KNOWN_AUTH: set[str] = {
    "accounts.google.com", "login.microsoftonline.com",
    "auth0.com", "appleid.apple.com",
    "cognito-idp.amazonaws.com",
}

# --- Cookie name patterns ---

ANALYTICS_COOKIE_PATTERNS: list[str] = [
    "_ga", "_gid", "_gat", "__utma", "__utmb", "__utmc", "__utmz", "__utmt",
    "_hjid", "_hjSession", "_hjSessionUser", "_hjAbsoluteSessionInProgress",
    "mp_", "ajs_",
    "_clck", "_clsk",
    "_fbp", "_fbc",
    "utm_", "utrid", "_mxab_", "_pv", "ilgim", "_d_id",
    "moe_", "wzrk_", "ct_", "af_", "_branch_",
]

ADVERTISING_COOKIE_PATTERNS: list[str] = [
    "IDE", "DSID", "FLC", "AID", "TAID", "exchange_uid",
    "__gads", "__gpi",
    "fr",  # Facebook
    "NID", "ANID", "1P_JAR", "CONSENT",
    "_gcl_",
    "test_cookie",
    "_abck", "bm_sz", "ak_bmsc",  # Bot/telemetry trackers
]

FUNCTIONAL_COOKIE_PATTERNS: list[str] = [
    "CookieConsent", "OptanonConsent", "OptanonAlertBoxClosed",
    "cookieconsent_status", "euconsent",
    "JSESSIONID", "PHPSESSID", "session_id", "sessionid",
    "csrf", "XSRF-TOKEN", "csrf_token",
    "__cfduid", "cf_clearance",
]


def _extract_base_domain(domain: str) -> str:
    """Extract base domain from full domain."""
    parts = domain.lstrip(".").split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def classify_domain(
    request_domain: str, site_domain: str
) -> tuple[TrackerCategory, str]:
    """
    Classify a domain using the layered classification system.

    Returns (category, classification_source).
    """
    base_domain = _extract_base_domain(request_domain)
    request_domain_clean = request_domain.lstrip(".")

    # Layer 1: Known domain lists
    for domain_to_check in (request_domain_clean, base_domain):
        if domain_to_check in KNOWN_ANALYTICS:
            return TrackerCategory.ANALYTICS, "known_list"
        if domain_to_check in KNOWN_ADVERTISING:
            return TrackerCategory.ADVERTISING, "known_list"
        if domain_to_check in KNOWN_SOCIAL:
            return TrackerCategory.SOCIAL_TRACKING, "known_list"
        if domain_to_check in KNOWN_CDN:
            return TrackerCategory.CDN, "known_list"
        if domain_to_check in KNOWN_FUNCTIONAL:
            return TrackerCategory.FUNCTIONAL, "known_list"
        if domain_to_check in KNOWN_PAYMENT:
            return TrackerCategory.PAYMENT, "known_list"
        if domain_to_check in KNOWN_AUTH:
            return TrackerCategory.AUTHENTICATION, "known_list"

    # Layer 2: First-party analysis
    site_base = _extract_base_domain(site_domain)
    if base_domain == site_base:
        return TrackerCategory.FIRST_PARTY, "first_party_match"

    # Layer 3: URL/path heuristics
    domain_lower = request_domain_clean.lower()
    if any(kw in domain_lower for kw in ("analytics", "stats", "metric", "telemetry")):
        return TrackerCategory.ANALYTICS, "domain_heuristic"
    if any(kw in domain_lower for kw in ("ad", "ads", "adserver", "banner", "sponsor")):
        return TrackerCategory.ADVERTISING, "domain_heuristic"
    if any(kw in domain_lower for kw in ("track", "pixel", "beacon")):
        return TrackerCategory.ADVERTISING, "domain_heuristic"
    if any(kw in domain_lower for kw in ("cdn", "static", "assets", "media")):
        return TrackerCategory.CDN, "domain_heuristic"

    return TrackerCategory.UNKNOWN, "unclassified"


def classify_cookie(
    cookie_name: str, cookie_domain: str, site_domain: str
) -> tuple[TrackerCategory, str]:
    """
    Classify a cookie using name patterns and domain analysis.

    Returns (category, classification_source).
    """
    # Check known cookie name patterns
    for pattern in ANALYTICS_COOKIE_PATTERNS:
        if cookie_name.startswith(pattern) or cookie_name == pattern:
            return TrackerCategory.ANALYTICS, "cookie_name_pattern"

    for pattern in ADVERTISING_COOKIE_PATTERNS:
        if cookie_name.startswith(pattern) or cookie_name == pattern:
            return TrackerCategory.ADVERTISING, "cookie_name_pattern"

    for pattern in FUNCTIONAL_COOKIE_PATTERNS:
        if cookie_name.startswith(pattern) or cookie_name == pattern:
            return TrackerCategory.FUNCTIONAL, "cookie_name_pattern"

    # Fall back to domain classification
    return classify_domain(cookie_domain, site_domain)


def is_third_party(request_domain: str, site_domain: str) -> bool:
    """Determine if a request domain is third-party relative to the site."""
    req_base = _extract_base_domain(request_domain)
    site_base = _extract_base_domain(site_domain)
    return req_base != site_base


def classify_network_request(
    url: str, site_domain: str
) -> dict:
    """
    Classify a network request URL.

    Returns dict with domain, is_third_party, category, classification_source.
    """
    parsed = urlparse(url)
    request_domain = parsed.hostname or ""

    third_party = is_third_party(request_domain, site_domain)
    category, source = classify_domain(request_domain, site_domain)

    # Additional URL path heuristics for third-party
    if third_party and category == TrackerCategory.UNKNOWN:
        path_lower = parsed.path.lower()
        if any(kw in path_lower for kw in ("/pixel", "/track", "/beacon", "/collect", "/event")):
            category = TrackerCategory.ADVERTISING
            source = "url_path_heuristic"
        elif any(kw in path_lower for kw in ("/analytics", "/stats", "/log")):
            category = TrackerCategory.ANALYTICS
            source = "url_path_heuristic"

    return {
        "domain": request_domain,
        "is_third_party": third_party,
        "category": category.value,
        "classification_source": source,
    }
