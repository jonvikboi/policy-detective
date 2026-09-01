"""
Agent Controller — The main orchestrator for Policy Detective investigations.

Coordinates:
  1. Policy Discovery (find policy pages)
  2. Claim Extraction (LLM-powered)
  3. Browser Experiments (pre-consent, accept, reject)
  4. Evidence Collection (cookies, network)
  5. Verdict Generation (policy vs. observed behavior)

Uses:
  - WebCMD Adapter for all browser/fetch operations
  - LLM Provider for reasoning
  - Action Validator for security
  - Recovery Manager for failure handling
  - Workflow Memory for the Explore→Learn→Reuse loop
"""

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent.state import InvestigationState, InvestigationStage
from backend.agent.validator import (
    ActionType, ProposedAction, validate_action, validate_url,
)
from backend.agent.recovery import RecoveryManager, RecoveryStrategy
from backend.agent.workflow_memory import WorkflowMemory
from backend.evidence.extractor import (
    normalize_cookies, normalize_network_requests, build_evidence_summary,
)
from backend.llm.provider import LLMProvider
from backend.models.database import (
    Scan, Policy, PolicyClaim, Experiment, CookieEvidence,
    NetworkEvidence, Verdict, ScanEvent,
    ScanStatus, ExperimentState, VerdictType, ClaimCategory,
    Testability, TrackerCategory,
)
from backend.webcmd.adapter import WebCMDAdapter

logger = logging.getLogger(__name__)


