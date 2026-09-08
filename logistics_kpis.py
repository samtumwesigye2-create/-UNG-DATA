from datetime import datetime, timezone
from uuid import uuid4
import os, psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app import auth

router = APIRouter(prefix="/v1/logistics", tags=["Logistics Analytics"])
DB = os.getenv("DATABASE_URL", "")

def conn():
    if not DB:
        raise HTTPException(503, "database_not_configured")
    return psycopg.connect(DB, row_factory=dict_row)

def now():
    return datetime.now(timezone.utc)

def ensure_schema():
    with conn() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS nova_logistics_events(
            id UUID PRIMARY KEY,
            source_system TEXT NOT NULL,
            module TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL,
            duration_minutes DOUBLE PRECISION,
            on_time BOOLEAN,
            exception BOOLEAN NOT NULL DEFAULT FALSE,
            outcome TEXT,
            created_at TIMESTAMPTZ NOT NULL
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_nova_logistics_events_module_time ON nova_logistics_events(module,occurred_at DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_nova_logistics_events_entity ON nova_logistics_events(entity_id)')

class LogisticsEventIn(BaseModel):
    source_system: str = Field(min_length=2, max_length=80)
    module: str = Field(min_length=2, max_length=80)
    entity_id: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=2, max_length=120)
    occurred_at: datetime | None = None
    duration_minutes: float | None = Field(default=None, ge=0)
    on_time: bool | None = None
    exception: bool = False
    outcome: str | None = Field(default=None, max_length=80)

@router.post('/events', status_code=201)
def ingest_event(body: LogisticsEventIn, x_ung_permissions: str | None = Header(None)):
    auth('nova.datasets.write', x_ung_permissions)
    ensure_schema()
    ts = body.occurred_at or now()
    with conn() as c:
        return c.execute('''INSERT INTO nova_logistics_events
            (id,source_system,module,entity_id,event_type,occurred_at,duration_minutes,on_time,exception,outcome,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (str(uuid4()),body.source_system,body.module,body.entity_id,body.event_type,ts,body.duration_minutes,body.on_time,body.exception,body.outcome,now())).fetchone()

@router.get('/kpis')
def kpis(module: str | None = None, x_ung_permissions: str | None = Header(None)):
    auth('nova.datasets.read', x_ung_permissions)
    ensure_schema()
    where = 'WHERE module=%s' if module else ''
    args = (module,) if module else ()
    with conn() as c:
        total = c.execute(f'SELECT COUNT(*) n FROM nova_logistics_events {where}', args).fetchone()['n']
        exceptions = c.execute(f'SELECT COUNT(*) n FROM nova_logistics_events {where} ' + ('AND exception=TRUE' if module else 'WHERE exception=TRUE'), args).fetchone()['n']
        ontime = c.execute(f'''SELECT COUNT(*) total, COUNT(*) FILTER (WHERE on_time=TRUE) good
            FROM nova_logistics_events {where} ''' + ('AND on_time IS NOT NULL' if module else 'WHERE on_time IS NOT NULL'), args).fetchone()
        dwell = c.execute(f'SELECT AVG(duration_minutes) n FROM nova_logistics_events {where} ' + ('AND duration_minutes IS NOT NULL' if module else 'WHERE duration_minutes IS NOT NULL'), args).fetchone()['n']
        outcomes = c.execute(f'''SELECT
            COUNT(*) FILTER (WHERE lower(COALESCE(outcome,''))='delivered') delivered,
            COUNT(*) FILTER (WHERE lower(COALESCE(outcome,''))='failed') failed
            FROM nova_logistics_events {where}''', args).fetchone()
        on_time_pct = round((ontime['good'] / ontime['total']) * 100, 2) if ontime['total'] else None
        exception_rate = round((exceptions / total) * 100, 2) if total else 0.0
        return {
            'module': module or 'all',
            'events': total,
            'on_time_pct': on_time_pct,
            'exception_rate_pct': exception_rate,
            'avg_dwell_minutes': round(float(dwell), 2) if dwell is not None else None,
            'delivered': outcomes['delivered'],
            'failed': outcomes['failed'],
            'generated_at': now(),
        }

@router.get('/kpis/by-module')
def kpis_by_module(x_ung_permissions: str | None = Header(None)):
    auth('nova.datasets.read', x_ung_permissions)
    ensure_schema()
    with conn() as c:
        return c.execute('''SELECT module,
            COUNT(*) events,
            ROUND(100.0*COUNT(*) FILTER (WHERE exception=TRUE)/NULLIF(COUNT(*),0),2) exception_rate_pct,
            ROUND(AVG(duration_minutes)::numeric,2) avg_dwell_minutes,
            ROUND(100.0*COUNT(*) FILTER (WHERE on_time=TRUE)/NULLIF(COUNT(*) FILTER (WHERE on_time IS NOT NULL),0),2) on_time_pct,
            COUNT(*) FILTER (WHERE lower(COALESCE(outcome,''))='delivered') delivered,
            COUNT(*) FILTER (WHERE lower(COALESCE(outcome,''))='failed') failed
            FROM nova_logistics_events GROUP BY module ORDER BY module''').fetchall()

@router.get('/events')
def list_events(module: str | None = None, entity_id: str | None = None, x_ung_permissions: str | None = Header(None)):
    auth('nova.datasets.read', x_ung_permissions)
    ensure_schema()
    clauses=[]; args=[]
    if module: clauses.append('module=%s'); args.append(module)
    if entity_id: clauses.append('entity_id=%s'); args.append(entity_id)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with conn() as c:
        return c.execute('SELECT * FROM nova_logistics_events' + where + ' ORDER BY occurred_at DESC LIMIT 500', tuple(args)).fetchall()
