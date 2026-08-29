"""
API Routes for Policy Detective.

Endpoints:
  POST /api/scans              — Start a new investigation
  GET  /api/scans/:id          — Get scan status
  GET  /api/scans/:id/status   — Get scan progress (for polling)
  GET  /api/scans/:id/policies — Get discovered policies
  GET  /api/scans/:id/claims   — Get extracted claims
  GET  /api/scans/:id/evidence — Get experiment evidence
  GET  /api/scans/:id/verdicts — Get verdicts
  GET  /api/scans/:id/report   — Get full report
  GET  /api/scans/:id/events   — SSE stream of scan events
"""

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from backend.agent.controller import AgentController
from backend.db.session import get_db, get_session_factory
from backend.models.database import (
    Scan, Policy, PolicyClaim, Experiment, CookieEvidence,
    NetworkEvidence, Verdict, ScanEvent, ScanStatus,
)
from backend.models.schemas import (
    ScanRequest, ScanResponse, PolicyResponse, ClaimResponse,
    ExperimentResponse, CookieEvidenceResponse, NetworkEvidenceResponse,
    VerdictResponse, ScanReportResponse, ScanEventResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# --- Background task runner ---

async def _run_scan_background(scan_id: str, url: str):
    """Run investigation in background with its own DB session."""
    factory = get_session_factory()
    async with factory() as db:
        try:
            controller = AgentController()
            await controller.run_investigation(scan_id, url, db)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Background scan failed: {e}", exc_info=True)
            # Update scan status
            try:
                result = await db.execute(select(Scan).where(Scan.id == scan_id))
                scan = result.scalar_one_or_none()
                if scan:
                    scan.status = ScanStatus.FAILED
                    scan.error = str(e)
                    scan.updated_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass


# --- Endpoints ---

@router.post("/scans", response_model=ScanResponse)
async def create_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a new policy investigation for a website."""
    # Validate URL
    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL")

    domain = parsed.hostname

    # Create scan record
    scan = Scan(url=url, domain=domain, status=ScanStatus.PENDING)
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    scan_id = scan.id
    logger.info(f"Created scan {scan_id} for {url}")

    # Launch investigation in background task
    asyncio.create_task(_run_scan_background(scan_id, url))

    return scan


@router.get("/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get scan details and current status."""
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.get("/scans/{scan_id}/status")
async def get_scan_status(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get scan progress for polling."""
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Get latest events
    events_result = await db.execute(
        select(ScanEvent)
        .where(ScanEvent.scan_id == scan_id)
        .order_by(ScanEvent.created_at.desc())
        .limit(10)
    )
    events = events_result.scalars().all()

    return {
        "id": scan.id,
        "status": scan.status.value if isinstance(scan.status, ScanStatus) else scan.status,
        "progress": scan.progress,
        "current_stage": scan.current_stage,
        "stage_details": scan.stage_details,
        "error": scan.error,
        "recent_events": [
            {"type": e.event_type, "data": e.data, "created_at": e.created_at.isoformat()}
            for e in events
        ],
    }


@router.get("/scans/{scan_id}/policies", response_model=list[PolicyResponse])
async def get_scan_policies(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get discovered policies for a scan."""
    result = await db.execute(
        select(Policy).where(Policy.scan_id == scan_id)
    )
    return result.scalars().all()


@router.get("/scans/{scan_id}/claims", response_model=list[ClaimResponse])
async def get_scan_claims(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get extracted policy claims for a scan."""
    result = await db.execute(
        select(PolicyClaim).where(PolicyClaim.scan_id == scan_id)
    )
    return result.scalars().all()


@router.get("/scans/{scan_id}/evidence")
async def get_scan_evidence(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get experiment evidence for a scan."""
    experiments_result = await db.execute(
        select(Experiment)
        .where(Experiment.scan_id == scan_id)
        .options(
            selectinload(Experiment.cookies),
            selectinload(Experiment.network_requests),
        )
    )
    experiments = experiments_result.scalars().all()

    return [
        {
            "id": exp.id,
            "state": exp.state.value if isinstance(exp.state, str) is False else exp.state,
            "status": exp.status,
            "page_url": exp.page_url,
            "page_title": exp.page_title,
            "started_at": exp.started_at.isoformat() if exp.started_at else None,
            "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
            "error": exp.error,
            "cookies": [
                {
                    "id": c.id,
                    "name": c.name,
                    "domain": c.domain,
                    "path": c.path,
                    "expires": c.expires,
                    "secure": c.secure,
                    "http_only": c.http_only,
                    "same_site": c.same_site,
                    "is_third_party": c.is_third_party,
                    "category": c.category.value if hasattr(c.category, 'value') else c.category,
                    "classification_source": c.classification_source,
                }
                for c in exp.cookies
            ],
            "network_requests": [
                {
                    "id": n.id,
                    "url": n.url,
                    "domain": n.domain,
                    "method": n.method,
                    "resource_type": n.resource_type,
                    "status_code": n.status_code,
                    "is_third_party": n.is_third_party,
                    "category": n.category.value if hasattr(n.category, 'value') else n.category,
                    "classification_source": n.classification_source,
                }
                for n in exp.network_requests
            ],
        }
        for exp in experiments
    ]


@router.get("/scans/{scan_id}/verdicts", response_model=list[VerdictResponse])
async def get_scan_verdicts(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get verdicts for a scan."""
    result = await db.execute(
        select(Verdict).where(Verdict.scan_id == scan_id)
    )
    return result.scalars().all()


@router.get("/scans/{scan_id}/report")
async def get_scan_report(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get complete investigation report."""
    # Scan
    scan_result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Policies
    policies_result = await db.execute(
        select(Policy).where(Policy.scan_id == scan_id)
    )
    policies = policies_result.scalars().all()

    # Claims
    claims_result = await db.execute(
        select(PolicyClaim).where(PolicyClaim.scan_id == scan_id)
    )
    claims = claims_result.scalars().all()

    # Verdicts
    verdicts_result = await db.execute(
        select(Verdict).where(Verdict.scan_id == scan_id)
    )
    verdicts = verdicts_result.scalars().all()

    # Experiments with evidence
    experiments_result = await db.execute(
        select(Experiment)
        .where(Experiment.scan_id == scan_id)
        .options(
            selectinload(Experiment.cookies),
            selectinload(Experiment.network_requests),
        )
    )
    experiments = experiments_result.scalars().all()

    # Build summary
    verdict_counts = {}
    for v in verdicts:
        vt = v.verdict_type.value if hasattr(v.verdict_type, 'value') else v.verdict_type
        verdict_counts[vt] = verdict_counts.get(vt, 0) + 1

    total_cookies = sum(len(exp.cookies) for exp in experiments)
    total_requests = sum(len(exp.network_requests) for exp in experiments)
    third_party_cookies = sum(
        sum(1 for c in exp.cookies if c.is_third_party) for exp in experiments
    )

    summary = {
        "total_claims": len(claims),
        "verdict_breakdown": verdict_counts,
        "consistent": verdict_counts.get("consistent", 0),
        "potential_inconsistencies": verdict_counts.get("potential_inconsistency", 0),
        "strong_inconsistencies": verdict_counts.get("strong_inconsistency", 0),
        "unable_to_verify": verdict_counts.get("unable_to_verify", 0),
        "test_failed": verdict_counts.get("test_failed", 0),
        "total_cookies_observed": total_cookies,
        "third_party_cookies": third_party_cookies,
        "total_network_requests": total_requests,
        "experiments_completed": sum(1 for e in experiments if e.status == "completed"),
        "policies_found": len(policies),
    }

    return {
        "scan": {
            "id": scan.id,
            "url": scan.url,
            "domain": scan.domain,
            "status": scan.status.value if hasattr(scan.status, 'value') else scan.status,
            "progress": scan.progress,
            "current_stage": scan.current_stage,
            "created_at": scan.created_at.isoformat(),
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        },
        "policies": [
            {
                "id": p.id, "url": p.url, "title": p.title,
                "policy_type": p.policy_type, "discovered_via": p.discovered_via,
                "content_preview": p.content[:500] if p.content else "",
            }
            for p in policies
        ],
        "claims": [
            {
                "id": c.id, "category": c.category.value if hasattr(c.category, 'value') else c.category,
                "claim_text": c.claim_text,
                "testability": c.testability.value if hasattr(c.testability, 'value') else c.testability,
                "test_type": c.test_type,
                "expected_behavior": c.expected_behavior,
            }
            for c in claims
        ],
        "verdicts": [
            {
                "id": v.id, "claim_id": v.claim_id,
                "verdict_type": v.verdict_type.value if hasattr(v.verdict_type, 'value') else v.verdict_type,
                "confidence": v.confidence,
                "confidence_reasoning": v.confidence_reasoning,
                "explanation": v.explanation,
                "expected_behavior": v.expected_behavior,
                "observed_behavior": v.observed_behavior,
                "evidence_summary": v.evidence_summary,
            }
            for v in verdicts
        ],
        "summary": summary,
    }


@router.get("/scans/{scan_id}/events")
async def get_scan_events_sse(scan_id: str, db: AsyncSession = Depends(get_db)):
    """SSE endpoint for real-time scan progress updates."""

    async def event_generator():
        last_event_id = None
        factory = get_session_factory()

        while True:
            async with factory() as session:
                # Check scan status
                scan_result = await session.execute(select(Scan).where(Scan.id == scan_id))
                scan = scan_result.scalar_one_or_none()
                if not scan:
                    yield {"event": "error", "data": '{"message": "Scan not found"}'}
                    return

                # Get new events
                query = select(ScanEvent).where(
                    ScanEvent.scan_id == scan_id
                ).order_by(ScanEvent.created_at.asc())

                if last_event_id:
                    query = query.where(ScanEvent.id > last_event_id)

                events_result = await session.execute(query)
                events = events_result.scalars().all()

                for event in events:
                    import json
                    yield {
                        "event": event.event_type,
                        "data": json.dumps({
                            "id": event.id,
                            **event.data,
                            "timestamp": event.created_at.isoformat(),
                        }),
                    }
                    last_event_id = event.id

                # Send progress heartbeat
                import json
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "status": scan.status.value if hasattr(scan.status, 'value') else scan.status,
                        "progress": scan.progress,
                        "stage": scan.current_stage,
                    }),
                }

                # Stop if scan is terminal
                status_val = scan.status.value if hasattr(scan.status, 'value') else scan.status
                if status_val in ("completed", "failed"):
                    yield {"event": "done", "data": json.dumps({"status": status_val})}
                    return

            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())
