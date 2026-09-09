from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from app import auth
from supply_chain_kpis import CATALOG, ensure, conn

router=APIRouter(prefix='/v1/supply-chain',tags=['Supply Chain KPI Ingest'])
VALID={k for _,k,_,_ in CATALOG}

def now(): return datetime.now(timezone.utc)

class ObservationIn(BaseModel):
    kpi_key:str
    value:float
    entity_id:str='enterprise'
    source_system:str=Field(min_length=2,max_length=80)
    period_start:datetime|None=None
    period_end:datetime|None=None
    measured_at:datetime|None=None

class BulkIn(BaseModel): observations:list[ObservationIn]

def _put(c,b:ObservationIn):
    if b.kpi_key not in VALID: raise HTTPException(422,f'unknown_kpi_key:{b.kpi_key}')
    ts=b.measured_at or now()
    return c.execute('''INSERT INTO nova_supply_chain_kpi_observations(kpi_key,entity_id,value,period_start,period_end,source_system,measured_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *''',(b.kpi_key,b.entity_id,b.value,b.period_start,b.period_end,b.source_system,ts)).fetchone()

@router.post('/observations',status_code=201)
def ingest(b:ObservationIn,x_ung_permissions:str|None=Header(None)):
    auth('nova.datasets.write',x_ung_permissions);ensure()
    with conn() as c:return _put(c,b)

@router.post('/observations/bulk',status_code=201)
def ingest_bulk(b:BulkIn,x_ung_permissions:str|None=Header(None)):
    auth('nova.datasets.write',x_ung_permissions);ensure()
    with conn() as c:return {'inserted':len([_put(c,x) for x in b.observations])}