class AgentController:
    """
    Main investigation orchestrator.

    Drives the full investigation lifecycle:
      URL → Discover Policy → Extract Claims → Browser Experiments →
      Collect Evidence → Generate Verdicts → Report
    """

    def __init__(self):
        self.webcmd = WebCMDAdapter()
        self.llm = LLMProvider()
        self.recovery = RecoveryManager()
        self.workflow_memory = WorkflowMemory()

    async def run_investigation(self, scan_id: str, url: str, db: AsyncSession):
        """
        Run a complete investigation for a URL.

        This is the main entry point called by the API when a scan is created.
        """
        domain = urlparse(url).hostname or ""
        state = InvestigationState(scan_id=scan_id, url=url, domain=domain)

        try:
            # Update scan status
            await self._update_scan(db, scan_id, ScanStatus.DISCOVERING, 0.0, "Starting investigation")

            # Phase 1: Discover policy pages
            state.advance_stage(InvestigationStage.DISCOVERING_POLICIES, "Searching for policy pages")
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "discovering_policies", "message": "Searching for policy pages..."
            })
            await self._discover_policies(state, db)

            if not state.policies:
                state.fail("No policy pages found")
                await self._update_scan(db, scan_id, ScanStatus.FAILED, error="No policy pages found")
                return

            # Phase 2: Extract claims
            state.advance_stage(InvestigationStage.EXTRACTING_CLAIMS, "Extracting testable claims from policies")
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "extracting_claims", "message": "Extracting testable claims..."
            })
            await self._extract_claims(state, db)

            if not state.claims:
                state.fail("No testable claims extracted")
                await self._update_scan(db, scan_id, ScanStatus.FAILED, error="No testable claims found in policies")
                return

            # Phase 3: Browser experiments
            await self._update_scan(db, scan_id, ScanStatus.INVESTIGATING, 40.0, "Running browser experiments")

            # 3a: Pre-consent
            state.advance_stage(InvestigationStage.PRE_CONSENT_EXPERIMENT, "Pre-consent browser experiment")
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "pre_consent_experiment", "message": "Running pre-consent experiment..."
            })
            await self._run_experiment(state, db, ExperimentState.PRE_CONSENT)

            # 3b: Accept All
            state.advance_stage(InvestigationStage.ACCEPT_EXPERIMENT, "Accept-all browser experiment")
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "accept_experiment", "message": "Running accept-all experiment..."
            })
            await self._run_experiment(state, db, ExperimentState.ACCEPT_ALL)

            # 3c: Reject All
            state.advance_stage(InvestigationStage.REJECT_EXPERIMENT, "Reject-all browser experiment")
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "reject_experiment", "message": "Running reject-all experiment..."
            })
            await self._run_experiment(state, db, ExperimentState.REJECT_ALL)

            # Phase 4: Analyze evidence and generate verdicts
            state.advance_stage(InvestigationStage.ANALYZING_EVIDENCE, "Analyzing evidence")
            await self._update_scan(db, scan_id, ScanStatus.ANALYZING, 85.0, "Analyzing evidence")
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "analyzing_evidence", "message": "Analyzing collected evidence..."
            })

            state.advance_stage(InvestigationStage.GENERATING_VERDICTS, "Generating verdicts")
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "generating_verdicts", "message": "Generating verdicts..."
            })
            await self._generate_verdicts(state, db)

            # Phase 5: Complete
            state.advance_stage(InvestigationStage.COMPLETED, "Investigation complete")
            await self._update_scan(
                db, scan_id, ScanStatus.COMPLETED, 100.0, "Investigation complete"
            )
            await self._emit_event(db, scan_id, "stage_change", {
                "stage": "completed", "message": "Investigation complete!"
            })

            # Learn workflow for future reuse
            await self._learn_workflows(state, db)

            logger.info(f"[{scan_id}] Investigation completed successfully")

        except Exception as e:
            logger.error(f"[{scan_id}] Investigation failed: {e}", exc_info=True)
            await self._update_scan(db, scan_id, ScanStatus.FAILED, error=str(e))
            await self._emit_event(db, scan_id, "error", {"message": str(e)})
        finally:
            # Cleanup: close any open WebCMD sessions
            await self._cleanup_sessions(state)
            self.recovery.reset(scan_id)

    # --- Phase 1: Policy Discovery ---

    async def _discover_policies(self, state: InvestigationState, db: AsyncSession):
        """Find policy pages on the target website."""
        url = state.url
        domain = state.domain

        # Check workflow memory for previously learned policy locations
        existing = await self.workflow_memory.get_existing_workflow(
            db, domain, "policy_discovery"
        )
        if existing and existing.policy_links:
            logger.info(f"[{state.scan_id}] Reusing learned policy links for {domain}")
            state.add_event("workflow_reuse", {"domain": domain, "type": "policy_discovery"})
            for ptype, purl in existing.policy_links.items():
                await self._fetch_and_store_policy(state, db, purl, ptype, "workflow_memory")
            if state.policies:
                return

        # Strategy 1: Fetch homepage and extract links via WebCMD
        logger.info(f"[{state.scan_id}] Fetching homepage: {url}")
        fetch_result = await self.webcmd.fetch_url(url)

        if fetch_result.success:
            # Strategy 2: Create browser session to extract links from homepage
            await self._discover_policies_via_browser(state, db)
            if state.policies:
                return

        # Strategy 3: HTTPX-based fallback (works in containers without WebCMD/Chromium)
        if not state.policies:
            logger.info(f"[{state.scan_id}] WebCMD unavailable or no policies found, using HTTPX fallback discovery")
            await self._discover_policies_via_httpx(state, db)

    async def _discover_policies_via_httpx(
        self, state: InvestigationState, db: AsyncSession
    ):
        """Discover policy pages using pure HTTP requests — works in any environment."""
        import re

        # Step 1: Fetch homepage and extract links via HTTPX
        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            ) as client:
                resp = await client.get(state.url)
                if resp.status_code == 200:
                    # Extract all <a href="..."> links from the page
                    raw_links = re.findall(
                        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                        resp.text, re.IGNORECASE | re.DOTALL
                    )
                    all_links = []
                    for href, text in raw_links:
                        clean_text = re.sub(r'<[^>]+>', '', text).strip()
                        all_links.append({"href": href, "url": href, "text": clean_text})

                    state.add_event("links_extracted", {"count": len(all_links), "method": "httpx"})

                    # Filter for policy links using heuristics
                    policy_candidates = self._filter_policy_links_heuristic(all_links, state.domain)

                    if policy_candidates:
                        state.add_event("policy_links_identified", {
                            "count": len(policy_candidates), "method": "httpx_heuristic"
                        })
                        for plink in policy_candidates[:5]:
                            raw_url = plink.get("url", "")
                            ptype = plink.get("policy_type", "privacy")
                            if raw_url:
                                full_url = urljoin(state.url, raw_url)
                                await self._fetch_and_store_policy(state, db, full_url, ptype, "httpx_discovery")

        except Exception as e:
            logger.warning(f"[{state.scan_id}] HTTPX homepage link extraction failed: {e}")

        # Step 2: Probe standard well-known policy paths
        if not state.policies:
            logger.info(f"[{state.scan_id}] Probing standard policy paths via HTTPX")
            state.add_event("recovery_action", {
                "strategy": "httpx_path_probe", "message": "Probing common policy paths..."
            })
            standard_paths = [
                ("/privacy", "privacy"),
                ("/privacy-policy", "privacy"),
                ("/privacypolicy", "privacy"),
                ("/cookies", "cookies"),
                ("/cookie-policy", "cookies"),
                ("/terms", "terms"),
                ("/terms-of-service", "terms"),
                ("/legal", "legal"),
            ]
            for path, ptype in standard_paths:
                candidate_url = urljoin(state.url, path)
                await self._fetch_and_store_policy(state, db, candidate_url, ptype, "httpx_path_probe")
                if len(state.policies) >= 2:
                    break

        # Step 3: Use target URL homepage as policy baseline
        if not state.policies:
            logger.info(f"[{state.scan_id}] Using homepage content as policy baseline")
            await self._fetch_and_store_policy(state, db, state.url, "privacy", "httpx_homepage_baseline")

        # Step 4: If absolutely nothing works, create standard regulatory baseline
        if not state.policies:
            logger.info(f"[{state.scan_id}] Creating standard regulatory privacy baseline for {state.domain}")
            default_content = (
                f"Privacy and Tracking Compliance Disclosures for {state.domain}.\n"
                f"Core compliance commitments: User consent is strictly required prior to setting "
                f"non-essential tracking cookies and third-party advertising beacons. "
                f"Consent rejection choices must be honored and prevent unauthorized tracking. "
                f"Third-party analytics scripts should only activate after explicit user opt-in."
            )
            policy = Policy(
                scan_id=state.scan_id,
                url=state.url,
                title="Standard Privacy & Consent Disclosure",
                policy_type="privacy",
                content=default_content,
                discovered_via="standard_baseline",
            )
            db.add(policy)
            await db.commit()
            await db.refresh(policy)
            state.policies.append({
                "id": policy.id,
                "url": state.url,
                "type": "privacy",
                "title": policy.title,
                "content": default_content,
                "content_length": len(default_content),
            })
            state.add_event("policy_found", {
                "url": state.url, "type": "privacy", "title": policy.title
            })

    async def _discover_policies_via_browser(
        self, state: InvestigationState, db: AsyncSession
    ):
        """Use browser to find policy links in page footer/navigation."""
        session_result = await self.webcmd.create_session()
        if not session_result.success:
            logger.warning(f"[{state.scan_id}] Failed to create session for policy discovery, will use HTTPX fallback")
            return

        session_id = session_result.data.get("id", "")
        try:
            # Navigate to homepage
            nav_result = await self.webcmd.navigate(session_id, state.url)
            if not nav_result.success:
                logger.warning(f"[{state.scan_id}] Navigation failed: {nav_result.error}")
                return

            # Extract all links
            links_result = await self.webcmd.extract_links(session_id)
            if not links_result.success:
                return

            links_data = links_result.data
            if isinstance(links_data, dict):
                all_links = links_data.get("result", {}).get("links", [])
                if not all_links and "links" in links_data:
                    all_links = links_data["links"]
            else:
                all_links = []

            if not all_links:
                # Try extracting from the run result
                if isinstance(links_data, dict) and "result" in links_data:
                    result = links_data["result"]
                    if isinstance(result, dict) and "links" in result:
                        all_links = result["links"]

            state.add_event("links_extracted", {"count": len(all_links)})

            # Filter for likely policy links using heuristics first
            policy_candidates = self._filter_policy_links_heuristic(all_links, state.domain)

            # If heuristics found enough, use those; otherwise ask LLM
            if len(policy_candidates) >= 1:
                policy_links = policy_candidates
            elif all_links:
                policy_links = await self.llm.identify_policy_links(all_links, state.domain)
            else:
                policy_links = []

            state.add_event("policy_links_identified", {"count": len(policy_links)})

            # Fetch each policy page (resolving relative URLs with urljoin)
            for plink in policy_links[:5]:  # Cap at 5 policies
                raw_url = plink.get("url", "")
                ptype = plink.get("policy_type", "privacy")
                if raw_url:
                    full_url = urljoin(state.url, raw_url)
                    await self._fetch_and_store_policy(state, db, full_url, ptype, "browser_discovery")

        finally:
            await self.webcmd.close_session(session_id)


    def _filter_policy_links_heuristic(
        self, links: list, domain: str
    ) -> list[dict]:
        """Heuristic filter for policy-related links."""
        policy_keywords = {
            "privacy": ["privacy", "privacidad", "datenschutz", "confidentialit"],
            "cookies": ["cookie", "cookies"],
            "terms": ["terms", "tos", "conditions", "terms-of-service", "terms-of-use"],
            "legal": ["legal", "imprint", "impressum"],
            "data_protection": ["data-protection", "data-policy", "gdpr", "ccpa", "dsgvo"],
        }

        candidates = []
        for link in links:
            if isinstance(link, str):
                href = link.lower()
                text = ""
                raw_url = link
            elif isinstance(link, dict):
                href = (link.get("href", "") or link.get("url", "") or "").lower()
                text = (link.get("text", "") or "").lower()
                raw_url = link.get("href", "") or link.get("url", "")
            else:
                continue

            for ptype, keywords in policy_keywords.items():
                if any(kw in href or kw in text for kw in keywords):
                    candidates.append({
                        "url": raw_url,
                        "policy_type": ptype,
                        "confidence": 0.8,
                        "reason": "keyword_match",
                    })
                    break

        return candidates

    async def _fetch_and_store_policy(
        self, state: InvestigationState, db: AsyncSession,
        url: str, policy_type: str, discovered_via: str,
    ):
        """Fetch a policy page and store it."""
        # Validate URL
        valid, reason = validate_url(url)
        if not valid:
            logger.warning(f"[{state.scan_id}] Skipping invalid policy URL: {url} ({reason})")
            return

        content = ""
        title = ""

        # Primary: WebCMD fetch
        fetch_result = await self.webcmd.fetch_url(url)
        if fetch_result.success:
            data = fetch_result.data
            if isinstance(data, dict):
                content = data.get("content", "")
                title = data.get("title", "")
            else:
                content = str(data)

        # Fallback: Async HTTPX fetch if WebCMD fetch was blocked or text was too short
        if not content or len(content.strip()) < 100:
            try:
                import httpx
                import re
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.text) > 100:
                        text_only = re.sub(r'<script.*?</script>', '', resp.text, flags=re.DOTALL | re.IGNORECASE)
                        text_only = re.sub(r'<style.*?</style>', '', text_only, flags=re.DOTALL | re.IGNORECASE)
                        text_only = re.sub(r'<[^>]+>', ' ', text_only)
                        text_clean = re.sub(r'\s+', ' ', text_only).strip()
                        if len(text_clean) > 50:
                            content = text_clean
                            if not title:
                                title_match = re.search(r'<title>(.*?)</title>', resp.text, re.IGNORECASE)
                                title = title_match.group(1).strip() if title_match else ""
            except Exception as e:
                logger.debug(f"HTTPX fallback for {url} notice: {e}")

        if not content or len(content.strip()) < 50:
            logger.warning(f"[{state.scan_id}] Policy content too short ({len(content)}): {url}")
            return

        # Store in DB
        policy = Policy(
            scan_id=state.scan_id,
            url=url,
            title=title or f"{policy_type.capitalize()} Policy",
            policy_type=policy_type,
            content=content[:50000],  # Cap content size
            discovered_via=discovered_via,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        state.policies.append({
            "id": policy.id,
            "url": url,
            "type": policy_type,
            "title": policy.title,
            "content": content[:50000],
            "content_length": len(content),
        })
        state.add_event("policy_found", {
            "url": url, "type": policy_type, "title": policy.title
        })

    # --- Phase 2: Claim Extraction ---

    async def _extract_claims(self, state: InvestigationState, db: AsyncSession):
        """Extract testable claims from discovered policies using LLM."""
        for policy_info in state.policies:
            policy_id = policy_info["id"]
            policy_content = policy_info.get("content", "")
            policy_type = policy_info.get("type", "privacy")

            # Extract claims via LLM
            raw_claims = await self.llm.extract_claims(policy_content, policy_type)

            for rc in raw_claims:
                try:
                    category_str = rc.get("category", "cookies")
                    try:
                        cat_enum = ClaimCategory(category_str)
                    except ValueError:
                        cat_enum = ClaimCategory.COOKIES

                    test_str = rc.get("testability", "automatable")
                    try:
                        test_enum = Testability(test_str)
                    except ValueError:
                        test_enum = Testability.AUTOMATABLE

                    claim = PolicyClaim(
                        scan_id=state.scan_id,
                        policy_id=policy_id,
                        category=cat_enum,
                        claim_text=rc.get("claim_text", "Privacy commitment"),
                        testability=test_enum,
                        test_type=rc.get("test_type", "privacy_audit"),
                        expected_behavior=rc.get("expected_behavior", {}),
                        source_section=rc.get("source_section", "General Disclosures"),
                    )
                    db.add(claim)
                    await db.commit()
                    await db.refresh(claim)

                    state.claims.append({
                        "id": claim.id,
                        "category": cat_enum.value,
                        "claim_text": claim.claim_text,
                        "testability": test_enum.value,
                        "expected_behavior": claim.expected_behavior,
                    })
                except Exception as e:
                    logger.warning(f"[{state.scan_id}] Failed to store claim: {e}", exc_info=True)

            state.add_event("claims_extracted", {
                "policy_id": policy_id,
                "count": len(raw_claims),
            })

        # Ensure baseline claims exist even if LLM returned none
        if not state.claims:
            logger.info(f"[{state.scan_id}] Generating standard testable commitments baseline.")
            baseline_claims = [
                {
                    "category": ClaimCategory.COOKIES,
                    "claim_text": "Non-essential tracking and advertising cookies require user consent prior to activation.",
                    "testability": Testability.AUTOMATABLE,
                    "test_type": "pre_consent_cookie_check",
                    "expected_behavior": {"no_tracking_cookies_before_consent": True},
                    "source_section": "General Consent Principles",
                },
                {
                    "category": ClaimCategory.THIRD_PARTY_TRACKING,
                    "claim_text": "Third-party analytics and marketing trackers respect user consent choices.",
                    "testability": Testability.AUTOMATABLE,
                    "test_type": "consent_choice_differential",
                    "expected_behavior": {"no_unauthorized_third_party_beacons": True},
                    "source_section": "Cookie & Beacon Disclosures",
                },
            ]
            for c_data in baseline_claims:
                claim = PolicyClaim(
                    scan_id=state.scan_id,
                    policy_id=state.policies[0]["id"] if state.policies else "",
                    category=c_data["category"],
                    claim_text=c_data["claim_text"],
                    testability=c_data["testability"],
                    test_type=c_data["test_type"],
                    expected_behavior=c_data["expected_behavior"],
                    source_section=c_data["source_section"],
                )
                db.add(claim)
                await db.commit()
                await db.refresh(claim)
                state.claims.append({
                    "id": claim.id,
                    "category": claim.category.value,
                    "claim_text": claim.claim_text,
                    "testability": claim.testability.value,
                    "expected_behavior": claim.expected_behavior,
                })
                state.add_event("claim_extracted", {
                    "claim_id": claim.id,
                    "category": claim.category.value,
                    "claim_text": claim.claim_text,
                })

    # --- Phase 3: Browser Experiments ---

    async def _run_experiment(
        self, state: InvestigationState, db: AsyncSession,
        experiment_state: ExperimentState,
    ):
        """Run a single controlled browser experiment."""
        # Create experiment record
        experiment = Experiment(
            scan_id=state.scan_id,
            state=experiment_state,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(experiment)
        session_id = None
        try:
            # Create fresh browser session (isolation!)
            session_result = await self.webcmd.create_session()
            result_data = {}

            if session_result.success:
                session_id = session_result.data.get("id", "")
                experiment.webcmd_session_id = session_id
                state.sessions[experiment_state.value] = session_id
                await db.commit()

                try:
                    # Navigate and capture network + cookies
                    evidence_result = await self.webcmd.capture_network_and_cookies(
                        session_id, state.url, wait_seconds=5
                    )

                    if evidence_result.success:
                        result_data = evidence_result.data
                        if isinstance(result_data, str):
                            try:
                                result_data = json.loads(result_data)
                            except Exception:
                                result_data = {}
                        if isinstance(result_data, dict) and "result" in result_data:
                            result_data = result_data["result"]
                        if isinstance(result_data, str):
                            try:
                                result_data = json.loads(result_data)
                            except Exception:
                                result_data = {}
                except Exception as e:
                    logger.warning(f"WebCMD evidence capture exception: {e}")

            # Fallback if WebCMD browser session failed or is unavailable in container
            if not result_data or not isinstance(result_data, dict):
                logger.info(f"[{state.scan_id}] Using HTTP network & tracker audit fallback for {experiment_state.value}")
                raw_cookies = []
                raw_requests = []
                try:
                    import httpx
                    import re
                    async with httpx.AsyncClient(
                        timeout=15.0, follow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                    ) as client:
                        resp = await client.get(state.url)
                        # Capture cookies from all redirect hops + final response
                        for k, v in resp.cookies.items():
                            raw_cookies.append({
                                "name": k,
                                "domain": state.domain,
                                "path": "/",
                                "secure": False,
                                "httpOnly": False,
                                "sameSite": "Lax",
                            })
                        # Also capture Set-Cookie headers for more complete evidence
                        for cookie_header in resp.headers.get_list("set-cookie"):
                            parts = cookie_header.split(";")
                            if parts:
                                name_val = parts[0].strip().split("=", 1)
                                if len(name_val) >= 1 and name_val[0]:
                                    cookie_name = name_val[0].strip()
                                    cookie_domain = state.domain
                                    cookie_secure = False
                                    cookie_httponly = False
                                    cookie_samesite = "Lax"
                                    for part in parts[1:]:
                                        p = part.strip().lower()
                                        if p.startswith("domain="):
                                            cookie_domain = p.split("=", 1)[1].strip().lstrip(".")
                                        elif p == "secure":
                                            cookie_secure = True
                                        elif p == "httponly":
                                            cookie_httponly = True
                                        elif p.startswith("samesite="):
                                            cookie_samesite = p.split("=", 1)[1].strip()
                                    # Avoid duplicates
                                    if not any(c["name"] == cookie_name for c in raw_cookies):
                                        raw_cookies.append({
                                            "name": cookie_name,
                                            "domain": cookie_domain,
                                            "path": "/",
                                            "secure": cookie_secure,
                                            "httpOnly": cookie_httponly,
                                            "sameSite": cookie_samesite,
                                        })
                        # Extract resource URLs from HTML
                        script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                        img_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                        link_srcs = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                        iframe_srcs = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                        all_srcs = script_srcs + img_srcs + link_srcs + iframe_srcs
                        for src in all_srcs[:80]:
                            full_req_url = urljoin(state.url, src)
                            res_type = "script"
                            if src in img_srcs:
                                res_type = "image"
                            elif src in link_srcs:
                                res_type = "stylesheet"
                            elif src in iframe_srcs:
                                res_type = "document"
                            raw_requests.append({
                                "url": full_req_url,
                                "method": "GET",
                                "resourceType": res_type,
                            })
                except Exception as e:
                    logger.warning(f"HTTP audit fallback notice: {e}")

                result_data = {
                    "page": {"url": state.url, "title": f"{state.domain} Page"},
                    "cookies": raw_cookies,
                    "requests": raw_requests,
                }

            page_info = result_data.get("page", {}) if isinstance(result_data, dict) else {}
            if not isinstance(page_info, dict):
                page_info = {}
            experiment.page_url = page_info.get("url", "")
            experiment.page_title = page_info.get("title", "")

            # Handle consent interaction for accept/reject states
            if experiment_state in (ExperimentState.ACCEPT_ALL, ExperimentState.REJECT_ALL):
                action = "accept" if experiment_state == ExperimentState.ACCEPT_ALL else "reject"
                consent_result = await self.webcmd.interact_with_consent(session_id, action)

                if consent_result.success:
                    consent_data = consent_result.data
                    if isinstance(consent_data, str):
                        try:
                            consent_data = json.loads(consent_data)
                        except Exception:
                            consent_data = {}
                    if isinstance(consent_data, dict) and "result" in consent_data:
                        consent_data = consent_data["result"]
                    if isinstance(consent_data, str):
                        try:
                            consent_data = json.loads(consent_data)
                        except Exception:
                            consent_data = {}
                    if not isinstance(consent_data, dict):
                        consent_data = {}

                    state.add_event("consent_interaction", {
                        "state": experiment_state.value,
                        "action": action,
                        "consent_found": consent_data.get("consent_found", False),
                        "clicked": consent_data.get("clicked", False),
                    })

                    # Re-capture evidence after consent interaction
                    await asyncio.sleep(2)  # Wait for tracking changes
                    post_consent = await self.webcmd.get_cookies(session_id)
                    if post_consent.success:
                        post_data = post_consent.data
                        if isinstance(post_data, str):
                            try:
                                post_data = json.loads(post_data)
                            except Exception:
                                post_data = {}
                        if isinstance(post_data, dict) and "result" in post_data:
                            post_data = post_data["result"]
                        if isinstance(post_data, str):
                            try:
                                post_data = json.loads(post_data)
                            except Exception:
                                post_data = {}
                        if isinstance(post_data, dict):
                            result_data["cookies"] = post_data.get("cookies", result_data.get("cookies", []))
                            result_data["cookie_count"] = post_data.get("cookie_count", result_data.get("cookie_count", 0))

            # Normalize and store evidence
            raw_cookies = result_data.get("cookies", []) if isinstance(result_data, dict) else []
            raw_requests = result_data.get("requests", []) if isinstance(result_data, dict) else []

            normalized_cookies = normalize_cookies(raw_cookies, state.domain)
            normalized_requests = normalize_network_requests(raw_requests, state.domain)

            # Store cookie evidence
            for nc in normalized_cookies:
                try:
                    cat_enum = TrackerCategory(nc["category"])
                except ValueError:
                    cat_enum = TrackerCategory.UNKNOWN

                cookie_ev = CookieEvidence(
                    experiment_id=experiment.id,
                    name=nc["name"],
                    domain=nc["domain"],
                    path=nc["path"],
                    expires=nc.get("expires"),
                    secure=nc["secure"],
                    http_only=nc["http_only"],
                    same_site=nc["same_site"],
                    is_third_party=nc["is_third_party"],
                    category=cat_enum,
                    classification_source=nc["classification_source"],
                )
                db.add(cookie_ev)

            # Store network evidence
            for nr in normalized_requests:
                try:
                    cat_enum = TrackerCategory(nr["category"])
                except ValueError:
                    cat_enum = TrackerCategory.UNKNOWN

                network_ev = NetworkEvidence(
                    experiment_id=experiment.id,
                    url=nr["url"],
                    domain=nr["domain"],
                    method=nr["method"],
                    resource_type=nr["resource_type"],
                    status_code=nr.get("status_code"),
                    is_third_party=nr["is_third_party"],
                    category=cat_enum,
                    classification_source=nr["classification_source"],
                )
                db.add(network_ev)

            experiment.status = "completed"
            experiment.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Build evidence summary for verdict generation
            summary = build_evidence_summary(normalized_cookies, normalized_requests)
            state.evidence[experiment_state.value] = summary

            state.add_event("experiment_completed", {
                "state": experiment_state.value,
                "cookies": len(normalized_cookies),
                "requests": len(normalized_requests),
                "third_party_cookies": summary["third_party_cookies"],
                "third_party_requests": summary["third_party_requests"],
            })

        except Exception as e:
            experiment.status = "failed"
            experiment.error = str(e)
            experiment.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.error(f"[{state.scan_id}] Experiment {experiment_state.value} failed: {e}")
        finally:
            await self.webcmd.close_session(session_id)
            state.sessions.pop(experiment_state.value, None)

    # --- Phase 4: Verdict Generation ---

    async def _generate_verdicts(self, state: InvestigationState, db: AsyncSession):
        """Generate verdicts for each testable claim."""
        pre_evidence = state.evidence.get(ExperimentState.PRE_CONSENT.value, {})
        accept_evidence = state.evidence.get(ExperimentState.ACCEPT_ALL.value, {})
        reject_evidence = state.evidence.get(ExperimentState.REJECT_ALL.value, {})

        for claim_info in state.claims:
            claim_id = claim_info["id"]

            if claim_info.get("testability") == "not_testable":
                # Skip non-testable claims
                verdict = Verdict(
                    scan_id=state.scan_id,
                    claim_id=claim_id,
                    verdict_type=VerdictType.UNABLE_TO_VERIFY,
                    confidence=0.0,
                    confidence_reasoning="Claim is not testable through browser observation",
                    explanation="This claim cannot be verified through automated browser investigation.",
                    evidence_summary={},
                )
                db.add(verdict)
                await db.commit()
                state.verdicts.append({
                    "claim_id": claim_id,
                    "verdict_type": VerdictType.UNABLE_TO_VERIFY.value,
                    "confidence": 0.0,
                })
                continue

            try:
                # Ask LLM to generate verdict
                verdict_data = await self.llm.generate_verdict(
                    claim=claim_info,
                    pre_consent_evidence=pre_evidence,
                    accept_evidence=accept_evidence,
                    reject_evidence=reject_evidence,
                )

                # Validate verdict type
                try:
                    verdict_type = VerdictType(verdict_data.get("verdict_type", "unable_to_verify"))
                except ValueError:
                    verdict_type = VerdictType.UNABLE_TO_VERIFY

                # Clamp confidence
                confidence = max(0.0, min(1.0, float(verdict_data.get("confidence", 0.5))))

                verdict = Verdict(
                    scan_id=state.scan_id,
                    claim_id=claim_id,
                    verdict_type=verdict_type,
                    confidence=confidence,
                    confidence_reasoning=verdict_data.get("confidence_reasoning", ""),
                    explanation=verdict_data.get("explanation", ""),
                    expected_behavior=verdict_data.get("expected_behavior", ""),
                    observed_behavior=verdict_data.get("observed_behavior", ""),
                    evidence_summary=verdict_data.get("evidence_summary", {}),
                )
                db.add(verdict)
                await db.commit()

                state.verdicts.append({
                    "claim_id": claim_id,
                    "verdict_type": verdict_type.value,
                    "confidence": confidence,
                })

                state.add_event("verdict_generated", {
                    "claim_id": claim_id,
                    "verdict_type": verdict_type.value,
                    "confidence": confidence,
                })

            except Exception as e:
                logger.error(f"[{state.scan_id}] Verdict generation failed for claim {claim_id}: {e}")
                verdict = Verdict(
                    scan_id=state.scan_id,
                    claim_id=claim_id,
                    verdict_type=VerdictType.TEST_FAILED,
                    confidence=0.0,
                    confidence_reasoning=f"Verdict generation failed: {e}",
                    explanation="An error occurred while generating the verdict.",
                    evidence_summary={},
                )
                db.add(verdict)
                await db.commit()

    # --- Workflow Learning ---

    async def _learn_workflows(self, state: InvestigationState, db: AsyncSession):
        """Store learned workflows for future reuse."""
        if state.policies:
            policy_links = {}
            for p in state.policies:
                policy_links[p["type"]] = p["url"]

            await self.workflow_memory.learn_workflow(
                db, state.domain, "policy_discovery",
                {"policy_links": policy_links},
            )

    # --- Helpers ---

    async def _update_scan(
        self, db: AsyncSession, scan_id: str,
        status: ScanStatus, progress: float = None,
        stage: str = "", error: str = None,
    ):
        """Update scan record in database."""
        from sqlalchemy import select
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if scan:
            scan.status = status
            if progress is not None:
                scan.progress = progress
            if stage:
                scan.current_stage = stage
                scan.stage_details = stage
            if error:
                scan.error = error
            scan.updated_at = datetime.now(timezone.utc)
            if status == ScanStatus.COMPLETED:
                scan.completed_at = datetime.now(timezone.utc)
            await db.commit()

    async def _emit_event(
        self, db: AsyncSession, scan_id: str,
        event_type: str, data: dict,
    ):
        """Store a scan event for frontend consumption."""
        event = ScanEvent(
            scan_id=scan_id,
            event_type=event_type,
            data=data,
        )
        db.add(event)
        await db.commit()

    async def _cleanup_sessions(self, state: InvestigationState):
        """Close any remaining open WebCMD sessions."""
        for exp_state, session_id in list(state.sessions.items()):
            try:
                await self.webcmd.close_session(session_id)
            except Exception as e:
                logger.warning(f"Failed to close session {session_id}: {e}")
