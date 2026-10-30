from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from intelligence import store, pipeline
from intelligence.api import app
from intelligence.evidence import verify_claim
from intelligence.research import answer

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    monkeypatch.setenv('APP_TOKEN','test-secret-'+'x'*40)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('ELEVENLABS_API_KEY',raising=False)

@pytest.fixture
def client():
    return TestClient(app,headers={'Authorization':'Bearer '+'test-secret-'+'x'*40})

def test_authentication():
    assert TestClient(app).get('/api/dashboard').status_code==401

def test_oman_schedule_and_redelivery():
    at=datetime(2026,10,30,7,0,tzinfo=timezone.utc)
    slots=pipeline.due_slots(at)
    assert [s.hour for s,_ in slots]==[7,11]
    assert str(slots[0][0].utcoffset())=='4:00:00'
    pipeline.schedule(at);pipeline.schedule(at)
    assert len(store.jobs())==2

def test_independent_queues():
    store.enqueue('deep','research.requested',{})
    store.enqueue('news','briefing.scheduled',{})
    assert store.claim('news')['queue']=='news'
    assert store.claim('research') is None

def test_retry_dead_letter_and_lease():
    store.enqueue('news','test',{},'one')
    first=store.claim('news',lease_seconds=-1)
    replay=store.claim('news')
    assert replay['id']==first['id']
    with store.broker() as db:
        db.execute("UPDATE jobs SET lease=0 WHERE id='one'")
    store.claim('news',lease_seconds=-1)
    replay=store.claim('news')
    assert replay['attempts']==4
    store.finish(replay,'failure')
    assert store.jobs()[0]['status']=='dead'

def test_independence_and_quotes():
    sources={str(n):{'text':'Exact evidence.','independence_group':str(n),'independence_reviewed':True,'credible':True} for n in range(3)}
    claim={'evidence':[{'source_id':s,'quote':'Exact evidence.'} for s in sources]}
    assert verify_claim(claim,sources)['status']=='Confirmed'
    sources['2']['independence_group']='1'
    assert verify_claim(claim,sources)['status']=='Partially Verified'
    sources['0']['text']='Different text'
    with pytest.raises(ValueError):verify_claim(claim,sources)

def test_no_confirmation_without_review():
    sources={str(n):{'text':'Evidence','independence_group':str(n),'credible':True} for n in range(3)}
    assert verify_claim({'evidence':[{'source_id':s,'quote':'Evidence'} for s in sources]},sources)['status']=='Partially Verified'

def test_publisher_failure_text_publication_and_dedup(monkeypatch):
    store.put('sources','bad',{'id':'bad','rss':'https://bad.example/rss'})
    store.put('sources','good',{'id':'good','rss':'https://good.example/rss'})
    article={'id':'a','title':'News','text':'A publisher excerpt','published_at':'2026-10-30','url':'https://example.com/a'}
    def ingest(s):
        if s['id']=='bad':raise RuntimeError('offline')
        return [article]
    monkeypatch.setattr(pipeline,'ingest',ingest)
    first=pipeline.briefing({'id':'first'})
    assert len(first['articles'])==1 and len(first['source_errors'])==1
    assert 'relevance and freshness' in first['ranking']
    assert pipeline.briefing({'id':'first'})==first
    second=pipeline.briefing({'id':'second'})
    assert second['articles']==[]
    pipeline.narrate({'domain':'briefings','id':'first','text':first['text']})
    assert store.get('briefings','first')['text']==first['text']
    assert store.get('briefings','first')['audio_status']=='unavailable'

