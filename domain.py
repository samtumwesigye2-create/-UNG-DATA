from dataclasses import dataclass, asdict
from uuid import uuid4
@dataclass
class Dataset:
    id:str; name:str; classification:str="internal"; status:str="available"
_datasets={}
def register_dataset(name:str, classification:str="internal"):
    d=Dataset(str(uuid4()),name,classification); _datasets[d.id]=d; return asdict(d)
def list_datasets(): return [asdict(x) for x in _datasets.values()]
