import httpx
import pytest
from intelligence import pipeline,store,worker
from intelligence.narration import NarrationError,provider_error,recover_unavailable_audio
from intelligence.api import app
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    monkeypatch.setenv('APP_TOKEN','test-secret-'+'x'*40)
    monkeypatch.delenv('ELEVENLABS_API_KEY',raising=False)
    monkeypatch.delenv('ELEVENLABS_VOICE_ID',raising=False)

@pytest.fixture
def client():
    return TestClient(app,headers={'Authorization':'Bearer '+'test-secret-'+'x'*40})

def configured(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY','not-a-real-provider-key')
    monkeypatch.setenv('ELEVENLABS_VOICE_ID','test-voice')

def record(status='unavailable'):
    return store.put('briefings','b',{'id':'b','text':'Written briefing','articles':[{'id':'a'}],'audio_status':status})

def test_retry_reports_unloaded_credentials_without_echoing_them(client):
    record()
    response=client.post('/api/narration',json={'domain':'briefings','id':'b'})
    assert response.status_code==503
    assert 'not loaded' in response.json()['detail']
    assert not store.jobs()

def test_retry_is_authenticated_scoped_and_single_flight(client,monkeypatch):
    configured(monkeypatch);record()
    assert TestClient(app).post('/api/narration',json={'domain':'briefings','id':'b'}).status_code==401
    assert client.post('/api/narration',json={'domain':'sources','id':'b'}).status_code==422
    first=client.post('/api/narration',json={'domain':'briefings','id':'b'})
    second=client.post('/api/narration',json={'domain':'briefings','id':'b'})
    assert first.status_code==second.status_code==202
    assert first.json()['job_id']==second.json()['job_id']
    assert len(store.jobs())==1
    assert store.get('briefings','b')['text']=='Written briefing'

def test_restart_recovers_latest_unavailable_content_only(monkeypatch):
    record()
    assert recover_unavailable_audio()==[]
    configured(monkeypatch)
    store.put('briefings','empty',{'id':'empty','text':'No new articles','articles':[],'audio_status':'unavailable'})
    assert len(recover_unavailable_audio())==1
    assert store.get('briefings','b')['audio_status']=='queued'
    assert recover_unavailable_audio()==[]
    assert len(store.jobs())==1

def test_invalid_key_stops_retries_and_preserves_written_text(client,monkeypatch):
    configured(monkeypatch);record()
    def rejected(*args,**kwargs):
        return httpx.Response(401,json={'detail':{'status':'invalid_api_key','message':'SENSITIVE PROVIDER BODY'}},request=httpx.Request('POST','https://api.elevenlabs.io/v1/text-to-speech/test'))
    monkeypatch.setattr(pipeline.httpx.Client,'post',rejected)
    # enqueue directly since the HTTP client above also underlies TestClient.
    from intelligence.narration import queue_audio
    queue_audio('briefings','b','Written briefing')
    worker.process_job(store.claim('voice'))
    result=store.get('briefings','b')
    assert result['text']=='Written briefing'
    assert result['audio_status']=='failed'
    assert result['audio_error_code']=='invalid_api_key'
    assert 'rejected the API key' in result['audio_reason']
    assert 'SENSITIVE' not in str(result)
    assert store.jobs()[0]['status']=='dead'
    assert result['audio_retry_pending'] is False

def test_quota_error_has_specific_safe_guidance():
    fault=provider_error(httpx.Response(401,json={'detail':{'status':'quota_exceeded','message':'PRIVATE'}}))
    assert fault.retryable is False and 'credits' in fault.reason
    assert 'PRIVATE' not in str(fault)

def test_transient_errors_retry_then_stop(monkeypatch):
    configured(monkeypatch);record()
    def unavailable(*args,**kwargs):
        return httpx.Response(503,json={'detail':{'message':'PRIVATE'}},request=httpx.Request('POST','https://api.elevenlabs.io/v1/text-to-speech/test'))
    monkeypatch.setattr(pipeline.httpx.Client,'post',unavailable)
    from intelligence.narration import queue_audio
    queue_audio('briefings','b','Written briefing')
    for attempt in range(1,5):
        with store.broker() as db:db.execute('UPDATE jobs SET available=0')
        worker.process_job(store.claim('voice'))
        assert store.jobs()[0]['status']==('dead' if attempt==4 else 'pending')
        assert store.get('briefings','b')['audio_retry_pending']==(attempt<4)
    assert store.get('briefings','b')['text']=='Written briefing'

def test_success_serves_authenticated_cached_audio(client,monkeypatch):
    configured(monkeypatch);record()
    calls=[]
    def success(*args,**kwargs):
        calls.append(args[0])
        return httpx.Response(200,content=b'ID3-controlled-audio-fixture',headers={'content-type':'audio/mpeg'},request=httpx.Request('POST','https://api.elevenlabs.io/v1/text-to-speech/test'))
    with monkeypatch.context() as patch:
        patch.setattr(pipeline.httpx.Client,'post',success)
        payload={'domain':'briefings','id':'b','text':'Written briefing'}
        pipeline.narrate(payload);pipeline.narrate(payload)
    result=store.get('briefings','b')
    assert result['audio_status']=='ready' and result['audio_reason'] is None
    assert len(calls)==1
    assert client.get('/api/audio/'+result['audio_file']).content==b'ID3-controlled-audio-fixture'
    assert TestClient(app).get('/api/audio/'+result['audio_file']).status_code==401
    assert client.post('/api/narration',json={'domain':'briefings','id':'b'}).json()['status']=='ready'
    assert not store.jobs()

def test_fast_cache_completion_is_not_overwritten_to_queued(client,monkeypatch):
    configured(monkeypatch);record()
    from intelligence import narration
    def immediate(domain,record_id,text):
        latest=store.get(domain,record_id)
        store.put(domain,record_id,{**latest,'audio_status':'ready','audio_file':'cached.mp3'})
        return 'immediate-cache'
    monkeypatch.setattr(narration,'queue_audio',immediate)
    assert client.post('/api/narration',json={'domain':'briefings','id':'b'}).status_code==202
    assert store.get('briefings','b')['audio_status']=='ready'


def test_unexpected_provider_error_body_is_not_echoed():
    fault=provider_error(httpx.Response(400,json={'detail':{'status':{'unexpected':'PRIVATE'}}}))
    assert fault.code=='http_400'
    assert 'PRIVATE' not in str(fault)
