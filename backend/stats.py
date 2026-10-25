"""Aggregate attempt-level success and pooled turn-level latency without survivorship bias."""
from collections import Counter, defaultdict
from statistics import mean, median
from .runner import percentile
from .schemas import GameResult
from .accounting import summarize_usage


def average(values):
    return mean(values) if values else None


def aggregate(games: list[GameResult]) -> list[dict]:
    groups = defaultdict(list)
    for game in games:
        groups[game.model].append(game)
    output = []
    for key, attempts in groups.items():
        scheduled = len(attempts)
        not_run = sum(g.status == 'NOT_RUN' for g in attempts)
        smoke_n = sum(g.diagnostic or g.status == 'SMOKE_TEST' for g in attempts)
        name, category, mock = attempts[0].model_name, attempts[0].category, attempts[0].mock
        billing = summarize_usage([c for g in attempts for r in g.records for c in r.response.calls])
        attempts = [g for g in attempts if not g.diagnostic and g.status not in ('NOT_RUN', 'SMOKE_TEST')]
        solved = [g for g in attempts if g.status == 'SOLVED']
        records = [r for g in attempts for r in g.records]
        latency = [r.latency_ms for r in records]
        calls = [c['latency_ms'] for r in records for c in r.response.calls]
        gaps = [g.optimality_gap for g in solved if g.optimality_gap is not None]
        lengths = sorted({len(g.scramble) for g in attempts})
        output.append({'model': key, 'name': name, 'category': category,
            'mock': mock, 'scheduled': scheduled, 'not_run': not_run, 'smoke_tests': smoke_n,
            'attempts': len(attempts), 'solved': len(solved),
            'unsolved': len(attempts)-len(solved), 'unavailable': sum(g.status == 'UNAVAILABLE' for g in attempts),
            'success_rate': 100*len(solved)/len(attempts) if attempts else 0,
            'avg_latency_ms': average(latency), 'median_latency_ms': percentile(latency, 50),
            'p95_latency_ms': percentile(latency, 95), 'avg_raw_call_ms': average(calls),
            'avg_latency_incl_retries_ms': average([r.latency_incl_retries_ms for r in records]),
            'total_time_s': sum(g.total_time_s for g in attempts),
            'avg_solve_time_s': average([g.total_time_s for g in solved]),
            'total_moves': sum(g.moves_used for g in attempts),
            'total_attempts_used': sum(g.attempts_used for g in attempts),
            'avg_solved_moves': average([g.moves_used for g in solved]),
            'gap_mean': average(gaps), 'gap_median': median(gaps) if gaps else None,
            'gap_distribution': dict(sorted(Counter(gaps).items())), 'gap_n': len(gaps),
            'invalid_count': sum(g.invalid_count for g in attempts),
            'retry_count': sum(g.retry_count for g in attempts),
            **billing,
            'solve_rate_by_length': {n: 100*sum(g.status == 'SOLVED' for g in attempts if len(g.scramble) == n)/sum(len(g.scramble) == n for g in attempts) for n in lengths}})
    return output


def fmt(value, suffix='') -> str:
    return f'{value:.2f}{suffix}' if value is not None else 'N/A'


