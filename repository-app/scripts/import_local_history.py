"""Import the owner's prior SQLite counter once; never fabricate missing costs."""
import argparse
import json
import sqlite3
from pathlib import Path
from backend.app.config import ROOT,load_settings
from backend.app.models.accounting import Ledger,units
from backend.app.models.registry import MODELS


def migrate(source: Path, destination: Path):
    with sqlite3.connect(source) as db:
        cap=db.execute('SELECT cap FROM suite WHERE id=1').fetchone()[0]
        rows=db.execute('SELECT id,run_id,model,started,usage,finished FROM requests ORDER BY id').fetchall()
    settings=load_settings(require_key=False,require_identity=False)
    if settings.max_requests!=cap:
        raise ValueError('Configured request cap differs from the existing persistent cap; refusing migration')
    model_ids=dict(zip(('jev','luna','clef','opus'),(m for m,_,_ in MODELS)))
    ledger=Ledger(destination)
    with ledger.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        for ident,run_id,model,started,encoded,finished in rows:
            usage=json.loads(encoded) if encoded else None
            amount=usage.get('cost') if isinstance(usage,dict) else None
            body=dict(status='FINISHED' if finished else 'PENDING',cost_usd=None if amount is None else str(amount),
                      timestamp_utc=started,legacy_request_id=ident,legacy_run_id=run_id,usage=usage,
                      source='user_local_request_ledger')
            db.execute('INSERT OR IGNORE INTO attempts(run_id,trial_id,model_id,suite,origin,hold,cost,body) VALUES(?,?,?,?,?,?,?,?)',
                       ('local-history',str(ident),model_ids.get(model,model),'historical','local-suite:'+str(ident),
                        units('.10'),None if amount is None else units(amount),json.dumps(body)))
    return ledger.dashboard_data()['total']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-db',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(migrate(args.source_db,ROOT/'data/results/phase3/ledger.sqlite3'),indent=2))
