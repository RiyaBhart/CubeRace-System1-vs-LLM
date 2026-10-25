# Pipeline review and condition implementation

## Verification performed before representation changes

The exact oracle through the existing runner solved 120 reproducible scrambles:
40 seeds each at scramble lengths 3, 4 and 5. Every solution length equaled the
BFS distance, including shorter true distances. Five initial tests passed (three
oracle corpora plus random and greedy legal-action tests). This is a finite corpus,
not an exhaustive proof over every possible seed or every depth-five state.
Independent U/R vectors, all 18 move bijections/inverses, quarter/half-turn orders,
center invariance, inverse scrambles and commutator tests also remain in the suite.

## Saved live audit (read only)

365 parseable decision records matched the API-selected move exactly; zero selected
move mismatches. The 99 other decision records were HTTP failures: three 401 and
96 502. No first-option/argmax substitution bug was found. Sanitized actual choice
fixtures from each decision model now complement synthetic contract fixtures.

Latest inspected legacy live race: `20261025T220450-0ab42055`.
Jev applied U 29 times and U' once (27 consecutive same-move repeats).
Clef applied L2 22 times, U2 seven, R2 once (17 immediate inverse pairs).
Luna applied 13 legal turns; 17 HTTP 502 failures consumed the other attempts.
Opus applied four turns, with 23 truncated parse failures among 28 calls and
reached its deadline. These are observed API/task failures, not evidence that
all 30 legal moves were executed. Invalid/API failures consume attempts under
the retained shared policy. Request caps do not expand the 30-attempt allowance.

## Bugs and presentation/reporting deficiencies fixed

1. Shared prompt hardcoded 30 remaining/maximum moves despite configurable smaller
   runner limits. Request builders now use the configured maximum for every model.
2. No explicit per-face top/right orientation in model input. Added a common color
   net, per-face orientation and fixed centers; engine permutations were unchanged.
3. History policy was fixed all-history despite a legacy N setting. New explicit
   HISTORY_LENGTH (-1/all default) controls presentation identically for all four;
   remaining moves always uses full applied history, even when display is truncated.
4. No condition/set/provenance grouping in aggregation. New records and summaries
   keep condition, test set and offline/live/simulation separate. Old records stay
   legacy. Offline controls cannot win the model-only badges or report conclusions.
5. Loop/parse diagnostics were unavailable. Every new result now carries diagnostics;
   the read-only CLI also computes them for old saved data and exposes raw responses.

No stale-state, different-scramble, selected-option, facelet-order or clockwise
engine bug was found. Added regressions explicitly test updated states/history,
all-four payload equivalence in both conditions and identical puzzle starts.
No fabricated solver-engine fix was made to explain weak live decisions.

## Conditions and safeguards

A/Pure: shared rich state, goal, 18 legal definitions, history, counts, anti-undo
instruction. B/Assisted adds only each action's one-step correct-facelet count.
No solver output reaches live agents; no loop filter removes legal moves. Richer
state consumes additional input tokens and has not been shown to improve live solves.
Oracle is an explicit offline control permitted to see the exact solution; it is
never presented as any assigned model. Oracle is NOT_RUN outside exact coverage.
Random and greedy do not inspect the scramble or exact solver.

Claude keeps strict move-only schema, low effort and 512 combined thinking/output
ceiling per the user's spending preference. No visible reasoning field was added:
it would consume more of the already restrictive completion allowance. Usage and
reasoning tokens are still logged. Automatic increases/retests remain prohibited.
A temperature of zero cannot be honored: Opus 5.5 rejects sampling parameters,
and the Decisions alpha request schema documents no temperature parameter.
Unsupported parameters are omitted rather than misrepresented as effective.

Sources checked without inference:
- https://platform.claude.com/docs/en/models/opus-5-5/migration-guide
- https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request

## Paired offline primary check (not live model evidence)

Same five seeds/puzzles, same limits, both conditions, seven agents per condition.
Named model rows below are explicitly programmed simulations. Baseline rows are
actual local policy executions. Oracle solved 5/5 in each, mean 4.4 optimal turns;
random and greedy solved 0/5 in each. This does not establish effects of Assisted
on real models; no paired live results were bought or invented.

| Set | Condition | Source | Agent | Solved/attempted | Solve % | Solved moves | Gap | Turn ms | Total s | Invalid |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| primary | pure | SIMULATED | Luna Decisions | 5/5 | 100.00 | 4.40 | 0.00 | 51.01 | 1.13 | 0 |
| primary | pure | SIMULATED | Claude Opus 5.5 | 5/5 | 100.00 | 4.40 | 0.00 | 361.43 | 7.96 | 0 |
| primary | pure | SIMULATED | Clef | 0/5 | 0.00 | N/A | N/A | 49.84 | 7.52 | 150 |
| primary | pure | SIMULATED | Jev 1.13 | 0/5 | 0.00 | N/A | N/A | 50.54 | 7.63 | 0 |
| primary | pure | OFFLINE BASELINE | Oracle (offline baseline) | 5/5 | 100.00 | 4.40 | 0.00 | 0.67 | 0.02 | 0 |
| primary | pure | OFFLINE BASELINE | Random (offline baseline) | 0/5 | 0.00 | N/A | N/A | 0.00 | 0.01 | 0 |
| primary | pure | OFFLINE BASELINE | Greedy (offline baseline) | 0/5 | 0.00 | N/A | N/A | 0.25 | 0.05 | 0 |
| primary | assisted | SIMULATED | Luna Decisions | 5/5 | 100.00 | 4.40 | 0.00 | 51.61 | 1.14 | 0 |
| primary | assisted | SIMULATED | Claude Opus 5.5 | 5/5 | 100.00 | 4.40 | 0.00 | 361.12 | 7.95 | 0 |
| primary | assisted | SIMULATED | Jev 1.13 | 0/5 | 0.00 | N/A | N/A | 50.68 | 7.65 | 0 |
| primary | assisted | SIMULATED | Clef | 0/5 | 0.00 | N/A | N/A | 49.76 | 7.51 | 150 |
| primary | assisted | OFFLINE BASELINE | Oracle (offline baseline) | 5/5 | 100.00 | 4.40 | 0.00 | 0.69 | 0.02 | 0 |
| primary | assisted | OFFLINE BASELINE | Random (offline baseline) | 0/5 | 0.00 | N/A | N/A | 0.00 | 0.02 | 0 |
| primary | assisted | OFFLINE BASELINE | Greedy (offline baseline) | 0/5 | 0.00 | N/A | N/A | 0.26 | 0.05 | 0 |


Final offline verification: 115 pytest tests passed (one upstream AnyIO deprecation warning).
Paired five-puzzle primary simulations plus offline controls completed under both conditions.
Browser verified Assisted selection, completion and seven separately labeled dashboard rows.
Live request ledger stayed at 598/604 during this verification; no budget changes were made.
