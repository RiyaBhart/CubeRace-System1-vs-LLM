"""Single-writer atomic snapshots. JSON is authoritative; CSV/report are derived."""
import csv
import io
import json
import os
from pathlib import Path
from .schemas import GameResult
from .stats import aggregate, make_report


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


class Store:
    def __init__(self, directory: Path, run_id: str, metadata: dict | None = None):
        if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id):
            raise ValueError('Unsafe run ID')
        self.directory, self.run_id = directory, run_id
        self.path = directory / f'{run_id}.json'
        self.games: list[GameResult] = []
        self.metadata = metadata or {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.metadata = data['metadata']
            self.games = [GameResult.model_validate(g) for g in data['games']]

    def snapshot(self) -> dict:
        return {'metadata': self.metadata, 'games': [g.model_dump() for g in self.games],
                'summary': aggregate(self.games)}

    def save(self, game: GameResult | None = None) -> None:
        if game and not any(g.attempt_id == game.attempt_id for g in self.games):
            self.games.append(game)
        atomic_write(self.path, json.dumps(self.snapshot(), indent=2, allow_nan=False))
        columns = [k for k in GameResult.model_fields if k not in ('records', 'config')]
        out = io.StringIO(newline='')
        writer = csv.DictWriter(out, fieldnames=columns)
        writer.writeheader()
        for g in self.games:
            row = g.model_dump(exclude={'records', 'config'})
            row['scramble'] = ' '.join(g.scramble)
            writer.writerow(row)
        atomic_write(self.directory / f'{self.run_id}.csv', out.getvalue())
        report = make_report(self.games, self.metadata)
        atomic_write(self.directory / f'{self.run_id}-report.md', report)
        atomic_write(self.directory / 'report.md', report)
