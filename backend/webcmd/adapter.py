"""
WebCMD Adapter — Single integration point between Policy Detective and WebCMD.

All WebCMD interactions go through this adapter. The agent orchestrator
calls clean Python methods; this module translates them into webcmd CLI
invocations and parses the structured JSON output.

Key WebCMD capabilities used:
- webcmd web fetch --url <url>                   → HTTP fetch (no browser)
- webcmd session create -f json                  → create browser session
- webcmd session close <id>                      → close browser session
- webcmd --session <id> browser run --stdin       → execute Playwright script
- webcmd --session <id> browser snapshot          → page accessibility snapshot
- webcmd --session <id> browser tabs              → list open pages

Browser run executes in a QuickJS sandbox with Playwright handles.
DOM access requires page.evaluate(). No Node APIs (fs, Buffer, etc.).
"""

import asyncio
import json
import logging
import shutil
import tempfile
import os
from dataclasses import dataclass, field
from typing import Optional

from backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class WebCMDResult:
    """Structured result from a WebCMD command."""
    success: bool
    data: dict | list | str = field(default_factory=dict)
    error: Optional[str] = None
    raw_output: str = ""


class WebCMDAdapter:
    """
    Adapter between Policy Detective and the WebCMD CLI.

    All browser operations are routed through this class.
    The rest of the application never calls webcmd directly.
    """

    def __init__(self):
        settings = get_settings()
        # Resolve full binary path (finds global PATH, node_modules/.bin, or Windows CMD)
        local_bin_1 = os.path.abspath(os.path.join("node_modules", ".bin", "webcmd"))
        local_bin_2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "node_modules", ".bin", "webcmd"))
        resolved = (
            shutil.which(settings.webcmd_binary)
            or (local_bin_1 if os.path.exists(local_bin_1) else None)
            or (local_bin_2 if os.path.exists(local_bin_2) else None)
        )
        self.binary = resolved or settings.webcmd_binary
        self.profile = settings.webcmd_profile
        self.timeout = settings.webcmd_timeout

    async def _run_command(
        self,
        args: list[str],
        stdin_data: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> WebCMDResult:
        """Execute a webcmd command and return parsed result."""
        cmd = [self.binary] + args
        effective_timeout = timeout or self.timeout
        cmd_str = " ".join(cmd)
        logger.info(f"WebCMD: {cmd_str}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=stdin_data.encode() if stdin_data else None),
                timeout=effective_timeout,
            )

            output = stdout.decode("utf-8", errors="replace").strip()
            err_output = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode != 0:
                logger.warning(f"WebCMD failed (exit {process.returncode}): {err_output or output}")
                # Try to parse error JSON
                try:
                    err_data = json.loads(output)
                    return WebCMDResult(
                        success=False,
                        error=err_data.get("error", {}).get("message", err_output or output),
                        data=err_data,
                        raw_output=output,
                    )
                except (json.JSONDecodeError, AttributeError):
                    return WebCMDResult(
                        success=False,
                        error=err_output or output,
                        raw_output=output,
                    )

            # Try to parse JSON output
            try:
                data = json.loads(output)
                return WebCMDResult(success=True, data=data, raw_output=output)
            except json.JSONDecodeError:
                return WebCMDResult(success=True, data=output, raw_output=output)

        except asyncio.TimeoutError:
            logger.error(f"WebCMD timeout after {effective_timeout}s: {cmd_str}")
            return WebCMDResult(success=False, error=f"Command timed out after {effective_timeout}s")
        except FileNotFoundError:
            logger.error(f"WebCMD binary not found: {self.binary}")
            return WebCMDResult(success=False, error=f"WebCMD binary not found: {self.binary}")
        except Exception as e:
            logger.error(f"WebCMD error: {e}")
            return WebCMDResult(success=False, error=str(e))

    # --- Session Management ---

    async def create_session(self) -> WebCMDResult:
        """Create a new isolated browser session. Returns session ID."""
        result = await self._run_command(
            ["--profile", self.profile, "session", "create", "-f", "json"]
        )
        if result.success and isinstance(result.data, dict):
            logger.info(f"Created WebCMD session: {result.data.get('id')}")
        return result

    async def close_session(self, session_id: str) -> WebCMDResult:
        """Close a browser session and release resources."""
        result = await self._run_command(
            ["--profile", self.profile, "session", "close", session_id]
        )
        logger.info(f"Closed WebCMD session: {session_id}")
        return result

    async def get_version(self) -> WebCMDResult:
        """Get the WebCMD CLI version."""
        return await self._run_command(["--version"])

    async def list_sessions(self) -> WebCMDResult:
        """List active browser sessions."""
        return await self._run_command(["session", "list", "-f", "json"])

    # --- Navigation & Page Interaction ---

    async def navigate(self, session_id: str, url: str) -> WebCMDResult:
        """Navigate to a URL and return page info + snapshot diff."""
        script = f"""
let navError = null;
for (let i = 0; i < 2; i++) {{
    try {{
        await page.goto({json.dumps(url)}, {{ waitUntil: 'domcontentloaded', timeout: 30000 }});
        navError = null;
        break;
    }} catch (err) {{
        navError = err;
        await new Promise(r => setTimeout(r, 1500));
    }}
}}
if (navError) throw navError;
return {{
    url: page.url(),
    title: await page.title(),
}};
"""
        return await self._run_script(session_id, script)

    async def snapshot(self, session_id: str, mode: str = "act") -> WebCMDResult:
        """Take a page snapshot. Modes: act, tree, read."""
        return await self._run_command([
            "--session", session_id,
            "browser", "snapshot",
            "--snapshot-mode", mode,
        ])

    async def extract_page_content(self, session_id: str) -> WebCMDResult:
        """Extract readable text content from the current page."""
        return await self.snapshot(session_id, mode="read")

    async def extract_links(self, session_id: str) -> WebCMDResult:
        """Extract all links from the current page with priority for policy keywords."""
        script = """
const links = await page.evaluate(() => {
    const all = Array.from(document.querySelectorAll('a[href]'));
    const prioritized = [];
    const others = [];

    for (const a of all) {
        const text = (a.innerText || a.textContent || '').trim().substring(0, 200);
        const href = a.href;
        if (!href || !href.startsWith('http')) continue;

        const textLower = text.toLowerCase();
        const hrefLower = href.toLowerCase();
        const item = { text: text, href: href, rel: a.getAttribute('rel') || '' };

        if (
            textLower.includes('priva') || textLower.includes('cookie') || textLower.includes('term') ||
            textLower.includes('legal') || textLower.includes('policy') || textLower.includes('tos') ||
            hrefLower.includes('priva') || hrefLower.includes('cookie') || hrefLower.includes('term') ||
            hrefLower.includes('policy')
        ) {
            prioritized.push(item);
        } else {
            others.push(item);
        }
    }

    return [...prioritized, ...others].slice(0, 400);
});
return { url: page.url(), links: links };
"""
        return await self._run_script(session_id, script, no_snapshot_diff=True)

    # --- Browser Run ---

    async def _run_script(
        self,
        session_id: str,
        script: str,
        no_snapshot_diff: bool = False,
        timeout: Optional[int] = None,
    ) -> WebCMDResult:
        """Execute a Playwright script in the browser session's QuickJS sandbox."""
        args = [
            "--session", session_id,
            "browser", "run", "--stdin",
        ]
        if no_snapshot_diff:
            args.append("--no-snapshot-diff")
        if timeout:
            args.extend(["--timeout", str(timeout)])

        return await self._run_command(args, stdin_data=script, timeout=timeout or self.timeout)

    async def run_script(self, session_id: str, script: str, **kwargs) -> WebCMDResult:
        """Public interface for running arbitrary validated scripts."""
        return await self._run_script(session_id, script, **kwargs)

    # --- Evidence Collection ---

    async def get_cookies(self, session_id: str) -> WebCMDResult:
        """Extract all cookies from the current browser context."""
        script = """
const cookies = await context.cookies();
return {
    url: page.url(),
    cookie_count: cookies.length,
    cookies: cookies.map(c => ({
        name: c.name,
        domain: c.domain,
        path: c.path,
        expires: c.expires,
        secure: c.secure,
        httpOnly: c.httpOnly,
        sameSite: c.sameSite || '',
    })),
};
"""
        return await self._run_script(session_id, script, no_snapshot_diff=True)

    async def capture_network_and_cookies(
        self, session_id: str, url: str, wait_seconds: int = 5
    ) -> WebCMDResult:
        """
        Navigate to URL, capture network requests and cookies.
        This is the core evidence collection script for controlled experiments.

        Captures:
        - All network requests (URL, domain, method, resource type, status)
        - All cookies after page load
        - Page metadata
        """
        script = f"""
const requests = [];
const responses = [];

// Arm network listeners BEFORE navigation
page.on('request', request => {{
    requests.push({{
        url: request.url(),
        method: request.method(),
        resourceType: request.resourceType(),
        isNavigationRequest: request.isNavigationRequest(),
    }});
}});

page.on('response', response => {{
    responses.push({{
        url: response.url(),
        status: response.status(),
    }});
}});

// Navigate with domcontentloaded
try {{
    await page.goto({json.dumps(url)}, {{ waitUntil: 'domcontentloaded', timeout: 20000 }});
}} catch (e) {{
    // Continue collecting evidence even if background assets take longer
}}

// Wait for additional async requests
await page.waitForTimeout({wait_seconds * 1000});

// Collect cookies
const cookies = await context.cookies();

return {{
    page: {{
        url: page.url(),
        title: await page.title(),
    }},
    request_count: requests.length,
    requests: requests.slice(0, 500).map(r => ({{
        url: r.url,
        method: r.method,
        resourceType: r.resourceType,
    }})),
    response_count: responses.length,
    cookie_count: cookies.length,
    cookies: cookies.map(c => ({{
        name: c.name,
        domain: c.domain,
        path: c.path,
        expires: c.expires,
        secure: c.secure,
        httpOnly: c.httpOnly,
        sameSite: c.sameSite || '',
    }})),
}};
"""
        return await self._run_script(
            session_id, script, no_snapshot_diff=True, timeout=60
        )

    async def interact_with_consent(
        self, session_id: str, action: str = "accept"
    ) -> WebCMDResult:
        """
        Find and interact with cookie consent UI.
        action: 'accept' or 'reject'

        Uses semantic locators (getByRole, getByText) to find consent buttons.
        Returns what was clicked and the resulting page state.
        """
        if action == "accept":
            button_patterns = """
const patterns = [
    /accept\\s*(all)?/i,
    /agree/i,
    /allow\\s*(all)?\\s*(cookies)?/i,
    /i\\s*agree/i,
    /got\\s*it/i,
    /ok/i,
    /consent/i,
];
"""
        else:
            button_patterns = """
const patterns = [
    /reject\\s*(all)?/i,
    /decline\\s*(all)?/i,
    /deny/i,
    /refuse/i,
    /necessary\\s*only/i,
    /essential\\s*only/i,
];
"""

        script = f"""
// First, take a snapshot of consent-related elements
const consentSelectors = [
    '[class*="cookie"]',
    '[class*="consent"]',
    '[class*="gdpr"]',
    '[class*="privacy"]',
    '[id*="cookie"]',
    '[id*="consent"]',
    '[id*="gdpr"]',
    '[role="dialog"]',
    '[class*="banner"]',
    '[class*="modal"]',
    '[class*="popup"]',
    '[class*="notice"]',
];

const consentElements = await page.evaluate((selectors) => {{
    for (const sel of selectors) {{
        const el = document.querySelector(sel);
        if (el && el.offsetHeight > 0) {{
            return {{
                found: true,
                selector: sel,
                text: el.innerText.substring(0, 500),
                html: el.outerHTML.substring(0, 1000),
            }};
        }}
    }}
    return {{ found: false }};
}}, consentSelectors);

if (!consentElements.found) {{
    return {{
        consent_found: false,
        action: '{action}',
        message: 'No consent UI detected on page',
    }};
}}

{button_patterns}

// Try each pattern with getByRole button first
let clicked = false;
let clickedText = '';

for (const pattern of patterns) {{
    try {{
        const btn = page.getByRole('button', {{ name: pattern }});
        if (await btn.count() > 0) {{
            await btn.first().click({{ timeout: 5000 }});
            clicked = true;
            clickedText = await btn.first().innerText();
            break;
        }}
    }} catch (e) {{
        // continue to next pattern
    }}
}}

// Fallback: try links with those texts
if (!clicked) {{
    for (const pattern of patterns) {{
        try {{
            const link = page.getByRole('link', {{ name: pattern }});
            if (await link.count() > 0) {{
                await link.first().click({{ timeout: 5000 }});
                clicked = true;
                clickedText = await link.first().innerText();
                break;
            }}
        }} catch (e) {{
            // continue
        }}
    }}
}}

// Wait for consent UI to dismiss
if (clicked) {{
    await page.waitForTimeout(2000);
}}

return {{
    consent_found: consentElements.found,
    action: '{action}',
    clicked: clicked,
    clicked_text: clickedText,
    url: page.url(),
}};
"""
        return await self._run_script(session_id, script, timeout=30)

    # --- HTTP Fetch (no browser) ---

    async def fetch_url(self, url: str) -> WebCMDResult:
        """Fetch a URL using WebCMD's HTTP fetch (no browser needed)."""
        return await self._run_command([
            "web", "fetch", "--url", url, "-f", "json",
        ], timeout=30)

    # --- Utility ---

    async def check_health(self) -> WebCMDResult:
        """Check if WebCMD is operational."""
        return await self._run_command(["--version"])

    async def get_page_info(self, session_id: str) -> WebCMDResult:
        """Get current page URL and title."""
        script = """
return {
    url: page.url(),
    title: await page.title(),
};
"""
        return await self._run_script(session_id, script, no_snapshot_diff=True)
