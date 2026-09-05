from fastapi.testclient import TestClient
from app import app
c=TestClient(app)
def test_health_ready_and_rbac():
 assert c.get('/health').status_code==200
 assert c.get('/ready').status_code==200
 assert c.get('/v1/datasets').status_code==403
 assert c.get('/v1/datasets',headers={'x-ung-permissions':'nova.datasets.read'}).status_code==200
