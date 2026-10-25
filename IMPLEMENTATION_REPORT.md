# OpenRouter cost-control implementation report

Scope: targeted changes to the existing local Assignment 02 implementation.
The supplied GitHub repository had no branches/commits; main was initialized
locally for the first verified source commit. Credentials, recordings, logs and
the persistent billing database are excluded from Git.

## Changes

- Claude: configurable `CLAUDE_REASONING_EFFORT=low` and
  `CLAUDE_MAX_TOKENS=512`. Mandatory adaptive reasoning remains on. Strict schema
  and parameter-support routing remain required; no alternate model or fallback
  schema. Settings are fixed for the run, fingerprinted and saved with games.
- Common payload: exact requested instruction, current state, full own legal
  history, solved goal, moves remaining, HTM and identical compact move meanings.
  Definitions occur once in each interface. No solver data, scramble, other
  agents' histories or cumulative chat transcript is supplied.
- Default retries: two → zero; configurable support remains shared. Smoke
  diagnostics force zero retries and at most one call per assigned model.
- Live requests require an explicit execution selection, paid-run consent and a
  positive hard request cap. The UI presents a final review dialog. CLI requires
  `--approve-live`; debug probing uses the same guarded path. Browsing or exporting
  results does not request inference. Simulation is the default, regardless of key.
- SQLite ledger: durable atomic reservations before dispatch, persistent suite
  and run caps, per-request raw usage, normalized token/reasoning/cost accounting,
  and model/run/suite totals. Missing cost is unknown; known subtotal is separate.
  Existing recorded live calls import once. Earlier unrecorded probes cannot be
  reconstructed. No automatic counter reset or budget increase exists. Explicit
  operator cap changes retain all counts and require a confirmation flag.
- Fail-fast permanent incompatibilities persist per model/run; later puzzle slots
  are NOT_RUN. No cube-performance heuristic ends an agent early. Scheduled,
  attempted, unsolved, unavailable, not-run and smoke counts remain distinct.
- UI: main controls reduced to test set, scramble size, execution and run/new
  scramble. Extra settings/replay are expandable. Request counts and reported
  costs remain visible. Student identity remains fixed in every screen.

## Contract verification and limits

Documentation checked on 2026-10-26 (Asia/Karachi):

- [OpenRouter reasoning contract](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
  maps unified effort to Claude; mandatory reasoning must not use none/disabled.
- [Anthropic effort](https://platform.claude.com/docs/en/build-with-claude/effort)
  documents always-on adaptive thinking for Opus 5.5 and low effort support.
- [OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)
  returns token, reasoning and cost usage in normal responses without extra calls.
  Chat explicitly includes `usage: {"include": true}` as requested. The Decisions
  contract already returns usage and does not document this request flag; no
  invented optional field is added to its alpha request.
- [Decisions schema](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)
  supports typed choice questions/criteria and usage in the response.

The exact compact empty-history Claude user message is **1,031 characters** in
this checkout, excluding system/schema. This is not a measured token count. The
user's quoted 1,157-character example belongs to a different implementation and
was not copied as a measurement here. Actual billed usage must come from responses.

The completion ceiling increased from the old implementation's 128 to 512 to
allow mandatory reasoning plus a schema answer. This is not itself a saving;
it can still truncate output. Effort, retries and payload controls reduce avoidable
spend opportunities, but neither dollar savings nor solution quality is claimed.
No paid inference was performed for this optimization verification. Live provider
support and performance of the fixed settings still require the user's explicitly
approved smoke test. Historical recordings do not validate the new methodology.

## Minimum-spend operation

A fresh suite allowance of 604 covers a four-call diagnostic plus the theoretical
600-call maximum for five puzzles × four models × 30 actions with zero retries.
On an existing installation, previously recorded calls continue to consume the
allowance. View the remaining budget and explicitly choose any operator change;
the software never enlarges the budget to make a run fit. Request caps cannot
guarantee a dollar ceiling. Use an OpenRouter key spending limit as an independent
account-side constraint if a monetary cap is needed.

After the user approves one smoke and one primary benchmark, saved replay,
statistics and export are sufficient to record the demo. Do not rerun for filming.
Use separate reports for simulated diagnostics, live smoke and live primary trials.

See VERIFICATION.md for executed checks and their scope.

## Claude routing compatibility correction

The user's subsequent explicitly approved run produced a recorded 404:
"No endpoints found that can handle the requested parameters", failing the
parameter-routing filter. An unbilled public endpoint-metadata GET confirmed
that none of the 11 returned endpoints advertised temperature support, whereas
reasoning, max_tokens and response_format were listed. The request still carried
the original implementation's temperature=0. That unsupported parameter was
removed, with a regression assertion that temperature/top_p/top_k are absent.
Effort, completion ceiling, assigned model and strict schema remain unchanged.
The fix was checked offline and against metadata, without another inference call;
live success is not asserted. Historical failed trials remain unchanged.

Source: [Anthropic Opus 5.5 migration guide](https://platform.claude.com/docs/en/models/opus-5-5/migration-guide).

## Historical model behavior (pre-optimization, not a new test)

The existing recording `20261025T211204-6daec4a2` contains 30 legal moves each
for Jev and Clef with no invalid outputs; neither solved that puzzle. Luna applied
two legal moves across 86 requests; Claude applied no move and recorded 13 invalid
outputs across 14 requests before ERROR. These observations motivated request
and retry safeguards but do not validate the new settings, establish a model
winner, or demonstrate savings. They were read from disk, with no inference.
