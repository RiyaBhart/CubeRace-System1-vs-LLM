# Rubik's Cube Race

Local FastAPI app for AI Engineering Assignment 02: four assigned OpenRouter
models act on identical 3×3 cubes, one legal HTM move per decision. Includes
deterministic engine, exact search, live SSE race, saved replay, statistics,
five report answers, tests, and a permanent student identity banner.

## Setup

Python 3.11+; run from this directory:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS/Linux use `source .venv/bin/activate` and `cp .env.example .env`.
Enter `STUDENT_NAME`, `ROLL_NUMBER`, and your own key in `.env`. Credentials are
backend-only and ignored by Git. If PowerShell blocks activation, invoke
`.venv\Scripts\python.exe` directly. `requirements-lock.txt` records the complete
Windows verification environment; `requirements.txt` pins portable direct dependencies.

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [the app](http://127.0.0.1:8000/). It always starts in **Simulation · free**.
The key does not opt you into inference. Benchmark settings and saved replay are
collapsed to keep the four model cards visible. The identity banner cannot be
dismissed and remains fixed on race, results and replay screens. Fill both
identity fields before recording. Responsive 2D cube nets work without a CDN;
only charts use pinned Chart.js 4.4.9. Tables and reports remain available offline.

## Minimum-spend workflow

1. Run the tests and use free simulation to check the interface.
2. Select **Smoke test · 4 calls**, choose Live, enter cap **4**, tick paid consent,
   review the four-model settings, then explicitly approve that one run. Smoke
   makes at most one request per model, with zero retries, and applies valid moves.
   It is a protocol diagnostic, not a solved-game benchmark. Inspect raw responses
   and statuses before continuing. Never present it as a solve-rate experiment.
3. Select Primary, five puzzles, one repeat, sequential mode. The recommended cap
   is **600** = 5 × 4 × 30 × (1 + 0 retries). Review the fixed Claude settings
   and explicitly approve the new run. It may use fewer requests if cubes solve,
   an API is incompatible, a deadline occurs, or the budget is exhausted.
4. Keep completed live recordings. Use Saved runs, Replay (1×/2.5×), Results and
   Export JSON for demonstrations. None of these operations invokes inference.
   Page load, refresh, GET configuration, and result reads also make zero inference
   calls. There is no automatic trial restart or failed-game rerun.

The default persistent suite ceiling is **604 requests** for a fresh installation.
Existing recorded live requests are imported once and consume that same allowance;
the application never resets or increases it. This is a **request ceiling, not a
dollar guarantee**. Actual cost and unknown cost are shown separately. For a
nonempty ledger, inspect remaining allowance before scheduling a large benchmark.

Equivalent explicit CLI operations (these commands spend credits):

```powershell
python -m backend.benchmark --set smoke --puzzles 1 --approve-live --request-cap 4
python -m backend.benchmark --set primary --puzzles 5 --repeats 1 --mode sequential --approve-live --request-cap 600
```

`--debug-probe --approve-live` is the same four-model, four-call diagnostic and
prints/persists raw responses. It cannot bypass consent, ledger accounting or
caps. Do not run it again when a saved smoke recording is sufficient. CLI calls
without `--approve-live` simulate and never infer, even with a real key configured.
`MOCK_MODELS=1` is an additional hard prohibition on live execution.

## Persistent budget and accounting

`results/live-budget.sqlite` uses atomic SQLite transactions to reserve each
request **before** network dispatch, including configured retries. Counters survive
refresh, crashes, cancellation, explicit resume and process restarts. A reserved
request may not have reached the service after a crash: counting it is deliberately
conservative. Cancelling a request does not prove it was free. Unknown costs stay
unknown. Raw usage is retained per request, plus normalized token/reasoning counts,
known billed subtotal, unknown-cost count, and complete total only if all costs
are known. Reasoning tokens are included in completion tokens and are not added
again to total usage. No extra inference or billing-query calls retrieve costs.

Chat requests ask for `usage: {"include": true}`; the Decisions API documents
usage as a response field and does not document that request flag, so it is not
sent there. The response usage is recorded on success and failure, including
invalid/truncated outputs. Billing is summarized per model, run and local suite.
Legacy completed recordings are imported once; older standalone probes or lost
in-flight requests from before ledger installation cannot be reconstructed.
Simulations never increment the live counter or produce invented dollar costs.

`LIVE_REQUEST_LIMIT` initializes the stored suite ceiling once. Changing `.env`
later does not change it. There is no reset endpoint. If an operator deliberately
needs a different ceiling, stop the server, inspect usage, then explicitly run:

```powershell
python -m backend.budget
python -m backend.budget --set-suite-cap 1000 --confirm-budget-change
```

That deliberate operator action preserves every request count; it is never run
by the app, a benchmark, export, replay or this verification. A per-run cap is
also immutable once recorded and cannot be increased by resume. Choosing a cap
does not reserve or enlarge the suite ceiling. If either cap is reached, active
attempts end BUDGET_EXHAUSTED and untouched slots are NOT_RUN.

## Fixed methodology and payload fairness

All four IDs remain solely in `backend/config.py`:

- `typesafe/jev-1.13`
- `openai/gpt-6-luna-decisions`
- `cloudflare/clef`
- `anthropic/claude-opus-5.5`

The exact common instruction is:

> Choose one move toward the goal. Facelets: row-major URFDLB, fixed centers. Singmaster turns: clockwise viewed directly at the named face. Half-turn metric (HTM): 180 degrees counts as one move. Limit: 30 moves.

Each call includes current `cube_facelets`, **complete own legal move history** in
`recent_moves`, solved `goal_facelets`, `moves_remaining` = 30 minus legal moves
already executed, `metric: HTM`, and identical meanings for all 18 legal choices.
`RECENT_MOVES_N` is retained only for legacy configuration compatibility; optimized
runs do not truncate history. No scramble, inverse solution, BFS output, other
agent history, heuristic score or accumulated chat transcript is sent.

Decisions places the instruction/criteria in the typed question and other fields
in state. Claude receives equivalent compact JSON and only this system message:
`Return one legal move as schema JSON.` The sole action shape is `{"move":"R"}`.
Strict JSON-schema output is preserved, with all legal moves in the enum and
`provider.require_parameters=true`. No alternative model, JSON-object downgrade,
output repair, or plain-text fallback is used.

`CLAUDE_REASONING_EFFORT=low` and `CLAUDE_MAX_TOKENS=512` are fixed across trials
and saved in the run fingerprint/results. Accepted efforts are low, medium, high,
xhigh and max. Mandatory adaptive reasoning is **not disabled**. The output limit
covers reasoning plus the action response; 512 is a ceiling, not consumption.
It may truncate an answer. That failure and reported usage are recorded without
automatically changing the ceiling, effort, prompt, budget or model.

This reduces avoidable overhead; **actual token savings, costs and solution quality
have not been established through paid testing of the optimized implementation**.
Character counts are not token measurements. See `IMPLEMENTATION_REPORT.md`.

Contract sources checked without inference:

- [OpenRouter reasoning controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
- [Claude Opus 5.5 model](https://openrouter.ai/anthropic/claude-opus-5.5)
- [Anthropic effort and mandatory adaptive thinking](https://platform.claude.com/docs/en/build-with-claude/effort)
- [OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)
- [Decisions request/response schema](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)

## Reliability, denominators and timing

Default `MAX_RETRIES=0`: one request per move attempt. If explicitly configured,
all four models share the same retry ceiling; invalid responses consume retries,
and network errors/429/5xx use exponential backoff. Permanent API errors such as
invalid ID, 401/403/404 or unsupported schema stop that model and persist a block
for the rest of the run, including explicit resume. Later puzzle slots are
NOT_RUN, with no repeated predictable request. This is API compatibility handling,
not a prediction that an agent will fail the cube. A new explicitly approved run
may intentionally recheck after an operator fixes the cause.

Limits remain 30 attempts and at most 30 applied legal moves, 300 seconds/game,
60 seconds/request by default. Invalid exhausted turns waste an attempt by default;
`INVALID_CONSUMES_ATTEMPT=0` preserves that optional shared policy but the hard live
request cap still applies. Solving stops immediately. UNAVAILABLE/ERROR are actual
attempted failures; NOT_RUN and smoke diagnostics are not counted as solving trials.
The summary shows scheduled, attempted, unsolved, unavailable and not-run counts
separately. Compare solved-only gaps alongside failure and missing-trial counts.

Use concurrent mode for a race, sequential for report measurements to reduce
rate-limit interference. Sequential order rotates across puzzles/repeats. Every
model has its own timer and semaphore; one pooled httpx client uses HTTP/2 and
keep-alive. An unbilled catalog GET warms the origin before timed games, only after
run approval for live execution. It cannot guarantee warm model weights or every
connection. `perf_counter` measures individual call-plus-parse time; turn raw
latency sums calls, while inclusive latency adds local accounting/logging/backoff.
Game time includes event delivery. Median/p95 interpolate recorded turn latencies.

## Engine, sets and exact search

54 facelets use Kociemba U R F D L B order, each face row-major viewed from outside;
centers stay fixed. Sticker geometry generates all 18 HTM permutations once.
Engine startup aborts if self-tests fail. Tests cover independent standard U/R
vectors, inverse/order/commutator identities, seeded scrambles and known BFS sizes.
Scrambles avoid repeated faces and reducible commuting triples. Local random
generators preserve reproducibility without changing global RNG state.

Warm-up: two 3–4-turn puzzles; primary: ten 4–5-turn puzzles by CLI default,
five by the economical UI default (minimum five); optional extension: five
15–20-turn puzzles. Fixed seeds, repeat counts and seed offsets are saved.
One-puzzle race mode uses its seed directly. Tests use exact HTM distance, never
scramble length as assumed truth. Default BFS depth five contains 621,649 states
and is cached once in a trusted local pickle; building runs off the event loop.
Bidirectional fallback proves distances up to eight moves within a node budget.
Failure to prove required primary truth stops orchestration rather than inventing it.

```powershell
python -m backend.benchmark --build-bfs 5
python -m backend.benchmark --set warmup --puzzles 2
python -m backend.benchmark --set extension --puzzles 5
```

The last two commands simulate. Optional `pip install -r requirements-optional.txt`
and `USE_KOCIEMBA=1` add an extension reference, labeled **not proven optimal**.
Extension optimality gaps remain N/A without an exact distance. Solvers assist
ground truth and explicitly synthetic demos only, never real agent decisions.
Do not load third-party pickle caches. Serialization validates colors/centers;
physical reachability of arbitrary external strings is not claimed.

## Results, resume and demo checklist

Each completed game atomically updates authoritative run JSON, derived CSV,
per-run Markdown report and latest `results/report.md`. Raw response calls/usage
also live in the durable budget ledger and rotating `calls.jsonl`; keys/headers
are never logged. Reports answer the five required questions with observed data
and include limits on small samples, correlated repeats, nondeterminism, network
variance, rate limits, provider routing and survivorship bias. No winner or hybrid
advantage is assumed. Rank is solved first, then legal turns, then time; unsolved
ties use correct facelets, then time. That display score never guides live actions.

Explicit `--resume RUN_ID` requires the same settings and, for live runs,
`--approve-live --request-cap ORIGINAL_CAP`. Completed failed or solved games are
skipped. An interrupted incomplete game is retried only by that explicit command;
its earlier reservations remain counted. Settings changes reject resume. JSON is
authoritative if a crash leaves stale CSV/report; resume regenerates derivatives.
Run one server worker/writer against a results directory. Stop with Ctrl+C for
graceful task cancellation and client cleanup. SSE reconnects missed events and
does not restart inference. After server restart, choose saved replay.

Mandatory recording stages:

1. Keep student name and roll number readable in the fixed banner **throughout**.
2. Show an in-progress concurrent race with identical starting cubes and histories.
3. Hold the completed cards with honest statuses, timings, turns and rankings.
4. Open Results for the statistical table/charts and five report answers, with
   identity still visible. Use saved live replay rather than paying to rerun for filming.

Simulated behaviors are arbitrary programmed examples, labeled SYNTHETIC. They
cannot establish the real models' performance. Recorded fixture provenance is
explicit: successful protocol samples are synthetic; the historical 401 sample
is a sanitized observed response. Do not mix diagnostic/simulated/legacy runs
with an optimized live primary experiment when making scientific claims.

## Architecture and verification

`cube_engine.py`, `scramble.py`, `optimal.py`: simulation and exact references.
`adapters/`: shared context, strict parsing and a single live network-call site.
`budget.py`, `accounting.py`: durable reservations, reported billing, explicit caps.
`runner.py`, `benchmark.py`: independent games, reproducible sets, consent, resume.
`storage.py`, `stats.py`, `schemas.py`: atomic exports, report and typed records.
`main.py`: local API, passive read routes, SSE and guarded run creation.
`frontend/`: plain HTML/CSS/JS, no build step. `backend/tests/`: offline tests.

```powershell
python -m pytest -q
node --check frontend/app.js
```

Node is optional except for the syntax check. Tests use mocked transports and
fake credentials, including the smoke→five-puzzle workflow, zero retries, caps,
restart/concurrency, consent, unknown costs, reasoning accounting, permanent
incompatibility, four-model fairness and simulation isolation. Browser checks
cancel the paid approval dialog and use only free simulation/saved replay.

Troubleshooting: 401 means invalid/disabled credentials; 402 indicates credit or
budget issues; 404 may be an invalid ID or endpoint. Inspect saved raw responses.
Never replace an assigned model silently. A schema rejection is recorded and
blocks repeated attempts in that run. If charts cannot load, use tables/report.
Delete only a corrupt BFS cache to rebuild it; **do not delete the live ledger to
get more budget**. Optional Kociemba may need compiler tools. This is a loopback
assignment application: public hosting would require authentication, quotas and
a multi-worker job store. No public deployment is included.
