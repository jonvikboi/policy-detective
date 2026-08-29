"""
MongoDB database module for Policy Detective using Motor (async driver).

Provides connection management, index initialization, and CRUD operations
for scans, policies, claims, experiments, evidence, verdicts, events, and workflows.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from backend.config import get_settings

logger = logging.getLogger(__name__)

_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None


def new_id() -> str:
    """Generate a unique string ID."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


async def get_mongo_client() -> AsyncIOMotorClient:
    """Get or initialize the global AsyncIOMotorClient."""
    global _mongo_client
    if _mongo_client is None:
        settings = get_settings()
        _mongo_client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
        )
    return _mongo_client


async def get_mongo_db() -> AsyncIOMotorDatabase:
    """Get or initialize the global MongoDB database."""
    global _mongo_db
    if _mongo_db is None:
        client = await get_mongo_client()
        settings = get_settings()
        _mongo_db = client[settings.mongodb_db_name]
    return _mongo_db


async def init_mongo_db():
    """Initialize MongoDB collections and create optimal performance indexes."""
    try:
        db = await get_mongo_db()
        # Verify connection
        await db.command("ping")
        logger.info("Connected to MongoDB successfully.")

        # Create indexes
        await db.scans.create_index([("created_at", -1)])
        await db.policies.create_index([("scan_id", 1)])
        await db.policy_contents.create_index([("scan_id", 1), ("url", 1)])
        await db.claims.create_index([("scan_id", 1), ("policy_id", 1)])
        await db.experiments.create_index([("scan_id", 1), ("state", 1)])
        await db.cookie_evidence.create_index([("experiment_id", 1)])
        await db.network_evidence.create_index([("experiment_id", 1)])
        await db.verdicts.create_index([("scan_id", 1), ("claim_id", 1)])
        await db.scan_events.create_index([("scan_id", 1), ("created_at", 1)])
        await db.workflow_records.create_index([("domain", 1), ("workflow_type", 1)], unique=True)

        logger.info("MongoDB collections and indexes initialized.")
    except Exception as e:
        logger.warning(f"MongoDB connection initialization note: {e}")


async def close_mongo_db():
    """Close the global MongoDB client."""
    global _mongo_client, _mongo_db
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB client connection closed.")


# --- CRUD Helper Operations ---

