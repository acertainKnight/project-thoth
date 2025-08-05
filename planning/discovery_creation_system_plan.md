# Discovery Creation System – Comprehensive Implementation Plan

## 1. Purpose & Vision
Design and implement a **Discovery Creation System (DCS)** that empowers end-users **and** AI agents to build, run, and maintain custom web-scraping workflows for academic research sites. The system should:

* Launch an interactive browser UI (preferably embedded within Obsidian) where the user/agent can visually navigate a target site.
* Allow selection of search elements, result containers, metadata fields, and PDF download links via point-and-click or programmatic prompts.
* Persist the resulting “Discovery Flow” as a reusable, shareable asset that integrates seamlessly with the existing research-processing pipeline.

---

## 2. Functional Requirements
1. **Interactive Browser Session**
   * Start/stop browser sessions from Obsidian commands or agent actions.
   * Support headful Chromium with remote-control APIs (Puppeteer/Playwright).
   * Provide DOM inspection/highlighting to select elements.
2. **Auth & Session Handling**
   * UI to enter credentials (manual) or delegate to secure credential vault.
   * Support common patterns: login forms, SSO redirects, MFA via TOTP/push.
3. **Flow Builder**
   * Record navigation steps (click, type, wait, scroll) with optional manual editing.
   * Element picker to tag:
     * Search input(s)
     * Submit buttons / filters
     * Result list container & item selector
     * Metadata fields inside each item (title, authors, abstract, date, journal, etc.)
     * PDF/full-text link
   * Allow XPath/CSS fallbacks and robustness rules (e.g., text-based anchors).
4. **Flow Definition Format**
   * Store as versioned JSON/YAML ("discovery.flow.json") containing:
     ```json
     {
       "name": "arXiv",
       "auth": { "type": "none" },
       "steps": [ {"action": "goto", "url": "https://arxiv.org"}, ... ],
       "selectors": {
         "resultItem": "li.arxiv-result",
         "title": "h1.title",
         ...
       },
       "pagination": { "type": "nextButton", "selector": "a[rel=next]" }
     }
     ```
   * Include schema & validation tooling.
5. **Execution Engine**
   * Headless/CI mode to run flows on schedule.
   * Robust retry, throttling, CAPTCHA avoidance hooks.
6. **Integration with Processing Pipeline**
   * Emit normalized `PaperMetadata` objects + PDF URL to downstream queue.
   * Surface mapping errors & new field suggestions.
7. **User Experience in Obsidian**
   * Command palette actions: `DCS: New Flow`, `DCS: Edit Flow`, `DCS: Run Flow`.
   * Sidebar panel showing live DOM, selected elements, property names.
   * Markdown codeblock preview of JSON flow with inline edit.
8. **AI-Assisted Features**
   * Natural-language prompt: “Scrape recent NLP papers from ACL Anthology.” → agent walks site & suggests flow.
   * Autocomplete selectors based on semantic labels (e.g., “title”).
9. **Extensibility**
   * Plugin architecture for custom step types (GraphQL fetch, API auth, etc.).
   * Template gallery (arXiv, PubMed, IEEE Xplore, Springer, etc.).

---

## 3. Non-Functional Requirements
* **Security**: Zero credential leakage, encrypted storage, strict CSP.
* **Portability**: Windows/macOS/Linux; offline development.
* **Observability**: Structured logs, session recording, error screenshots.
* **Performance**: <2 s overhead per navigation step in headless mode.
* **Scalability**: Parallel scraping with isolated browser contexts.

---

## 4. High-Level Architecture
```text
┌──────────────────────┐        ┌───────────────────┐
│ Obsidian Plugin UI   │◀──────▶│ Browser Controller │◀──────┐
└──────────────────────┘        └───────────────────┘       │
        ▲                             ▲                    │
        │                             │                    │
        │  YAML/JSON Flows            │                    │
        ▼                             ▼                    │
┌──────────────────────┐        ┌───────────────────┐       │
│   Flow Repository    │◀──────▶│ Execution Engine  │──────►│Downstream pipeline
└──────────────────────┘        └───────────────────┘       │  (metadata, PDFs)
        ▲                             ▲                    │
        │  AI Suggestions             │ Feedback           │
        ▼                             ▼                    │
┌──────────────────────┐        ┌───────────────────┐       │
│   LLM Agent Layer    │────────┴───────────────────┘       │
└──────────────────────┘                                    │
                                                            │
                         Monitoring & Storage ──────────────┘
```

