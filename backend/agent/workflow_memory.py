"""
Workflow Memory — Application-level workflow knowledge for the
Explore → Learn → Reuse loop.

Stores successful navigation paths, consent UI selectors, and policy
page locations per domain. On subsequent scans of the same domain,
previously learned paths are reused before exploring from scratch.

Integrates with WebCMD's sitemap system at ~/.webcmd/sites/<site>/sitemap/
for browser-level navigation memory.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import WorkflowRecord

logger = logging.getLogger(__name__)

# WebCMD sitemap root
WEBCMD_SITES_DIR = os.path.expanduser("~/.webcmd/sites")


class WorkflowMemory:
    """
    Manages the Explore → Learn → Reuse loop.

    On first visit to a domain:
      1. Explore — discover policy pages and consent UI
      2. Learn — store successful paths in DB + WebCMD sitemap
      3. Future visits reuse learned paths

    Uses both:
      - Application DB (WorkflowRecord) for policy-specific memory
      - WebCMD sitemaps for browser navigation memory
    """

    async def get_existing_workflow(
        self, db: AsyncSession, domain: str, workflow_type: str
    ) -> Optional[WorkflowRecord]:
        """Check if we have a learned workflow for this domain."""
        result = await db.execute(
            select(WorkflowRecord).where(
                WorkflowRecord.domain == domain,
                WorkflowRecord.workflow_type == workflow_type,
            )
        )
        record = result.scalar_one_or_none()

        if record:
            logger.info(
                f"Found existing workflow for {domain}/{workflow_type} "
                f"(success: {record.success_count}, fail: {record.failure_count})"
            )
        return record

    async def learn_workflow(
        self,
        db: AsyncSession,
        domain: str,
        workflow_type: str,
        data: dict,
    ) -> WorkflowRecord:
        """Store a learned workflow from successful exploration."""
        # Check for existing
        existing = await self.get_existing_workflow(db, domain, workflow_type)

        if existing:
            # Update existing
            if "navigation_path" in data:
                existing.navigation_path = data["navigation_path"]
            if "consent_ui_selector" in data:
                existing.consent_ui_selector = data["consent_ui_selector"]
            if "policy_links" in data:
                existing.policy_links = data["policy_links"]
            existing.success_count += 1
            existing.last_verified_at = datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
            logger.info(f"Updated workflow for {domain}/{workflow_type}")
            return existing

        # Create new
        record = WorkflowRecord(
            domain=domain,
            workflow_type=workflow_type,
            navigation_path=data.get("navigation_path", []),
            consent_ui_selector=data.get("consent_ui_selector", {}),
            policy_links=data.get("policy_links", {}),
            success_count=1,
            last_verified_at=datetime.now(timezone.utc),
        )
        db.add(record)
        logger.info(f"Learned new workflow for {domain}/{workflow_type}")
        return record

    async def record_failure(
        self, db: AsyncSession, domain: str, workflow_type: str
    ):
        """Record a workflow failure to track reliability."""
        existing = await self.get_existing_workflow(db, domain, workflow_type)
        if existing:
            existing.failure_count += 1
            existing.updated_at = datetime.now(timezone.utc)
            logger.warning(
                f"Workflow failure for {domain}/{workflow_type} "
                f"(total failures: {existing.failure_count})"
            )

    def check_webcmd_sitemap(self, domain: str) -> Optional[dict]:
        """Check if WebCMD has sitemap knowledge for this domain."""
        site_dir = os.path.join(WEBCMD_SITES_DIR, domain, "sitemap")
        if not os.path.isdir(site_dir):
            return None

        sitemap_info = {"path": site_dir, "files": []}
        try:
            for f in os.listdir(site_dir):
                sitemap_info["files"].append(f)
        except OSError:
            pass

        if sitemap_info["files"]:
            logger.info(f"Found WebCMD sitemap for {domain}: {sitemap_info['files']}")
            return sitemap_info
        return None