class MongoRepository:
    """High-level repository operations for Policy Detective entities."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    # Scans
    async def create_scan(self, scan_data: dict) -> dict:
        doc = {
            "_id": scan_data.get("id") or new_id(),
            "url": scan_data["url"],
            "domain": scan_data["domain"],
            "status": scan_data.get("status", "pending"),
            "progress": scan_data.get("progress", 0.0),
            "current_stage": scan_data.get("current_stage", "initializing"),
            "stage_details": scan_data.get("stage_details", ""),
            "error": scan_data.get("error", None),
            "created_at": scan_data.get("created_at") or utcnow(),
            "updated_at": scan_data.get("updated_at") or utcnow(),
            "completed_at": scan_data.get("completed_at", None),
        }
        await self.db.scans.insert_one(doc)
        doc["id"] = doc["_id"]
        return doc

    async def get_scan(self, scan_id: str) -> Optional[dict]:
        doc = await self.db.scans.find_one({"_id": scan_id})
        if doc:
            doc["id"] = doc["_id"]
        return doc

    async def update_scan(
        self,
        scan_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        stage: Optional[str] = None,
        error: Optional[str] = None,
        stage_details: Optional[str] = None,
    ) -> Optional[dict]:
        updates: dict[str, Any] = {"updated_at": utcnow()}
        if status is not None:
            updates["status"] = status
            if status == "completed":
                updates["completed_at"] = utcnow()
        if progress is not None:
            updates["progress"] = progress
        if stage is not None:
            updates["current_stage"] = stage
        if stage_details is not None:
            updates["stage_details"] = stage_details
        if error is not None:
            updates["error"] = error

        await self.db.scans.update_one({"_id": scan_id}, {"$set": updates})
        return await self.get_scan(scan_id)

    # Policies & Policy Content Collections
    async def insert_policy(self, policy_data: dict) -> dict:
        doc = {
            "_id": policy_data.get("id") or new_id(),
            "scan_id": policy_data["scan_id"],
            "url": policy_data["url"],
            "title": policy_data.get("title", ""),
            "policy_type": policy_data.get("policy_type", "privacy"),
            "content": policy_data.get("content", ""),
            "content_length": len(policy_data.get("content", "")),
            "discovered_via": policy_data.get("discovered_via", "browser_discovery"),
            "created_at": policy_data.get("created_at") or utcnow(),
        }
        # Insert into both policies and dedicated policy_contents collection
        await self.db.policies.insert_one(doc)
        await self.db.policy_contents.insert_one(dict(doc))
        doc["id"] = doc["_id"]
        return doc

    async def get_policies_by_scan(self, scan_id: str) -> list[dict]:
        cursor = self.db.policies.find({"scan_id": scan_id})
        policies = []
        async for doc in cursor:
            doc["id"] = doc["_id"]
            policies.append(doc)
        return policies

    # Claims
    async def insert_claim(self, claim_data: dict) -> dict:
        doc = {
            "_id": claim_data.get("id") or new_id(),
            "scan_id": claim_data["scan_id"],
            "policy_id": claim_data.get("policy_id", ""),
            "category": claim_data.get("category", "cookies"),
            "claim_text": claim_data.get("claim_text", ""),
            "testability": claim_data.get("testability", "automatable"),
            "test_type": claim_data.get("test_type", ""),
            "expected_behavior": claim_data.get("expected_behavior", {}),
            "source_section": claim_data.get("source_section", ""),
            "created_at": claim_data.get("created_at") or utcnow(),
        }
        await self.db.claims.insert_one(doc)
        doc["id"] = doc["_id"]
        return doc

    async def get_claims_by_scan(self, scan_id: str) -> list[dict]:
        cursor = self.db.claims.find({"scan_id": scan_id})
        claims = []
        async for doc in cursor:
            doc["id"] = doc["_id"]
            claims.append(doc)
        return claims

    # Experiments
    async def insert_experiment(self, exp_data: dict) -> dict:
        doc = {
            "_id": exp_data.get("id") or new_id(),
            "scan_id": exp_data["scan_id"],
            "state": exp_data["state"],
            "status": exp_data.get("status", "running"),
            "webcmd_session_id": exp_data.get("webcmd_session_id", ""),
            "page_url": exp_data.get("page_url", ""),
            "page_title": exp_data.get("page_title", ""),
            "error": exp_data.get("error", None),
            "started_at": exp_data.get("started_at") or utcnow(),
            "completed_at": exp_data.get("completed_at", None),
        }
        await self.db.experiments.insert_one(doc)
        doc["id"] = doc["_id"]
        return doc

    async def update_experiment(self, exp_id: str, updates: dict):
        await self.db.experiments.update_one({"_id": exp_id}, {"$set": updates})

    async def get_experiments_by_scan(self, scan_id: str) -> list[dict]:
        cursor = self.db.experiments.find({"scan_id": scan_id})
        exps = []
        async for doc in cursor:
            doc["id"] = doc["_id"]
            exps.append(doc)
        return exps

    # Cookie & Network Evidence
    async def insert_cookie_evidence_batch(self, experiment_id: str, cookies: list[dict]):
        if not cookies:
            return
        docs = []
        for c in cookies:
            docs.append({
                "_id": new_id(),
                "experiment_id": experiment_id,
                "name": c.get("name", ""),
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
                "expires": c.get("expires"),
                "secure": c.get("secure", False),
                "http_only": c.get("http_only", False),
                "same_site": c.get("same_site", ""),
                "is_third_party": c.get("is_third_party", False),
                "category": c.get("category", "unknown"),
                "classification_source": c.get("classification_source", ""),
                "created_at": utcnow(),
            })
        await self.db.cookie_evidence.insert_many(docs)

    async def insert_network_evidence_batch(self, experiment_id: str, requests: list[dict]):
        if not requests:
            return
        docs = []
        for r in requests:
            docs.append({
                "_id": new_id(),
                "experiment_id": experiment_id,
                "url": r.get("url", ""),
                "domain": r.get("domain", ""),
                "method": r.get("method", "GET"),
                "resource_type": r.get("resource_type", ""),
                "status_code": r.get("status_code"),
                "initiator": r.get("initiator", ""),
                "is_third_party": r.get("is_third_party", False),
                "category": r.get("category", "unknown"),
                "classification_source": r.get("classification_source", ""),
                "created_at": utcnow(),
            })
        await self.db.network_evidence.insert_many(docs)

    # Verdicts
    async def insert_verdict(self, verdict_data: dict) -> dict:
        doc = {
            "_id": verdict_data.get("id") or new_id(),
            "scan_id": verdict_data["scan_id"],
            "claim_id": verdict_data["claim_id"],
            "verdict_type": verdict_data.get("verdict_type", "unable_to_verify"),
            "confidence": float(verdict_data.get("confidence", 0.0)),
            "confidence_reasoning": verdict_data.get("confidence_reasoning", ""),
            "explanation": verdict_data.get("explanation", ""),
            "expected_behavior": verdict_data.get("expected_behavior", {}),
            "observed_behavior": verdict_data.get("observed_behavior", {}),
            "evidence_summary": verdict_data.get("evidence_summary", {}),
            "created_at": verdict_data.get("created_at") or utcnow(),
        }
        await self.db.verdicts.insert_one(doc)
        doc["id"] = doc["_id"]
        return doc

    async def get_verdicts_by_scan(self, scan_id: str) -> list[dict]:
        cursor = self.db.verdicts.find({"scan_id": scan_id})
        verdicts = []
        async for doc in cursor:
            doc["id"] = doc["_id"]
            verdicts.append(doc)
        return verdicts

    # Scan Events
    async def insert_event(self, scan_id: str, event_type: str, data: dict) -> dict:
        doc = {
            "_id": new_id(),
            "scan_id": scan_id,
            "event_type": event_type,
            "data": data,
            "created_at": utcnow(),
        }
        await self.db.scan_events.insert_one(doc)
        doc["id"] = doc["_id"]
        return doc

    async def get_events_by_scan(self, scan_id: str, limit: int = 50) -> list[dict]:
        cursor = self.db.scan_events.find({"scan_id": scan_id}).sort("created_at", 1).limit(limit)
        events = []
        async for doc in cursor:
            doc["id"] = doc["_id"]
            events.append(doc)
        return events

    # Workflows
    async def save_workflow(self, domain: str, workflow_type: str, data: dict):
        doc = {
            "domain": domain,
            "workflow_type": workflow_type,
            "policy_links": data.get("policy_links", {}),
            "consent_ui_selector": data.get("consent_ui_selector", {}),
            "updated_at": utcnow(),
        }
        await self.db.workflow_records.update_one(
            {"domain": domain, "workflow_type": workflow_type},
            {"$set": doc, "$inc": {"success_count": 1}, "$setOnInsert": {"_id": new_id(), "created_at": utcnow()}},
            upsert=True,
        )

    async def get_workflow(self, domain: str, workflow_type: str) -> Optional[dict]:
        return await self.db.workflow_records.find_one({"domain": domain, "workflow_type": workflow_type})
