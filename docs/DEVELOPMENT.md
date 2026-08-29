# Development & Operational Guide

## Prerequisites

- **Node.js**: v20+ (tested on Node v24)
- **Python**: v3.12+ (tested on Python 3.14)
- **WebCMD CLI**: Installed globally via `npm install -g @agentrhq/webcmd`
- **CloakBrowser**: Verified via `webcmd doctor`

---

## Environment Setup

1. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   Add your Groq API key in `.env`:
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   LLM_MODEL=llama-3.3-70b-versatile
   LLM_PROVIDER=groq
   ```

2. **Install Python Backend Dependencies**:
   ```bash
   pip install -r pyproject.toml
   # or
   pip install fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy[asyncio] aiosqlite httpx groq python-dotenv sse-starlette
   ```

3. **Install Frontend Dependencies**:
   ```bash
   cd frontend
   npm install
   ```

---

## Running the Application

### 1. Start Backend Server
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/health`

### 2. Start Frontend Dev Server
```bash
cd frontend
npm run dev
```
- Access UI: `http://localhost:3000` (proxies `/api` requests to backend on port 8000)

---

## Running an Automated Scan via CLI / Curl

```bash
# 1. Start a scan
curl -X POST http://127.0.0.1:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{"url": "https://nytimes.com"}'

# 2. Check status
curl http://127.0.0.1:8000/api/scans/<scan-id>/status

# 3. Retrieve final report
curl http://127.0.0.1:8000/api/scans/<scan-id>/report
```
