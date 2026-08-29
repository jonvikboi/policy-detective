# Policy Detective — Implementation Plan

## Architecture Mapping

### Layers (from architecture diagram)

1. **User Layer** — User provides website URL + policy question
2. **Application Layer** — Next.js Frontend (Policy Detective UI)
3. **Agent / Reasoning Layer** — Python Agent Orchestrator + LLM + Action Validator
4. **WebCMD Layer** — Browser-Agent Infrastructure (Control, Memory/Learning, Authoring/Reuse)
5. **Real Website Layer** — Target website pages (homepage, FAQ, policy pages, etc.)
6. **Evidence / Decision Layer** — Evidence Extraction Engine + Policy Verdict Engine
7. **Output Layer** — Structured Result back to frontend

### Component Mapping

| Architecture Component | Implementation |
|---|---|
| Frontend — Policy Detective UI | Next.js + TypeScript + Tailwind + shadcn/ui |
| Python Agent Orchestrator | FastAPI + async Python |
| Agent Controller | `backend/agent/controller.py` |
| Investigation State | `backend/agent/state.py` (Pydantic models + DB) |
| Action Planner | `backend/agent/planner.py` (LLM-driven) |
| Action Validator | `backend/agent/validator.py` (allowlist-based) |
| Recovery Manager | `backend/agent/recovery.py` |
| Evidence Manager | `backend/agent/evidence.py` |
| Verdict Coordinator | `backend/agent/verdict.py` |
| Workflow Memory | `backend/agent/workflow_memory.py` + WebCMD sitemaps |
| LLM / Reasoning Engine | `backend/llm/provider.py` (abstracted) |
| Action Validator (allowlist) | `backend/agent/validator.py` |
| WebCMD Adapter | `backend/webcmd/adapter.py` |
| Evidence Extraction Engine | `backend/evidence/extractor.py` |
| Policy Verdict Engine | `backend/verdict/engine.py` |
| Tracker Classification | `backend/evidence/classifier.py` |

## WebCMD Integration Points

### Verified Capabilities (from installed CLI v0.7.4)

| Capability | WebCMD Command | Status |
|---|---|---|
| HTTP fetch | `webcmd web fetch --url <url>` | ✅ Built-in |
| Session create | `webcmd session create -f json` | ✅ Works |
| Session list | `webcmd session list` | ✅ Works |
| Session close | `webcmd session close <id>` | ✅ Works |
| Browser navigate | `webcmd --session <id> browser run --stdin` (with `page.goto`) | ✅ Works |
| Browser snapshot | `webcmd --session <id> browser snapshot --snapshot-mode act/tree/read` | ✅ Works |
| Browser run (Playwright) | `webcmd --session <id> browser run --file <path>` | ✅ Works |
| Network capture | `page.on('response', ...)` inside `browser run` | ✅ Via Playwright |
| Cookie extraction | `page.context().cookies()` inside `browser run` | ✅ Via Playwright |
| Local storage | `page.evaluate(() => localStorage)` inside `browser run` | ✅ Via page.evaluate |
| Sitemap/workflow | `~/.webcmd/sites/<site>/sitemap/` files | ✅ File-based |
| Plugin discovery | `webcmd plugin search <query>` | ✅ Available |

### Key Constraints

- `browser run` executes in QuickJS sandbox (not Node, not browser)
- DOM access requires `page.evaluate()`
- No filesystem access from browser run
- Artifacts via `writeArtifact()` for file output
- Sessions are isolated browser workspaces
- Each `run` gets fresh JS scope, browser state persists

### WebCMD Adapter Design

```python
class WebCMDAdapter:
    async def create_session() -> str
    async def close_session(session_id: str)
    async def navigate(session_id: str, url: str) -> dict
    async def snapshot(session_id: str, mode: str) -> dict
    async def run_script(session_id: str, script: str) -> dict
    async def get_cookies(session_id: str) -> list[dict]
    async def capture_network(session_id: str, url: str, script: str) -> dict
    async def fetch_url(url: str) -> dict
    async def extract_page_content(session_id: str) -> dict
```

All methods shell out to `webcmd` CLI commands.

## Implementation Phases

### Phase 1: Project Initialization + WebCMD Integration
- Project structure (backend + frontend)
- FastAPI skeleton with health checks
- WebCMD adapter module
- Next.js frontend scaffold
- Database setup (SQLite for MVP, PostgreSQL-ready)

### Phase 2: Frontend Scan Flow
- Landing page with URL input
- Investigation progress page
- Results dashboard skeleton
- API integration layer

### Phase 3: Policy Discovery
- Homepage fetching via WebCMD
- Footer/navigation link extraction
- Policy page identification
- Recovery strategies (search, related links)

### Phase 4: Policy Claim Extraction
- Policy text parsing
- LLM-based claim extraction
- Claim categorization and testability scoring
- Structured claim output

### Phase 5: Agent Orchestrator
- Agent controller with state machine
- Action planner (LLM-driven)
- Action validator with allowlist
- Investigation state management

### Phase 6: Browser Investigation
- Controlled browser experiments
- Pre-consent capture
- Accept-all capture
- Reject-all capture

### Phase 7: Evidence Collection
- Cookie evidence extraction
- Network request capture
- Third-party domain identification
- Evidence normalization

### Phase 8: Tracker Classification
- Known tracker domain lists
- First/third party analysis
- URL pattern heuristics
- Classification pipeline

### Phase 9: Verdict Engine
- Policy vs. evidence comparison
- Verdict generation (CONSISTENT, POTENTIAL_INCONSISTENCY, etc.)
- Confidence scoring
- Evidence-backed reasoning

### Phase 10: Recovery + Workflow Memory
- Retry logic
- Browser escalation
- Site search fallback
- WebCMD sitemap integration
- Workflow learning

### Phase 11: Dashboard + Reporting
- Full results display
- Finding details with evidence
- Report generation
- Live progress updates via SSE

### Phase 12: Security + Testing + Polish
- Input validation
- Session isolation
- Prompt injection protection
- Unit/integration tests

## MVP Scope

The first working milestone:
1. Enter URL → Find privacy policy → Extract 3-5 testable claims
2. Create WebCMD browser sessions (3 states)
3. Pre-consent / Accept / Reject experiments
4. Capture cookies + network evidence
5. Compare against policy claims
6. Generate verdicts with confidence
7. Display in UI with evidence

## Database (MVP)

Using SQLite for MVP simplicity (SQLAlchemy models are PostgreSQL-compatible).

## Known Limitations

1. WebCMD has no built-in "network capture" command — we intercept via Playwright `page.on('response')` inside `browser run`
2. Sitemap/workflow memory is file-based, not a database API
3. Cookie values should not be stored (security) — store metadata only
4. PDF extraction requires additional tooling (not in WebCMD)
5. Some consent UIs are highly dynamic and may need adaptive interaction strategies
