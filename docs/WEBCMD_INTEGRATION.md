# WebCMD Integration Architecture

Policy Detective utilizes [WebCMD](https://github.com/agentrhq/webcmd) as its core browser and HTTP agent infrastructure.

## 1. Verified CLI Commands Used

All WebCMD commands are wrapped in `backend/webcmd/adapter.py`:

| Operation | CLI Command | Purpose |
|---|---|---|
| Health Check | `webcmd doctor` | Ensures daemon on port 9777 & CloakBrowser are ready |
| HTTP Fetch | `webcmd web fetch --url <url> -f json` | High-speed, local readability content extraction |
| Create Session | `webcmd --profile <profile> session create -f json` | Creates an isolated browser context |
| List Sessions | `webcmd session list -f json` | Monitors active session states |
| Close Session | `webcmd session close <session-id>` | Cleanly destroys browser workspace |
| Run Script | `webcmd --session <id> browser run --stdin` | Executes Playwright in QuickJS sandbox |
| Page Snapshot | `webcmd --session <id> browser snapshot --snapshot-mode act/read` | Accessibility tree inspection |
| List Tabs | `webcmd --session <id> browser tabs` | Inspects open pages in session |

---

## 2. Browser Sandbox Rules (QuickJS)

1. **DOM Access**:
   All DOM interactions run inside `page.evaluate()`:
   ```javascript
   const title = await page.evaluate(() => document.title);
   ```

2. **Network Request Interception**:
   Request and response listeners are armed *before* triggering navigation:
   ```javascript
   const requests = [];
   page.on('request', req => {
     requests.push({ url: req.url(), method: req.method(), resourceType: req.resourceType() });
   });
   await page.goto(url, { waitUntil: 'networkidle' });
   ```

3. **Cookie Extraction**:
   Extracted safely from context:
   ```javascript
   const cookies = await context.cookies();
   ```

4. **Consent Interaction**:
   Semantic locators (`getByRole`, `getByText`) find and click consent buttons (`Accept All` / `Reject All`) without brittle CSS selectors.

---

## 3. Session Isolation & Safety

- Each scan experiment generates a brand-new WebCMD session ID (`session_<uuid>`).
- Sessions are strictly destroyed on completion or failure.
- No user personal profiles or auth secrets are shared.
