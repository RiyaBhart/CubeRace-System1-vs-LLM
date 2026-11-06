# Rubik’s Cube Race — AI Engineering Assignment 02

**Riya Bhart · 23K-0063**

A reproducible OpenRouter experiment that compares how quickly four assigned models choose Rubik’s Cube moves and whether those moves lead to a solve. Each model starts from the same scrambled 3×3 cube and plays one move at a time under the same limits.

**Quick links:** [Setup](#setup-and-run) · [Results at a glance](#results-at-a-glance) · [Experiment design](#experiment-design) · [Demo checklist](#demo-checklist) · [Source credit](#source-credit)

## Results at a glance

The current app has **no eligible paired LIVE primary trials** in its saved data. This table shows the available primary evidence; **N/A** means there is no eligible sample, so a solve rate or timing cannot be calculated.

| Model | Solved / eligible | Mean move latency | Mean solve time | Mean optimality gap |
| --- | ---: | ---: | ---: | ---: |
| Jev 1.13 | 0 / 0 | N/A | N/A | N/A |
| GPT-6 Luna Decisions | 0 / 0 | N/A | N/A | N/A |
| Clef | 0 / 0 | N/A | N/A | N/A |
| Claude Opus 5.5 | 0 / 0 | N/A | N/A | N/A |

The local snapshot inspected for this README also contained 52 warm-up model entries marked `NOT_RUN`. They are excluded from the eligible denominator and do not establish a 0% solve rate. No LIVE extension trials were found in the current app. Older records from the earlier app use a different schema and are kept separate. Local run files are ignored by Git; a fresh checkout does not come with those records.

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

1. **Fastest model:** No eligible paired primary timing samples are available.
2. **Highest solve rate:** No eligible paired primary trials are available for comparison.
3. **Shortest solutions:** No eligible primary solves were recorded in the current app, so every primary optimality gap is N/A.
4. **Speed versus quality:** The saved evidence cannot establish a trade-off.
5. **Deployment choice:** There is no measured winner. A future hybrid could ask a decision model for a move first and escalate to the LLM after repeated states or low confidence. That is a proposal; it has not been benchmarked.

Latency includes network and provider behavior. Even with more data, results should be read alongside sample size, route changes, invalid responses, timeouts, and the number of trials excluded by spending or infrastructure limits.

## Demo checklist

No demo video is published in this repository. For the assignment recording:

1. Capture the **in-progress race** with all four model cards visible.
2. Capture the **completed race** with the final outcomes on screen.
3. Open **Results lab** for the closing statistics screen.
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