---

## 5. Detailed Component Design
### 5.1 Obsidian Plugin
* **Tech**: TypeScript, Svelte/React, Obsidian API.
* **Modules**:
  1. Command registrations.
  2. Webview panel embedding live browser (via WebSocket to local server or `webview` tag if Electron sandboxed).
  3. DOM inspector overlay + CSS path capture.
  4. Flow editor with schema-aware form & raw code toggle.

### 5.2 Browser Controller
* **Tech**: Node.js w/ Playwright (robust, Firefox/Chromium/Webkit).
* **Capabilities**:
  * Launch headful or headless.
  * Expose RPC over WebSocket (`/ws/browser`).
  * Serialize/deserialize element handles for UI highlighting.
  * Screenshot/record video segments for audit trails.

### 5.3 Execution Engine
* **Tech**: Node.js service or serverless worker.
* **Responsibilities**:
  * Read flow JSON, perform steps sequentially/asynchronously.
  * Extract data via selectors; normalize and emit.
  * Handle pagination until termination conditions met.
  * Pluggable throttling & politeness policy.

### 5.4 LLM Agent Layer
* **Prompts & Skills**:
  * Interpret user intent to generate flow skeletons.
  * Suggest selectors by analyzing DOM diff.
  * Auto-fix flows when selectors break (self-healing).
* **APIs**: Use OpenAI or local LLM via LangChain.

### 5.5 Flow Repository
* **Storage**: Git-tracked `discoveries/` folder inside Obsidian vault.
* **Structure**:
  * `discoveries/<site>/<version>/discovery.flow.json`
  * `discoveries/<site>/README.md`
  * `discoveries/templates/`
* **Versioning**: Semantic version bumps when schema/selector changes.

---

## 6. User Journey Example
1. User triggers **“New Flow”**.
2. Plugin spins up Playwright with Chromium; webview appears.
3. User navigates to *ieeexplore.ieee.org* and logs in.
4. Click **“Record Flow”**.
5. User inputs example query “… neural network compression …” ; submits.
6. Selects first article card; highlights title, authors, publication date, PDF icon.
7. Stops recording; mapping panel shows captured selectors.
8. System auto-generates JSON; user tweaks field names.
9. Press **“Validate”**; engine tests on 1 page, returns parsed sample.
10. Save flow; Git commit created.
11. Schedule periodic run daily; results appear in research inbox.

---

## 7. Implementation Roadmap
| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 0 | 1w | Requirements finalization, risk assessment |
| 1 | 2w | Obsidian plugin scaffold, Playwright controller prototype |
| 2 | 3w | DOM picker & flow recording MVP |
| 3 | 2w | Flow execution engine (headless) + basic metadata extract |
| 4 | 2w | Auth module, credential vault integration |
| 5 | 2w | AI agent flow suggestion & self-healing POC |
| 6 | 1w | Packaging, docs, template flows gallery |
| 7 | —  | Beta testing, feedback iteration |

---

## 8. Security & Privacy Considerations
* **Credential Encryption**: Store via OS keychain or Vaultwarden; never plaintext.
* **Sandboxing**: Run browser in isolated container/user profile.
* **Rate Limits**: Respect robots.txt; exponential backoff; captcha solve only if legal.
* **Data Minimization**: Persist only required metadata & PDF content.

---

## 9. Open Questions
1. Preferred credential management backend? (Keytar vs. OS keychain vs. HashiCorp Vault)
2. Licensing constraints for bundled browser binaries?
3. How to handle paywalled PDFs requiring institution proxy?
4. UI/UX for multi-step auth (2FA, reCAPTCHA)?
5. Desired level of self-healing vs. manual review when selectors break?

---

## 10. Glossary
* **Flow**: Serialized set of navigation & extraction instructions.
* **Selector**: CSS/XPath expression pointing to DOM nodes.
* **DCS**: Discovery Creation System.

---

© 2025 ResearchTools Inc.