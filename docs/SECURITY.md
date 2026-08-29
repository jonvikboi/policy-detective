# Security & Safety Architecture

Policy Detective investigates live, third-party websites. Therefore, every target site is treated as **untrusted** and potentially hostile.

## 1. Threat Mitigations

### A. Server-Side Request Forgery (SSRF) Protection
- All URLs pass through `backend/agent/validator.py:validate_url()`:
  - Blocks `localhost`, `127.0.0.1`, `0.0.0.0`.
  - Blocks private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
  - Blocks cloud instance metadata endpoints (`169.254.169.254`, `metadata.google`, `metadata.aws`).
  - Blocks non-HTTP protocols (`file://`, `ftp://`, `data://`, `javascript://`).

### B. Prompt Injection Protection
- Webpage content is treated strictly as data, never as prompt instructions.
- System instructions explicitly forbid page text from modifying investigation goals or executing commands.

### C. Action Allowlist Boundary
- The LLM cannot execute arbitrary shell or browser commands directly.
- All actions pass through `validate_action()` allowlist:
  - `fetch_url`, `navigate`, `snapshot`, `click`, `extract_links`, `extract_content`, `get_cookies`, `capture_evidence`, `interact_consent`, `conclude`.
  - Unrecognized actions are immediately rejected.

### D. Privacy & Secret Protection
- **No Cookie Values Stored**: Only cookie names, domains, expiry timestamps, flags (`Secure`, `HttpOnly`, `SameSite`), and tracker classifications are retained.
- **No Credential Harvesting**: Forms containing passwords or payment fields are ignored.

### E. Session Isolation
- Every experiment (Pre-Consent, Accept-All, Reject-All) runs in a distinct WebCMD browser context.
- Residual browser storage is discarded on session closure.
