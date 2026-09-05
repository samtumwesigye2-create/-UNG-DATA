from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel
from domain import register_dataset,list_datasets
from integration import dependencies
SYSTEM_ID="UNG-NOVA"; LEGACY_ID="UNG-DATA"; VERSION="0.2.0"
app=FastAPI(title=SYSTEM_ID,version=VERSION,description="UNG Data and Analytics System")
class DatasetIn(BaseModel): name:str; classification:str="internal"
def auth(p,h):
 s={x.strip() for x in (h or "").split(",") if x.strip()}
 if p not in s and "ung.admin" not in s: raise HTTPException(403,"UNG-JANUS permission required")
@app.get("/")
def root(): return {"system":SYSTEM_ID,"legacy_id":LEGACY_ID,"status":"online","version":VERSION}
@app.get("/health")
def health(): return {"status":"ok","service":SYSTEM_ID,"version":VERSION}
@app.get("/ready")
def ready(): return {"status":"ready","service":SYSTEM_ID,"dependencies":dependencies()}
@app.get("/v1/system")
def system(): return {"system_id":SYSTEM_ID,"legacy_id":LEGACY_ID,"domain":"data-analytics","dependencies":dependencies()}
@app.get("/v1/datasets")
def datasets(x_ung_permissions:str|None=Header(None)): auth("nova.datasets.read",x_ung_permissions); return list_datasets()
@app.post("/v1/datasets",status_code=201)
def add(body:DatasetIn,x_ung_permissions:str|None=Header(None)): auth("nova.datasets.write",x_ung_permissions); return register_dataset(body.name,body.classification)
