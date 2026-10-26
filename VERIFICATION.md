# Verification record

Verified on 2026-10-26 (Asia/Karachi), Windows, Python 3.13.13.

## Optimized implementation

- **102 pytest tests passed.** One upstream Starlette/AnyIO deprecation warning;
  no failures. Python compilation and JavaScript syntax checks also passed.
- Engine/search regression suite: all 18 inverse permutations, quarter/half-turn
  orders, independent standard U/R facelet vectors, commutator, seeded scrambles,
  exact depth-five count (621,649) and depth-eight exact solution.
- Cost tests: default zero retries; explicit configurable retries; no permit means
  no request; simulation cannot invoke a real adapter; immutable per-run caps;
  persistent suite counters; concurrent reservations cannot overshoot; reservations
  survive cancellation/restart; legacy recordings import once; explicit operator
  cap changes preserve counts. No automatic reset or limit increase is present.
- Request fairness: four exact assigned IDs; common instruction; identical cube,
  solved goal, complete own history, moves remaining, HTM and legal meanings.
  No scramble, inverse solution, BFS output or cross-agent decisions are sent.
- Claude contract: low effort, 512-token ceiling, strict enum schema and parameter
  support routing; mandatory thinking is never disabled. Effort/ceiling are fixed
  and fingerprinted across trials. Unsupported schema has no downgrade.
- Claude compatibility correction: removed unsupported temperature=0 after a
  user-approved run returned a parameter-routing 404. Public unbilled metadata
  listed no temperature support across 11 endpoints. Regression tests assert no
  temperature/top_p/top_k. No paid inference was initiated to test this fix.
- Accounting: raw per-request usage, input/completion/reasoning/total tokens and
  known/unknown billed cost. Reasoning is not double counted. Partial known cost
  never becomes a fabricated complete total. Model/run/suite summaries are tested.
- Offline acceptance workflow: one four-call smoke followed by a five-puzzle,
  four-model benchmark through httpx.MockTransport. No extra requests on completed
  resume/result reads. Even a solved smoke diagnostic is excluded from benchmark
  denominators. NOT_RUN slots receive no rank medals or solve-rate credit.
- Permanent 400/401/404/422 incompatibilities: four first failures then sixteen
  NOT_RUN slots across five puzzles; no repeats on later puzzles or resume.
- Passive HTTP routes: page/configuration/health/results/puzzle/billing reads and
  missing-consent requests dispatch no inference. JSON export uses saved data.

## Browser checks

- Simplified main controls, expandable settings/replay, student banner and four
  model cards verified. Each replay/game card carries its own LIVE/SIMULATED label.
- Paid-run review dialog opened and **cancelled**, without approving a paid call.
  Simulation completed successfully. An existing live recording was exported and
  replayed at 2.5×, with no inference started by those operations.
- Final UI checks used an isolated server on port 8001 with MOCK_MODELS=1,
  no API key, a separate results directory and live choice disabled. That suite's
  live-request count remained **zero** through simulation and results inspection.
- Desktop 1440×1000 and mobile 390×844 checked. A results-chart intrinsic-width
  overflow was found and fixed. Final mobile document width was 375px at 390px
  viewport; the fixed banner remained at top=0. No browser errors were reported.
- Screenshot `outputs/simplified-ui.jpg` records the labeled synthetic desktop UI.

## External verification limits

No paid inference was initiated by the agent for these optimization checks.
Existing recordings were inspected rather than rerun. The operator may independently
approve live runs in the main app; those calls are counted by the same ledger and
must not be confused with offline verification. This report claims no new live
model quality, successful four-model compatibility, measured token savings or
monetary savings for the optimized settings. The replacement key is stored only
in the ignored backend .env; its value is not included in source, logs or archives.
Model-specific verification requires the user's explicitly approved smoke run.
Optional Kociemba installation remains unverified.

A subsequent user-approved smoke response reached Claude but exhausted all 512
completion tokens on reasoning without producing a move. At the user's explicit
choice, the ceiling remains 512 and no paid retest was started. Targeted offline
adapter/runner regression tests cover clear truncation reporting and failed-smoke
status. The earlier 102-test full-suite result predates these two added cases.

## Reproduce without spending

1. Install requirements in a virtual environment; enter student identity in .env.
2. Run `python -m pytest -q` and `node --check frontend/app.js`.
3. Start `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
4. Leave Execution on Simulation; run a race and inspect Results.
5. Open saved recordings, replay or export. These operations never infer.
6. Only when deliberately approved, run the four-call smoke and then a five-puzzle
   sequential primary benchmark as documented in README. Existing request counts
   remain in force; request caps are whole calls, not dollars.


## Pure/Assisted pipeline update

See PIPELINE_REVIEW.md for the first oracle checks, saved-response audit, fixes,
API constraints, paired offline comparison, and provenance limitations. No paid
inference was run by the agent for this update. The full updated suite passed
115 tests before final configuration/documentation edits; final verification is
recorded below after those edits.

Final offline verification: 115 pytest tests passed (one upstream AnyIO deprecation warning).
Paired five-puzzle primary simulations plus offline controls completed under both conditions.
Browser verified Assisted selection, completion and seven separately labeled dashboard rows.
Live request ledger stayed at 598/604 during this verification; no budget changes were made.


## Reference reuse and independent blue interface

116 offline pytest tests passed, one upstream AnyIO deprecation warning.
Browser verified permanent identity, free-by-default controls and the new theme.
Health endpoint returned ok after restarting the local server. Persistent live
usage remains 604/604. No paid calls or budget increases were performed.
See THIRD_PARTY.md for permission confirmation and exact reused portions.
