"""Service-owned document stores and a single-host durable, leased message broker."""
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

ROOT = Path(os.getenv('STATE_DIR', 'state'))


def connect(domain):
    ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ROOT / f'{domain}.sqlite', timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, value TEXT NOT NULL)')
    return db


def put(domain, key, value):
    with connect(domain) as db:
        db.execute('INSERT INTO documents VALUES (?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))
    return value


def get(domain, key, default=None):
    with connect(domain) as db:
        row = db.execute('SELECT value FROM documents WHERE id=?', (key,)).fetchone()
    return json.loads(row[0]) if row else default


def all_docs(domain):
    with connect(domain) as db:
        return [json.loads(r[0]) for r in db.execute('SELECT value FROM documents ORDER BY rowid DESC')]


def delete(domain, key):
    with connect(domain) as db:
        db.execute('DELETE FROM documents WHERE id=?', (key,))


def broker():
    db = connect('broker')
    db.execute('''CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY, queue TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER DEFAULT 0,
      available REAL NOT NULL, lease REAL DEFAULT 0, error TEXT, created REAL NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS job_poll ON jobs(queue,status,available)')
    db.commit()
    return db


def enqueue(queue, event, payload, key=None):
    key = key or str(uuid.uuid4())
    with broker() as db:
        db.execute('INSERT OR IGNORE INTO jobs(id,queue,event,payload,available,created) VALUES (?,?,?,?,?,?)',
                   (key, queue, event+'.v1', json.dumps(payload), time.time(), time.time()))
    return key


def claim(queue, lease_seconds=180):
    with broker() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM jobs WHERE queue=? AND ((status='pending' AND available<=?) OR (status='running' AND lease<?)) ORDER BY created LIMIT 1", (queue,time.time(),time.time())).fetchone()
        if not row:
            return None
        db.execute("UPDATE jobs SET status='running',attempts=attempts+1,lease=? WHERE id=?", (time.time()+lease_seconds,row['id']))
        result = dict(row)
        result['attempts'] += 1
        result['payload'] = json.loads(result['payload'])
        return result


def finish(job, error=None):
    with broker() as db:
        if error:
            db.execute('UPDATE jobs SET status=?,error=?,available=?,lease=0 WHERE id=? AND attempts=?',
                       ('dead' if job['attempts'] >= 4 else 'pending', str(error)[:300],time.time()+min(300,2**job['attempts']),job['id'],job['attempts']))
        else:
            db.execute("UPDATE jobs SET status='done',lease=0,error=NULL WHERE id=? AND attempts=?", (job['id'],job['attempts']))


def jobs():
    with broker() as db:
        return [dict(r) for r in db.execute('SELECT id,queue,event,status,attempts,error,created FROM jobs ORDER BY created DESC LIMIT 100')]