def analysis_answers(rows: list[dict]) -> list[str]:
    if rows and all(r['attempts'] == 0 for r in rows):
        return ['No completed benchmark trials are available; smoke diagnostics and NOT_RUN slots do not establish a model winner.'] * 5
    measured = [r for r in rows if r['avg_latency_ms'] is not None and r['unavailable'] < r['attempts']]
    quality = [r for r in rows if r['gap_mean'] is not None]
    if not rows:
        return ['No attempts recorded; run a benchmark before drawing conclusions.']
    fastest = min(measured, key=lambda r: r['avg_latency_ms']) if measured else None
    attempted_rows = [r for r in rows if r['attempts'] > 0]
    best_rate = max(attempted_rows, key=lambda r: r['success_rate'])
    best_quality = min(quality, key=lambda r: (r['gap_mean'], r['avg_solved_moves'])) if quality else None
    prefix = 'SYNTHETIC DEMO ONLY: these behaviors were programmed and do not evaluate the named models. ' if any(r['mock'] for r in rows) else ''
    q1 = (f"{fastest['name']} had the lowest observed mean turn latency: {fmt(fastest['avg_latency_ms'], ' ms')}, median {fmt(fastest['median_latency_ms'], ' ms')}; including retries/backoff {fmt(fastest['avg_latency_incl_retries_ms'], ' ms')}." if fastest else 'No eligible model latency measurements are available.')
    tied = [r for r in attempted_rows if r['success_rate'] == best_rate['success_rate']]
    q2 = f"{' and '.join(r['name'] for r in tied)} had the highest observed solve rate, {fmt(best_rate['success_rate'], '%')}. " + '; '.join(f"{r['name']}: {r['solved']}/{r['attempts']} solved, {r['unsolved']} unsolved" for r in rows) + '.'
    if not any(r['solved'] for r in attempted_rows):
        q2 = 'No attempted model solved a puzzle; no solve-rate winner was established. ' + '; '.join(f"{r['name']}: {r['attempts']} attempted, {r['not_run']} NOT_RUN" for r in rows) + '.'
    if all(r['unavailable'] == r['attempts'] for r in attempted_rows):
        q2 = 'All attempts were UNAVAILABLE. No solve-rate winner can be inferred; the recorded zero successes reflect service/access failures, not tested solving ability.'
    q3 = (f"{best_quality['name']} had the lowest mean proven-optimum gap, {fmt(best_quality['gap_mean'])} HTM moves (median {fmt(best_quality['gap_median'])}, n={best_quality['gap_n']}). " if best_quality else 'No solved attempts with proven optima are available. ')
    solved_rows = [r for r in rows if r['avg_solved_moves'] is not None]
    if solved_rows:
        shortest = min(solved_rows, key=lambda r: r['avg_solved_moves'])
        q3 += f"Lowest solved-only mean solution length: {shortest['name']}, {fmt(shortest['avg_solved_moves'])} turns. These subsets may differ; failures are excluded from gaps."
    q4 = ('The lowest-latency model also led the observed mean optimality gap and solve rate.' if fastest and best_quality and fastest['model'] == best_quality['model'] and fastest['success_rate'] == best_rate['success_rate'] else 'The measurements do not establish that the fastest model also has the best solution quality; compare solve rate as well as solved-only gaps.')
    evidence = '; '.join(f"{r['name']}: {fmt(r['avg_latency_ms'], ' ms')}, {fmt(r['success_rate'], '%')} solved, mean gap {fmt(r['gap_mean'])}" for r in rows)
    q5 = f'Evidence: {evidence}. '
    if any(r['mock'] for r in rows) or not fastest or not best_quality or len(rows) < 4:
        q5 += 'A deployment choice is not justified by this dataset. Obtain complete live paired measurements first. '
    elif fastest['model'] == best_quality['model'] and fastest['success_rate'] == 100:
        q5 += f"For comparable short states, {fastest['name']} is a tentative candidate; validate harder states and a larger sample. "
    else:
        q5 += f"If reliability is the priority, {best_rate['name']} is the tentative observed candidate; a latency-sensitive application should explicitly price its failure rate. "
    q5 += 'A concrete hybrid could use fast proposals for routine states, track repeated states and lack of progress, and escalate after three stalled turns or calibrated low confidence to an LLM that proposes a short plan. Validate each action in the engine. This hybrid was not measured here and must be benchmarked separately.'
    return [prefix + q1, q2, q3, q4, q5]


