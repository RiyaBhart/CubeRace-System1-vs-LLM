"""Read-only summaries and offline comparisons. Never creates an API client."""
import argparse
import json
from collections import Counter
from pathlib import Path
from .cube_engine import invert_move
from .schemas import GameResult


def game_diagnostics(game):
    moves = [r.move for r in game.records if r.valid and r.move]
    calls = [c for r in game.records for c in r.response.calls]
    parse_failures = sum(str(c.get('error', '')).startswith('Invalid output:') for c in calls)
    visited = {game.start_state}
    revisits = 0
    for record in game.records:
        if record.valid:
            revisits += record.state_after in visited
            visited.add(record.state_after)
    return {'unique_states': len(visited), 'state_revisits': revisits,
        'loop_filter_fallbacks': sum(r.loop_filter_fallback for r in game.records),
        'move_frequency': dict(Counter(moves)),
        'immediate_undo_loops': sum(b == invert_move(a) for a, b in zip(moves, moves[1:])),
        'same_move_repeats': sum(a == b for a, b in zip(moves, moves[1:])),
        'invalid_outputs': game.invalid_count, 'parse_failures': parse_failures,
        'invalid_output_rate': game.invalid_count / len(calls) if calls else None,
        'responses': len(calls),
        'errors': dict(Counter(str(c['error']) for c in calls if c.get('error')))}


def comparison_report(games):
    from .stats import aggregate, fmt
    lines = ['| Set | Condition / action policy | Source | Agent | Solved/attempted | Solve % | Solved moves | Gap | Turn ms | Total s | Invalid |',
             '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in aggregate(games):
        lines.append(f"| {row['benchmark_set']} | {row['condition']} / {row['action_policy']} | {row['source']} | {row['name']} | "
            f"{row['solved']}/{row['attempts']} | {fmt(row['success_rate']) if row['attempts'] else 'N/A'} | "
            f"{fmt(row['avg_solved_moves'])} | {fmt(row['gap_mean'])} | {fmt(row['avg_latency_ms'])} | "
            f"{fmt(row['total_time_s'])} | {row['invalid_count']} |")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path, help='Saved run JSON files (one or several conditions)')
    parser.add_argument('--raw', action='store_true', help='Print persisted raw responses; no inference')
    parser.add_argument('--output', type=Path, help='Save comparison Markdown')
    args = parser.parse_args()
    games = [GameResult.model_validate(g) for path in args.paths
             for g in json.loads(path.read_text(encoding='utf-8'))['games']]
    report = comparison_report(games)
    print(report)
    if args.output:
        args.output.write_text(report + '\n', encoding='utf-8')
    for game in games:
        print(json.dumps({'puzzle': game.puzzle_id, 'model': game.model, 'condition': game.condition,
            'status': game.status, **game_diagnostics(game)}, indent=2))
        if args.raw:
            print(json.dumps([r.response.raw_response for r in game.records], indent=2))


if __name__ == '__main__':
    main()
