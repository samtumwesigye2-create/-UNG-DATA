from datetime import datetime, timezone
from fastapi import APIRouter, Header
from app import auth
from logistics_kpis import conn, ensure_schema

router=APIRouter(prefix='/v1/supply-chain',tags=['Supply Chain KPIs'])
def now(): return datetime.now(timezone.utc)
CATALOG=[
(1,'perfect_order_fulfillment','Perfect Order Fulfillment','percent'),(2,'otif','On-Time In-Full','percent'),(3,'order_fulfillment_cycle_time','Order Fulfillment Cycle Time','minutes'),(4,'forecast_accuracy','Forecast Accuracy','percent'),(5,'forecast_bias','Forecast Bias','percent'),(6,'supply_plan_adherence','Supply Plan Adherence','percent'),(7,'supplier_on_time_delivery','Supplier On-Time Delivery','percent'),(8,'supplier_defect_rate','Supplier Defect Rate','percent'),(9,'responsible_sourcing_coverage','Responsible Sourcing Coverage','percent'),(10,'inventory_accuracy','Inventory Accuracy','percent'),(11,'inventory_days_of_supply','Inventory Days of Supply','days'),(12,'stockout_backorder_rate','Stockout / Backorder Rate','percent'),(13,'excess_obsolete_inventory','Excess & Obsolete Inventory','value'),(14,'cash_to_cash_cycle_time','Cash-to-Cash Cycle Time','days'),(15,'total_supply_chain_cost','Total Supply Chain Cost','currency'),(16,'logistics_cost_per_order','Logistics Cost per Order','currency/order'),(17,'capacity_utilization','Capacity Utilization','percent'),(18,'time_to_recover','Time to Recover','minutes'),(19,'critical_supplier_risk_coverage','Critical Supplier Risk Coverage','percent'),(20,'end_to_end_visibility_coverage','End-to-End Visibility Coverage','percent'),(21,'transport_emissions_intensity','Transport Emissions Intensity','kg_co2e/tonne-km')]

def ensure():
 ensure_schema()
 with conn() as c:
  c.execute('''CREATE TABLE IF NOT EXISTS nova_supply_chain_kpi_observations(kpi_key TEXT NOT NULL,entity_id TEXT NOT NULL DEFAULT 'enterprise',value DOUBLE PRECISION NOT NULL,period_start TIMESTAMPTZ NULL,period_end TIMESTAMPTZ NULL,source_system TEXT NOT NULL,measured_at TIMESTAMPTZ NOT NULL,PRIMARY KEY(kpi_key,entity_id,measured_at))''')

def computed(c,key):
 if key=='perfect_order_fulfillment':
  r=c.execute("SELECT count(*) n,count(*) FILTER(WHERE lower(coalesce(outcome,''))='delivered' AND coalesce(on_time,false)=true AND exception=false) ok FROM nova_logistics_events").fetchone(); return 100*r['ok']/r['n'] if r['n'] else None
 if key=='otif':
  r=c.execute("SELECT count(*) FILTER(WHERE lower(coalesce(outcome,''))='delivered') n,count(*) FILTER(WHERE lower(coalesce(outcome,''))='delivered' AND coalesce(on_time,false)=true AND exception=false) ok FROM nova_logistics_events").fetchone(); return 100*r['ok']/r['n'] if r['n'] else None
 if key=='order_fulfillment_cycle_time':
  r=c.execute("SELECT avg(duration_minutes) v FROM nova_logistics_events WHERE lower(coalesce(outcome,''))='delivered'").fetchone(); return float(r['v']) if r['v'] is not None else None
 if key=='end_to_end_visibility_coverage':
  r=c.execute("SELECT count(distinct entity_id) total,count(distinct entity_id) FILTER(WHERE source_system IS NOT NULL AND module IS NOT NULL) covered FROM nova_logistics_events").fetchone(); return 100*r['covered']/r['total'] if r['total'] else None
 return None

@router.get('/kpis/catalog')
def catalog(x_ung_permissions:str|None=Header(None)):
 auth('nova.datasets.read',x_ung_permissions); return [{'number':n,'key':k,'name':name,'unit':unit} for n,k,name,unit in CATALOG]
@router.get('/kpis')
def all_kpis(x_ung_permissions:str|None=Header(None)):
 auth('nova.datasets.read',x_ung_permissions);ensure();out=[]
 with conn() as c:
  for n,key,name,unit in CATALOG:
   v=computed(c,key); source='computed-live'
   if v is None:
    r=c.execute('SELECT value,source_system,measured_at FROM nova_supply_chain_kpi_observations WHERE kpi_key=%s ORDER BY measured_at DESC LIMIT 1',(key,)).fetchone()
    if r:v=float(r['value']);source=r['source_system']
   out.append({'number':n,'key':key,'name':name,'value':round(v,4) if v is not None else None,'unit':unit,'status':'available' if v is not None else 'awaiting-source-data','source':source if v is not None else None})
 return {'kpis':out,'available':sum(x['value'] is not None for x in out),'total':21,'generated_at':now()}
