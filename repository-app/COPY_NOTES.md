# Copy and local adaptation notes

Upstream source and revision: see IMPORTED_REVISION.txt and THIRD_PARTY.md.
The user confirmed source reuse permission and requested a full copy. No key
from the upstream repository was searched for, used or included. This copy
uses the key supplied directly by the user, only in ignored local configuration.

## Imported source

All backend/app source, frontend code, scripts, tests, fixed puzzle data and
stage definitions were copied. Original font and OFL license are retained.
UPSTREAM_README.md preserves the author's documentation as reference; its
measurements are explicitly not this user's experimental results. Only the
prompt-only net-n2.request.json fixture is included from their verification
data. Their live records, evidence ledger, videos and screenshots are excluded
from the local dashboard and deliverable archive.

## Changes required for this computer

- Windows byte-range file locking replaces Unix-only fcntl through a platform
  adapter. Peak working-set memory is measured with the Windows API.
- Atomic file replacement retries short-lived Windows file-sharing failures.
  These are local filesystem retries, not inference retries.
- JavaScript MIME is explicitly application/javascript. Windows registered
  .js as text/plain, causing nosniff to block the copied cube renderer.
- Startup does not load the upstream author's billing. Missing historical
  pricing samples remain unknown. Offline formula tests use temporary,
  explicitly synthetic test fixtures instead of live evidence.
- Fixed per-run settings accept the owner's retained 512-token ceiling as
  well as the upstream 1024-token fixture setting. Neither is raised or
  selected adaptively; each run snapshots its exact settings.
- Some tests required portable timer tolerances and an asynchronous mock
  response to deterministically test an already-inflight three-request wave.
  External sockets remain prohibited in automated tests; Windows' local
  socketpair is allowed for the asyncio runtime.

## Presentation

The first copy kept upstream HTML/JS and changed only color literals. The user
then requested a more distinct interface. An independent dark stylesheet now
changes typography, header, intro, navigation, control layout and card treatment.
The model IDs, cube colors and client/agent decision logic remain unchanged.
Visible source attribution is retained. The approval dialog refers to the exact
fixed settings in its quote instead of falsely claiming 1024 tokens while the
local environment is set to 512.

## Verification and budgets

495 functional offline tests passed, covering engine, exact solver, shared
prompts, adapters, runner/API, stages, request accounting and safeguards.
Three additional checks passed for locks, memory, JS MIME, secret-free
configuration and the redesigned presentation.
The submission/archive tests tied to the author's private artifacts were not
claimed as checks of this owner's results.

The prior user's ledger was imported idempotently: 718 recorded requests and a
724 cap. Unknown charges remain unknown; the copied harness assigns conservative
unknown-cost holds. Those holds can block live execution even with a newly
configured key. No paid inference was run during import, UI adaptation or key
replacement. No budget was reset or increased. The key was not validated with
an inference call. Earlier app sources/results remain preserved in the parent.
