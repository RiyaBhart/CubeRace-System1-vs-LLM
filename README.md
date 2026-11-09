# Rubik’s Cube Race — AI Engineering Assignment 02

**Riya Bhart · 23K-0063**

A reproducible OpenRouter experiment that compares how quickly four assigned models choose Rubik’s Cube moves and whether those moves lead to a solve. Each model starts from the same scrambled 3×3 cube and plays one move at a time under the same limits.

**Quick links:** [Setup](#setup-and-run) · [Results at a glance](#results-at-a-glance) · [Experiment design](#experiment-design) · [Demo checklist](#demo-checklist) · [Source credit](#source-credit)

**[Video demo and explanation](https://drive.google.com/file/d/1pOuVruJdv7YTMDlz07FWIKJD98CFzg2m/view?usp=sharing)**

## Results at a glance

Two concurrent **LIVE warm-up runs** were saved for the **same puzzle**, `warmup-001` (`R D2 L'`). The exact shortest solution is **3 turns**. All eight trials reached the 30-action limit without solving the cube. These are two repeats on one scramble, not two different puzzles.

| Model | Solved / trials | Valid turns / actions | Valid-move latency, mean / median / p95 | Mean trial time | Final correct stickers, latest run | Forfeits, both runs |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Jev 1.13 | 0 / 2 | 60 / 60 | 662 / 543 / 1,368 ms | 21.50 s | 22 / 54 | 0 |
| GPT-6 Luna Decisions | 0 / 2 | 30 / 60 | 777 / 634 / 1,812 ms | 21.89 s | 20 / 54 | 30 refusals |
| Clef | 0 / 2 | 60 / 60 | 1,040 / 889 / 1,920 ms | 32.64 s | 24 / 54 | 0 |
| Claude Opus 5.5 | 0 / 2 | 4 / 60 | 8,267 / 8,331 / 9,390 ms | 296.12 s | 34 / 54 | 56 truncated |

Latency includes only responses that yielded valid moves. The valid-turn count is also the latency sample size. A refusal or truncated response consumes an action without changing the cube. Trial time includes forfeits. Solve time and optimality gap are **N/A** because there were no solves. Correct stickers show partial progress; they are not an exact distance to solved.

**Cost across both runs:** 240 requests, zero retries, **$0.978581 in reported charges**, and 30 requests without a reported cost. The known amount is a subtotal, not the final bill.

**Scope:** No eligible paired LIVE primary or extension trials were saved. The five-puzzle primary minimum has not been met. Raw run files, credentials, and the local ledger remain outside Git.

## Research question

Do fast decision models offer a better speed–quality trade-off than a frontier LLM? The benchmark measures successful move-response latency, total trial time, move count, solve rate, and distance from the exact optimum on short puzzles. It also keeps invalid responses and infrastructure errors visible so latency can be read alongside reliability.

## Setup and run

Run these commands from the repository root on Windows. Python 3.11+ is recommended. A compatible C toolchain may be needed if a Kociemba wheel is unavailable.

```powershell
cd repository-app
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-windows.txt
Copy-Item .env.example .env
.venv\Scripts\python -X utf8 -m scripts.build_bfs --report data/cache/bfs-build.json
.venv\Scripts\python -X utf8 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Before starting the server, open `repository-app/.env` and set `STUDENT_NAME=Riya Bhart` and `STUDENT_ROLL=23K-0063`. Leave the placeholder API key in place for a simulated demo. For a separately approved LIVE run, set `OPENROUTER_API_KEY` privately in that file. Restart the server after changes. If you already have a local `.env`, keep it and skip the copy command.

On macOS or Linux, use `python3 -m venv .venv`, `.venv/bin/python`, `requirements.txt`, and `cp .env.example .env`.

- [Race arena](http://127.0.0.1:8000/): Choose a puzzle, run a race, or replay a saved run.
- [Results lab](http://127.0.0.1:8000/dashboard.html): View warm-up, primary, and extension statistics separately.
- Stop the server with **Ctrl+C**.

### Spend-free verification

The race defaults to **SIMULATED**, which uses local mock agents. Loading the app, opening the dashboard, exporting, or replaying a saved run makes no paid inference requests. Select a saved run and choose **Replay saved run** to show existing moves without sending them to OpenRouter again.

From `repository-app/`, run a focused offline check:

```powershell
.venv\Scripts\python -X utf8 -m pytest backend/tests/test_engine.py backend/tests/test_prompts.py backend/tests/test_windows_port.py -q
```

The [verification notes](repository-app/COPY_NOTES.md) describe the larger offline suite and which upstream archive checks depend on files excluded from this repository.

## Experiment design

All four agents receive the same current state: a 54-character `URFDLB` facelet string, an unfolded net, up to six recent legal moves, and the action counters. The shared instructions define the same 18 Singmaster moves. A half-turn counts as one move. The agents do not receive the scramble, solver output, or each other’s moves.

| Model | OpenRouter ID | Interface |
| --- | --- | --- |
| Jev 1.13 | `typesafe/jev-1.13` | Decisions API |
| GPT-6 Luna Decisions | `openai/gpt-6-luna-decisions` | Decisions API |
| Clef | `cloudflare/clef` | Decisions API |
| Claude Opus 5.5 | `anthropic/claude-opus-5.5` | Chat Completions with strict move JSON schema |

| Puzzle suite | Designed sample | Reference |
| --- | --- | --- |
| Warm-up | 3 puzzles, 3–4 turns | Exact HTM distance |
| Primary | 10 puzzles, 4–5 turns | Exact HTM distance |
| Extension | 5 puzzles, 15–20 turns | Kociemba reference upper bound |

Breadth-first search covers **621,649 states through depth five**, including solved. It supplies the exact shortest distance for covered puzzles and is never used to select a live move. Optimality gap is action slots used minus exact shortest distance for solved trials with a known optimum. An unsolved trial has no gap. Extension references are not proof of optimality.

The supplied settings use a **30-action limit**, a **300-second trial budget**, and a **60-second request timeout**. Claude uses fixed low reasoning effort and a 512-token ceiling, with no automatic transport or malformed-response retries. LIVE runs require explicit confirmation; budget limits and known or unknown charges are recorded separately from OpenRouter’s account balance.

## What the current evidence can answer

1. **Fastest decisions:** Jev had the lowest mean and median valid-move latency across both repeats: about 662 ms and 543 ms.
2. **Highest solve rate:** All four tied at 0 out of 2. Both trials per model used the same puzzle.
3. **Shortest solutions:** No model solved. The exact optimum was three turns, so an optimality gap cannot be reported.
4. **Speed versus quality:** Jev returned valid moves fastest. Claude finished both races with 34 of 54 stickers correctly placed, but produced only 4 valid turns across 60 actions and did not solve.
5. **Deployment choice:** I would test a hybrid before adopting either approach. A fast model could propose routine moves and escalate after a refusal or repeated state. Luna refused 30 times and Claude truncated 56 responses. The hybrid remains a proposal, not a measured improvement.

Latency includes network and provider behavior. The one-scramble sample, unequal valid-response counts, and fixed 512-token ceiling limit what can be concluded. A follow-up should use distinct paired primary puzzles and report response failures alongside latency.

## Demo checklist

The recording is linked at the top of this README. To show this result locally, open the saved LIVE warm-up and use Replay, or use the original LIVE footage if available. For the assignment recording:

1. Capture the **in-progress race** with all four model cards visible.
2. Capture the **completed race** with the final outcomes on screen.
3. Open **Results lab**, then select **Warm-up** for the closing statistics screen.
4. Keep the **student name and roll number visible throughout**. Label simulated and replay footage accurately; replay does not replace a required live recording.

## Repository map

| Path | Contents |
| --- | --- |
| [`repository-app/backend/app/`](repository-app/backend/app/) | Cube engine, shared prompts, model adapters, race runner, and FastAPI |
| [`repository-app/frontend/`](repository-app/frontend/) | Race arena, cube and net views, results, and replay |
| [`repository-app/data/puzzles/`](repository-app/data/puzzles/) | Fixed warm-up, primary, and extension puzzles |
| [`repository-app/backend/tests/`](repository-app/backend/tests/) | Offline engine, prompt, adapter, workflow, and safeguard tests |
| [`repository-app/scripts/`](repository-app/scripts/) | Cache generation, verification, and benchmark tools |
| [`LEGACY_README.md`](LEGACY_README.md) | Documentation for the earlier root-level app |

## Source credit

The current app adapts [Srijaali/ai-engineering](https://github.com/Srijaali/ai-engineering/tree/8dbedf12d56c37f1ba467c626107a0e3ebc67d9f) with permission. This version includes a redesigned interface, Windows compatibility changes, and separate local run and billing records. The [upstream README](repository-app/UPSTREAM_README.md) is preserved for attribution; its results and recording belong to the upstream project. See [attribution details](repository-app/THIRD_PARTY.md) and the [current app’s operational notes](repository-app/README.md).
