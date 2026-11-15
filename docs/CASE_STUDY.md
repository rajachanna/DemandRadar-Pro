# DemandRadar Pro — Engineering Case Study

**Problem.** Small automation agencies often search for opportunities manually across multiple public forums, while confusing public collaboration requests with paying contracts. Generic lead-generation bots can encourage spam and fabricated estimates.

**Approach.** An operator-controlled, read-only opportunity intake process. The system keeps original URLs, dates and source labels; ranks them with transparent keyword/evidence rules; allows human verification, then provides editable proposals and status tracking. A connected AI model is an **optional drafting improvement**, not a source of truth.

**Architecture.** FastAPI/SQLite backend, fixed API source adapters (`sources.py`), explainable scoring (`scoring.py`), idempotent repository (`storage.py`), human reviewed proposals (`drafts.py`), same-origin operator dashboard (no JS frameworks/CDNs). Source errors and zero-result scans remain visible.

**Threat modeling.** Protect private operator endpoints; never fetch arbitrary URLs; redact contact details; no automatic prospect communication; store only minimal public post text; restrict outbound provider calls to known services. API keys remain server-side. CSV is neutralized for spreadsheet formula injection. Use a reverse proxy and server-side rate limiter prior to multi-user/public operation.

**Test strategy.** Deterministic scorer fixtures for paid/unpaid indicators, Unicode, budget mentions, temporal recency; mock transport fixtures for public APIs, auth/validation and CSV; SQLite deduplication/status persistence; offline sample pipeline. CI also creates a Python wheel and verifies that dashboard HTML/CSS/JS are packaged.

**Commercial value.** Enables a repeatable opportunity-review workflow and makes demo code visible to prospective clients. It does **not** create or verify jobs, guarantee profitability, estimate real conversion rates, or send actual outreach. Results must be confirmed by an operator.

**Future production phases (not yet built).** Provider-approved additional RFP sources, robust queue and incremental scanning, configurable lead qualification policies, team permissions, managed secret storage, rate limiting, audit exports and scoped integration tests. Each connector would need its own permissions and provider validation before advertising support.
