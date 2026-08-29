# 🕵️‍♂️ Policy Detective

> **Agentic Web Investigation System** — Audits stated privacy & cookie policies against real technical web behavior using [WebCMD](https://github.com/agentrhq/webcmd) browser infrastructure.

![Policy Detective Architecture](docs/policy-detective-architecture-updated.jpg)

---

## 🌟 Key Capabilities

- **Autonomous Policy Discovery**: Navigates homepages and footers to locate Privacy Policies, Cookie Policies, and Terms of Service documents.
- **Claim Extraction**: Uses LLM reasoning to convert unstructured legal disclosures into testable technical commitments.
- **3-State Controlled Experiments**: Executes isolated browser sessions across **Pre-Consent**, **Accept-All**, and **Reject-All** states to measure differential tracking behavior.
- **Stealth Browser Infrastructure**: Powered by WebCMD's QuickJS sandboxed Playwright runtime and CloakBrowser Chromium (v146).
- **Layered Tracker Classification**: Deterministic matching against 100+ known analytics/advertising domain signatures + heuristic fallback.
- **Evidence-Backed Verdicts**: Computes confidence scores and generates non-accusatory findings backed by captured network requests and cookie metadata.
- **Explore → Learn → Reuse Loop**: Persists successful navigation paths and sitemap knowledge for instantaneous re-audits.

---

## 🏗️ Architecture Overview

```
USER
  ↓
Frontend (React 19 + TypeScript + Tailwind CSS v4)
  ↓
FastAPI Backend Orchestrator
  ├── Agent Controller
  ├── Investigation State Machine
  ├── Action Validator (SSRF & Security Allowlist)
  ├── Recovery Manager (7-Step Escalation)
  ├── Evidence Manager & Layered Classifier
  ├── Verdict Engine
  └── Workflow Memory (Explore → Learn → Reuse)
  ↓
WebCMD Browser Infrastructure (CloakBrowser Stealth Chromium)
  ↓
REAL TARGET WEBSITE (Homepage, Policies, Consent Banners)
  ↓
Evidence Extraction Engine → Verdict Engine → Live UI Report
```

---

## 🚀 Quick Start

### 1. Requirements
- Node.js v20+
- Python 3.12+
- WebCMD CLI: `npm install -g @agentrhq/webcmd`

### 2. Setup
```bash
# Clone & install backend dependencies
cp .env.example .env
# Set your GROQ_API_KEY in .env

pip install fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy[asyncio] aiosqlite httpx groq python-dotenv sse-starlette

# Install frontend dependencies
cd frontend
npm install
```

### 3. Launch
```bash
# Terminal 1 — Backend:
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — Frontend:
cd frontend
npm run dev
```

Visit **`http://localhost:3000`** in your browser.

---

## 📚 Documentation

- [System Architecture](docs/ARCHITECTURE.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [WebCMD Integration Details](docs/WEBCMD_INTEGRATION.md)
- [Security & Safety Safeguards](docs/SECURITY.md)
- [Development Guide](docs/DEVELOPMENT.md)

---

## 🔒 Security & Privacy Notice
Policy Detective runs in isolated temporary browser contexts. Raw cookie values and user credentials are never recorded or stored. Findings describe technical alignment between stated disclosures and observable telemetry.