def test_voice_failure_preserves_text(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY','test')
    monkeypatch.setenv('ELEVENLABS_VOICE_ID','test')
    def fail(*a,**kw):raise RuntimeError('provider unavailable')
    monkeypatch.setattr(pipeline.httpx.Client,'post',fail)
    store.put('briefings','a',{'text':'written','presentation_version':'spoken-v1','narration_script':'Spoken fixture'})
    with pytest.raises(RuntimeError):pipeline.narrate({'domain':'briefings','id':'a','text':'written'})
    assert store.get('briefings','a')['text']=='written'
    assert store.get('briefings','a')['audio_status']=='failed'

def test_research_context_and_cache_provenance(client):
    doc=client.post('/api/documents',json={'title':'HR project','text':'Oman HR software supports payroll.','permission_confirmed':True}).json()
    answer({'id':'q1','question':'Oman HR','mode':'trusted','conversation_id':'c'})
    result=store.get('answers','q1')
    assert result['sources'][0]['id']==doc['id']
    assert 'not fresh' in result['limitations']
    assert result['verification']!='Confirmed'
    assert client.get('/api/export').status_code==200
    assert client.delete('/api/documents/'+doc['id']).status_code==200

def test_integrations_never_claim_connected(client):
    integrations=client.get('/api/integrations').json()
    assert integrations['elevenlabs']=='not_configured'
    assert integrations['youtube']=='not_connected'
    assert client.get('/api/dashboard').status_code==200

def test_unapproved_source_and_private_destination_rejected(client):
    assert client.post('/api/sources',json={'name':'Bad','rss':'https://127.0.0.1/rss','domains':['127.0.0.1']}).status_code==422
    assert client.post('/api/sources',json={'name':'Bad','rss':'https://evil.example/rss','domains':['approved.example']}).status_code==422

def test_documents_require_permission(client):
    assert client.post('/api/documents',json={'title':'Private','text':'text','permission_confirmed':False}).status_code==422

def test_openai_failure_degrades_to_excerpts(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test')
    import httpx
    def fail(*a,**kw):raise httpx.ConnectError('offline')
    monkeypatch.setattr(pipeline.httpx.Client,'post',fail)
    assert pipeline.generate('question','evidence') is None

def test_followup_keeps_prior_retrieval_context():
    store.put('documents','doc',{'id':'doc','title':'Payroll','text':'Payroll in Oman','retrieved_at':'2025-01-01'})
    answer({'id':'one','question':'Payroll Oman','mode':'trusted','conversation_id':'same'})
    answer({'id':'two','question':'What about that?','mode':'trusted','conversation_id':'same'})
    assert store.get('answers','two')['sources'][0]['id']=='doc'

def test_stale_consumer_cannot_finish_new_lease():
    store.enqueue('news','test',{},'lease')
    old=store.claim('news',lease_seconds=-1)
    new=store.claim('news')
    store.finish(old)
    assert store.jobs()[0]['status']=='running'
    store.finish(new)
    assert store.jobs()[0]['status']=='done'

def test_real_feed_parsing_without_unapproved_links(monkeypatch):
    from email.utils import format_datetime
    stamp=format_datetime(datetime.now(timezone.utc))
    xml=f'''<rss version="2.0"><channel><title>Test fixture, not production news</title><item><title>Fixture story</title><link>https://publisher.example/story</link><pubDate>{stamp}</pubDate><description>Supported feed excerpt.</description></item><item><title>Unapproved redirect</title><link>https://other.example/story</link><pubDate>{stamp}</pubDate></item></channel></rss>'''
    monkeypatch.setattr(pipeline,'retrieve',lambda *args:xml.encode())
    articles=pipeline.ingest({'id':'test','name':'Fixture publisher','rss':'https://publisher.example/rss','domains':['publisher.example']})
    assert len(articles)==1
    assert articles[0]['text']=='Supported feed excerpt.'
    assert articles[0]['publisher']=='Fixture publisher'
    assert store.get('articles',articles[0]['id'])['retrieved_at']

def test_atom_iso_dates_are_eligible(monkeypatch):
    stamp=datetime.now(timezone.utc).isoformat()
    xml=f'''<feed xmlns="http://www.w3.org/2005/Atom"><title>Fixture Atom</title><entry><id>urn:fixture:1</id><title>Atom story</title><link href="https://publisher.example/story"/><updated>{stamp}</updated><summary>Current Atom evidence.</summary></entry></feed>'''
    monkeypatch.setattr(pipeline,'retrieve',lambda *args:xml.encode())
    articles=pipeline.ingest({'id':'test','name':'Fixture publisher','rss':'https://publisher.example/rss','domains':['publisher.example']})
    assert len(articles)==1
    assert articles[0]['text']=='Current Atom evidence.'
