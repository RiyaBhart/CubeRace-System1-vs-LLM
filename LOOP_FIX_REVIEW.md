# State-loop and paid-repeat review — 2026-10-26

## Observed saved race

Source: results/20261026T092720-1d8201c6.json, Pure, three-turn scramble,
proven exact distance 3. No new live inference was used in this investigation.

| Decision model | Applied turns | Distinct states including start | State revisits | Parse failures |
|---|---:|---:|---:|---:|
| Jev | 30 | 4 | 27 | 0 |
| Luna | 30 | 12 | 19 | 0 |
| Clef | 30 | 9 | 22 | 0 |

All recorded transitions replayed exactly, and applying the saved scramble to
solved reproduced the shared starting state. The observed failure is cycling
policies, not an identified permutation, stale-state or selected-option bug.

Claude produced one applied move and 17 explicitly truncated responses, then
received HTTP 403 with provider metadata scope=key_limit. The provider reported
approximately USD 2.02 spent against a USD 2.00 key ceiling. This differs from the
local suite cap. No key, cap, effort or token limit was changed. Do not infer a
solve-rate winner from access failures.

## Fixed

1. Shared moves_remaining incorrectly subtracted legal history length even when
   an invalid result consumed an attempt. Runner now supplies consumed attempts;
   all four adapters receive the same correct remaining allowance, legal history
   and applied-move count. Retries within one attempt do not consume extra turns.
2. Assisted previously only advised avoiding immediate inverses. Added its
   explicitly labeled visited-state filter. It removes options returning to any
   state visited by that agent. Pure continues offering all 18 turns. This is an
   ablation, not a disguised change to the main benchmark.
3. Explicit output-ceiling truncation no longer triggers configured retries or
   another turn at the unchanged state. It records the invalid attempt, usage and
   ERROR, and stops this game. This is a technical response failure, not heuristic
   termination based on lack of progress or predicted inability to solve.
4. Provider key-limit errors have a readable message instead of generic 403.
   Saved-record views prioritize a recorded key-limit error over earlier
   truncations and derive revisit counts without rewriting original results.
5. Record offered options, state-before/state-after, filtering policy and any
   all-neighbours-visited fallback. Summary/report groups distinguish both action
   policy and prompt revision, so old/new assisted results cannot be pooled.

## Fairness and edge cases

The filter uses only the agent's own visited states and legal engine moves.
No BFS, inverse-scramble plan, optimum distance, reference path or another
agent's actions enter live decisions. The same filter function is used for all
four models and offline controls. All 18 one-step facelet counts remain visible;
only current offered options appear in choice criteria and the strict chat enum.
The model chooses the action; an out-of-offer output is invalid, never repaired.

If every neighbouring state was visited, offer all 18 moves and record an explicit
fallback. No forced replacement, hidden reset, extra paid request or speculative
failure stop occurs. Legal histories are retained; filtering does not depend on
how many history entries are displayed in the prompt. Prompt revision is now
oriented-color-net-v4 and is checked on resume. Claude remains low effort / 512
tokens, retries zero, maximum attempts 30. Stopping on truncation applies to any
adapter reporting an explicit exhausted output ceiling.

## Offline evidence and limits

The oracle solved 120 three-to-five-turn scrambles optimally in Pure, and the same
120 in Assisted without revisits or filter fallbacks. Independent engine vectors
and inverse tests remain. Regressions cover all-four offered choices, rejected
out-of-offer actions without replacement, updated budgets after invalid output,
immediate inverses, repeated half-turns, four-quarter cycles, full-neighbourhood
fallback, single-call truncation, safe key-limit errors and protocol separation.

A free greedy control on the exact saved starting state produced:

| Condition | Status | Turns | Revisited states |
|---|---|---:|---:|
| pure / unrestricted | RAN_OUT_OF_MOVES | 30 | 28 |
| assisted / avoid_visited | RAN_OUT_OF_MOVES | 30 | 0 |

This is direct evidence that removing cycles does not guarantee solving. The
filter changes exploration; correct-facelet scores can have local maxima. No
claim of better live solve rate is made without a separately approved paid
comparison. The free UI simulation only verifies presentation and integration.

At the end of the existing user-started race the ledger was 714/724. Investigation
and offline verification made zero additional live calls; limits were unchanged.
The UI defaults to simulation, and no benchmark starts on refresh or restart.

Final verification: 135 tests passed (one upstream AnyIO deprecation warning).
JavaScript syntax check passed. Browser verified Assisted loop-guard controls
and a free simulation; read-only saved-run API derived the actual revisit counts.
Health/startup passed after restart. Live usage stayed at 714/724.
