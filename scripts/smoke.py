"""Exercise real HTTP APIs and asynchronous workers. Never prints the access key."""
import os
import time
import httpx
from pathlib import Path

values=dict(line.split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
headers={'Authorization':'Bearer '+values['APP_TOKEN']}
with httpx.Client(base_url='http://127.0.0.1:8000',headers=headers,timeout=10,trust_env=False) as client:
    assert client.get('/health').status_code==200
    assert httpx.get('http://127.0.0.1:8000/api/dashboard',trust_env=False).status_code==401
    doc=client.post('/api/documents',json={'title':'Smoke test authorised document','text':'The readiness marker is cedar-green.','permission_confirmed':True}).json()
    job=client.post('/api/questions',json={'question':'readiness marker','mode':'trusted'}).json()
    for _ in range(30):
        answer=client.get('/api/answers/'+job['id']).json()
        if 'text' in answer:break
        time.sleep(.3)
    assert 'cedar-green' in answer['text']
    assert answer['sources'][0]['id']==doc['id']
    assert answer['verification']=='Partially Verified'
    assert client.get('/api/operations').json()['workers']
    # Leave the user's content intact; remove only this smoke test's records.
    client.delete('/api/documents/'+doc['id'])
    client.delete('/api/answers/'+job['id'])
    assert client.get('/api/dashboard').status_code==200
with httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=30) as web:
    response=web.get('/')
    assert response.status_code==200 and 'Clarity in a' in response.text
    assert web.get('/api/dashboard',headers=headers).status_code==200
print('PASS: authentication, authorised ingestion, async research worker, source provenance, deletion, dashboard and API gateway')
