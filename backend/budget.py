"""Crash-safe, process-safe reservation of every live inference request.

Reservations count before dispatch and survive cancellation/restart. No reset or
automatic limit increase exists. Simulated calls never enter this ledger.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .accounting import summarize_usage


class BudgetExhausted(RuntimeError):
    pass


class Ledger:
    def __init__(self, directory: Path, initial_limit: int):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'live-budget.sqlite'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS suite (id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, cap INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, model TEXT NOT NULL,
                    started TEXT NOT NULL, usage TEXT, finished INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS blocks (run_id TEXT, model TEXT, reason TEXT,
                    PRIMARY KEY(run_id,model));
                CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY);
            ''')
            db.execute('INSERT OR IGNORE INTO suite(id,cap) VALUES(1,?)', (initial_limit,))
            db.execute('BEGIN IMMEDIATE') if not db.in_transaction else None
            if not db.execute("SELECT 1 FROM migrations WHERE name='legacy-recordings'").fetchone():
                for path in sorted(directory.glob('*.json')):
                    try:
                        data = json.loads(path.read_text(encoding='utf-8'))
                        if data['metadata'].get('mock', True):
                            continue
                        for game in data['games']:
                            for record in game.get('records', []):
                                for call in record.get('response', {}).get('calls', []):
                                    raw = call.get('raw_response')
                                    usage = call.get('usage') or (raw.get('usage') if isinstance(raw, dict) else None)
                                    db.execute('INSERT INTO requests(run_id,model,started,usage,finished) VALUES(?,?,?,?,1)',
                                        (path.stem, game['model'], record.get('timestamp', 'legacy'),
                                         json.dumps(usage) if usage else None))
                    except (ValueError, KeyError, TypeError):
                        continue
                db.execute("INSERT INTO migrations VALUES('legacy-recordings')")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def approve(self, run_id: str, cap: int) -> 'LivePermit':
        if cap < 1:
            raise ValueError('Explicit positive request cap is required')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO runs(id,cap) VALUES(?,?)', (run_id, cap))
            saved = db.execute('SELECT cap FROM runs WHERE id=?', (run_id,)).fetchone()[0]
            if saved != cap:
                raise ValueError('An existing run budget cannot be changed or increased')
        return LivePermit(self, run_id)

    def set_suite_cap(self, cap: int, *, confirmed: bool = False):
        """Only an explicit operator CLI action can change this stored ceiling."""
        if not confirmed or cap < 0:
            raise PermissionError('Explicit operator confirmation is required')
        with self.connect() as db:
            db.execute('UPDATE suite SET cap=? WHERE id=1', (cap,))

    def reserve(self, run_id: str, model: str) -> int:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT cap FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None:
                raise PermissionError('Run has no approved live budget')
            total = db.execute('SELECT count(*) FROM requests').fetchone()[0]
            used = db.execute('SELECT count(*) FROM requests WHERE run_id=?', (run_id,)).fetchone()[0]
            cap = db.execute('SELECT cap FROM suite WHERE id=1').fetchone()[0]
            if total >= cap or used >= row[0]:
                raise BudgetExhausted('Persistent suite or approved run request cap exhausted')
            cursor = db.execute('INSERT INTO requests(run_id,model,started) VALUES(?,?,?)',
                                (run_id, model, datetime.now(timezone.utc).isoformat()))
            return cursor.lastrowid

    def finish(self, request_id: int, usage: dict | None):
        with self.connect() as db:
            db.execute('UPDATE requests SET usage=?,finished=1 WHERE id=?',
                       (json.dumps(usage) if usage is not None else None, request_id))

    def block(self, run_id: str, model: str, reason: str):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO blocks VALUES(?,?,?)', (run_id, model, reason))

    def blocked(self, run_id: str, model: str) -> str | None:
        with self.connect() as db:
            row = db.execute('SELECT reason FROM blocks WHERE run_id=? AND model=?', (run_id, model)).fetchone()
            return row[0] if row else None

    def summary(self, run_id: str | None = None) -> dict:
        with self.connect() as db:
            if run_id:
                records = db.execute('SELECT model,usage FROM requests WHERE run_id=?', (run_id,)).fetchall()
                cap_row = db.execute('SELECT cap FROM runs WHERE id=?', (run_id,)).fetchone()
                cap = cap_row[0] if cap_row else None
            else:
                records = db.execute('SELECT model,usage FROM requests').fetchall()
                cap = db.execute('SELECT cap FROM suite WHERE id=1').fetchone()[0]
        calls = [{'model': model, 'usage': json.loads(usage) if usage else None} for model, usage in records]
        return {**summarize_usage(calls), 'request_limit': cap,
                'by_model': {model: summarize_usage([c for c in calls if c['model'] == model])
                             for model in sorted({c['model'] for c in calls})}}


class LivePermit:
    def __init__(self, ledger: Ledger, run_id: str):
        self.ledger, self.run_id = ledger, run_id

    def reserve(self, model: str) -> int:
        return self.ledger.reserve(self.run_id, model)


if __name__ == '__main__':
    import argparse
    from .config import settings
    parser = argparse.ArgumentParser(description='Inspect or explicitly change the persistent suite ceiling; request counts never reset.')
    parser.add_argument('--set-suite-cap', type=int)
    parser.add_argument('--confirm-budget-change', action='store_true')
    args = parser.parse_args()
    ledger = Ledger(settings.results_dir, settings.live_request_limit)
    if args.set_suite_cap is not None:
        if not args.confirm_budget_change:
            parser.error('Changing the stored ceiling requires --confirm-budget-change')
        ledger.set_suite_cap(args.set_suite_cap, confirmed=True)
    print(json.dumps(ledger.summary(), indent=2))
