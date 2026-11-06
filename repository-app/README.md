# Rubik's Cube Race — repository copy

Full application source copied with user-confirmed permission from
https://github.com/Srijaali/ai-engineering at `8dbedf12d56c37f1ba467c626107a0e3ebc67d9f`.
Original documentation is preserved as UPSTREAM_README.md. Its benchmark numbers
belong to the upstream author, not this copy or this student. No upstream live
runs, videos, screenshots or billing snapshots are loaded into this dashboard.

The backend, client logic and cube renderer are copied from the source. The
user subsequently requested a distinct presentation: an independent dark theme,
new header/navigation, workspace introduction, rectangular controls and card
styling are applied in local-theme.css and the HTML shell. Source attribution
remains visible in the footer. Backend changes enable Windows file locking,
peak-memory reporting and JavaScript MIME types; no cube/agent policy is changed.
Startup no longer imports upstream diagnostic bills, and missing historical
measurements are unknown instead of invented. A prompt-only regression fixture
is retained with source attribution.

## Local run on Windows

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-windows.txt
# Copy .env.example to .env and supply your own key/identity.
.venv\Scripts\python -X utf8 -m scripts.build_bfs
.venv\Scripts\python -X utf8 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The working copy's .env contains the key supplied by the user and student
identity. It is ignored and excluded from archives; no key is sent to the
browser. No paid inference was performed for import or verification. Credentials
were configured but not validated against OpenRouter.

Earlier user preferences are preserved locally: low effort, 512 completion-token
ceiling, zero transport/malformed retries and 30 moves. The upstream source
classes retain their defaults for reproducible unit tests; production loads the
local .env. The fixed configuration gate accepts 512 or 1024 but never switches
between them automatically. Each approved run snapshots its exact settings.

## Existing billing and results

Existing local request usage is imported once from the prior app's SQLite ledger,
with missing costs still unknown. MAX_REQUESTS stays 724; no budget is reset
or increased. The original private ledger and saved results remain intact in the
parent project's results directory; their schema is different and they are not
silently relabeled as runs from this imported app.

The imported harness conservatively reserves $0.10 for an unknown-cost request.
Historical unknown-cost holds therefore may block new paid execution until costs
are explicitly reconciled from trustworthy provider evidence. Do not replace
unknown charges with zero or delete a ledger to make a run start. The current
local monetary ceiling stays $2.00, not the upstream $4.00 default. This is
separate from OpenRouter's own balance and key spending ceiling.

The UI defaults to SIMULATED. LIVE still requires explicit run confirmation.
Refresh, viewing results, replay and export do not send inference requests.
Copying the repository does not guarantee that any model solves a puzzle.

## Verification

See COPY_VERIFICATION.json and COPY_NOTES.md. The functional offline suite uses
mock HTTP and forbids external network connections. Some original submission
checks depend on the upstream author's private/archive evidence and do not
represent acceptance tests for this owner's new checkout.


## Current key and UI update

The most recently supplied key is stored only in this copy's ignored `.env`.
The server must be restarted to load a changed key; no paid validation is run
automatically. A new key does not erase existing cost holds or request usage.