def make_report(games: list[GameResult], metadata: dict) -> str:
    rows = aggregate(games)
    lines = ['# Rubik\'s Cube Race — measured results', '',
             '**SYNTHETIC MOCK DATA — not model performance evidence.**' if metadata.get('mock') else 'Live OpenRouter measurements.',
             '', f"Run: {metadata.get('run_id')} | Mode: {metadata.get('mode')} | Set: {metadata.get('set')}", '',
             '| Model | Solved / attempts | Mean / median / p95 turn ms | Mean solve s | Solved moves | Mean / median gap | Invalid / retries |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['name']} | {r['solved']}/{r['attempts']} | {fmt(r['avg_latency_ms'])} / {fmt(r['median_latency_ms'])} / {fmt(r['p95_latency_ms'])} | {fmt(r['avg_solve_time_s'])} | {fmt(r['avg_solved_moves'])} | {fmt(r['gap_mean'])} / {fmt(r['gap_median'])} | {r['invalid_count']} / {r['retry_count']} |")
    for n, answer in enumerate(analysis_answers(rows), 1):
        lines += ['', f'## {n}. Required analysis', '', answer]
    lines += ['', '## Definitions and distributions', '',
        'Turn latency pools every recorded turn, including failures; it sums network-call plus parsing durations before backoff. Inclusive latency includes retries, logging, format negotiation, and backoff. Raw individual call mean is also exported. Total game time includes event delivery overhead. Success rate uses all scheduled completed attempts, including unavailable/error results; inspect those counts before comparing model capability. Repeats are attempts, not independent puzzles. Gap is legal turns minus proven exact distance for solved attempts only.', '']
    for r in rows:
        lines.append(f"- {r['name']}: gap distribution {r['gap_distribution']}; solve rate by scramble length {r['solve_rate_by_length']}; unsolved {r['unsolved']}; unavailable {r['unavailable']}; tokens {r['tokens']}; reported USD cost {r['cost']}.")
    lines += ['', '## Limitations / threats to validity', '',
        'Small samples and correlated repeats do not establish statistical significance. Nondeterminism, model aliases/provider routing, API variance, network latency, rate limits, shared host load, search overhead in synthetic adapters, and sequential order effects can affect results. Sequential measurement reduces rate-limit interference but does not remove time-of-day effects. A shared HTTP connection warmup does not warm model weights or all pooled connections. Unavailable models are not capability failures; separate their counts. Solved-only gaps have survivorship bias and must be read alongside failures. Physical reachability of arbitrary external facelet strings is not checked; the app generates legal states. Extension references are not proven optimal; no exact gap is computed there. Mock experiments cannot answer comparative claims about real models. Confidence values need calibration. Unknown usage is N/A; partial usage after interrupted requests can undercount provider billing. Hybrid performance remains an untested proposal.', '']
    lines += ['', '## Fixed methodology and billing', '',
        'New optimized runs use the exact shared instruction, complete own legal move history, goal state, moves remaining, HTM and identical legal move definitions. Live agents never see a scramble or solver output. Claude uses a fixed effort and completion ceiling recorded below, strict JSON schema and no format downgrade. Default retries are zero. No performance-dependent adaptation is used. NOT_RUN and smoke diagnostics are excluded from attempted solve-rate denominators and remain explicitly scheduled. Interrupted/failed requests may still be billed.',
        '', f"Run billing: {metadata.get('billing', 'Unknown / legacy or simulated run')}",
        '', f"Suite billing snapshot: {metadata.get('suite_billing', 'Unknown / legacy or simulated run')}", '']
    if games:
        lines.append(f"Recorded settings: {games[0].config}")
    for r in rows:
        lines.append(f"- {r['name']}: scheduled {r['scheduled']}; attempted {r['attempts']}; NOT_RUN {r['not_run']}; smoke diagnostics {r['smoke_tests']}; requests {r['requests_used']}; known billed amount {r['known_cost']}; unknown-cost requests {r['unknown_cost_requests']}; total cost {r['cost']}; reasoning tokens {r['reasoning_tokens']}.")
    return '\n'.join(lines)
