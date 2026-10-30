import json
from datetime import datetime,timezone
import httpx
import pytest
from fastapi.testclient import TestClient
from intelligence import store,pipeline,worker
from intelligence.editorial import build_briefing_presentation,prepare_presentation,speech_text,target_minutes
from intelligence.api import app

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    monkeypatch.setenv('APP_TOKEN','test-secret-'+'x'*40)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('ELEVENLABS_API_KEY',raising=False)
    monkeypatch.delenv('ELEVENLABS_VOICE_ID',raising=False)


def article(key='a'):
    return {'id':key,'title':'Fixture development '+key,'text':'Evidence from the approved publisher.','publisher':'Fixture publisher','url':'https://publisher.example/'+key}


def edition(sources):
    return json.dumps({'intro':'Here is what matters today.','stories':[{'source_ids':[s['id']],'headline':'A clear headline','summary':'One concise paragraph.','script':'A natural explanation of this development. It matters for the reasons in the evidence.'} for s in sources],'outro':'That is your update.'})


def test_spoken_script_is_separate_and_attributed_without_spoken_ids():
    sources=[article('a'),article('b')]
    result=build_briefing_presentation({'articles':sources,'text':'DO NOT READ THIS ANALYST REPORT'},lambda *a,**k:edition(sources))
    assert 'DO NOT READ' not in result['narration_script']
    assert result['stories'][0]['source_ids']==['a']
    assert len(result['narration_segments'])==4
    assert result['narration_segments'][2]['source_ids']==['b']
    assert result['estimated_duration_seconds']<result['target_duration_seconds']


def test_unsupported_citations_fall_back_without_padding():
    response=edition([article('invented')])
    result=build_briefing_presentation({'articles':[article()]},lambda *a,**k:response)
    assert 'fallback' in result['narration_method']
    assert result['stories'][0]['source_ids']==['a']
    assert result['estimated_duration_seconds']<60
    assert 'invented' not in result['narration_script']


def test_source_hashes_urls_and_report_labels_are_not_spoken():
    raw='What happened: A development. (Source ID: '+'a'*64+')\nImportance: It matters. https://publisher.example/a'
    spoken=speech_text(raw)
    assert 'Source ID' not in spoken and 'aaaa' not in spoken
    assert 'https' not in spoken and 'Importance:' not in spoken
    assert 'A development' in spoken


def test_edition_duration_targets_are_oman_based_and_adjustable():
    assert target_minutes({'scheduled_at':'2026-10-30T03:00:00+00:00'})==9
    assert target_minutes({'scheduled_at':'2026-10-30T07:00:00+00:00'})==4
    assert target_minutes({'scheduled_at':'2026-10-30T11:00:00+00:00'})==6
    assert target_minutes({'scheduled_at':'2026-10-30T17:00:00+00:00'})==9
    store.put('preferences','user',{'briefing_minutes':{'midday':3}})
    assert target_minutes({'scheduled_at':'2026-10-30T07:00:00+00:00'})==3


def test_old_audio_is_converted_without_reading_report_or_fetching_new_news(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY','fixture')
    monkeypatch.setenv('ELEVENLABS_VOICE_ID','fixture')
    original={'id':'b','text':'Written analyst record remains','articles':[article()],'audio_status':'ready','audio_file':'old.mp3'}
    store.put('briefings','b',original)
    def no_provider(*a,**kw):raise AssertionError('An unedited report must not be sent to speech')
    monkeypatch.setattr(pipeline.httpx.Client,'post',no_provider)
    pipeline.narrate({'domain':'briefings','id':'b','text':original['text']})
    assert store.get('briefings','b')['audio_status']=='preparing_script'
    assert store.jobs()[0]['queue']=='editor'
    prepare_presentation({'domain':'briefings','id':'b'})
    result=store.get('briefings','b')
    assert result['text']==original['text'] and result['audio_file'] is None
    assert result['presentation_version']=='spoken-v1'
    assert 'Written analyst' not in result['narration_script']


def test_chapter_audio_is_cached_and_never_truncated(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY','fixture')
    monkeypatch.setenv('ELEVENLABS_VOICE_ID','fixture')
    chunks=[{'text':'Intro sentence.','title':'Intro','source_ids':[]},{'text':'A story sentence. '*900,'title':'Story','source_ids':['a'],'story_index':0}]
    store.put('briefings','b',{'id':'b','text':'DO NOT READ','narration_script':'unused aggregate','narration_segments':chunks,'presentation_version':'spoken-v1'})
    requests=[]
    def provider(*a,**kw):
        requests.append(kw['json']['text'])
        return httpx.Response(200,content=b'ID3'+kw['json']['text'].encode(),headers={'content-type':'audio/mpeg'},request=httpx.Request('POST','https://api.elevenlabs.io'))
    monkeypatch.setattr(pipeline.httpx.Client,'post',provider)
    pipeline.narrate({'domain':'briefings','id':'b','text':'DO NOT READ'})
    result=store.get('briefings','b')
    assert result['audio_status']=='ready' and len(result['audio_segments'])>2
    assert all(len(text)<=3501 for text in requests)
    replayed=' '.join((store.ROOT/'audio'/s['audio_file']).read_bytes()[3:].decode() for s in result['audio_segments'])
    assert replayed.split()==(' '.join(c['text'] for c in chunks)).split()
    assert all(s['source_ids']==['a'] for s in result['audio_segments'][1:])
    before=len(requests)
    pipeline.narrate({'domain':'briefings','id':'b','text':'DO NOT READ'})
    assert len(requests)==before


def test_interruption_question_is_bound_to_the_story_and_followup_context():
    from intelligence.research import answer
    source=article('story')
    store.put('briefings','b',{'id':'b','title':'Briefing','articles':[source]})
    client=TestClient(app,headers={'Authorization':'Bearer '+'test-secret-'+'x'*40})
    assert client.post('/api/questions',json={'question':'Who is responsible?','briefing_id':'b','article_id':'wrong'}).status_code==422
    result=client.post('/api/questions',json={'question':'Who is responsible?','briefing_id':'b','article_id':'story','conversation_id':'c'})
    assert result.status_code==202
    job=store.claim('research');answer(job['payload'])
    first=store.get('answers',job['payload']['id'])
    assert first['sources'][0]['id']=='story'
    answer({'id':'followup','question':'And before that?','mode':'trusted','conversation_id':'c'})
    followup=store.get('answers','followup')
    assert followup['briefing_id']=='b' and followup['article_id']=='story'
    assert followup['sources'][0]['id']=='story'


def test_lease_renewal_is_fenced_by_attempt():
    store.enqueue('voice','fixture',{},'lease')
    old=store.claim('voice',lease_seconds=-1)
    latest=store.claim('voice')
    assert store.renew(old) is False
    assert store.renew(latest) is True


def test_editor_to_voice_pipeline_keeps_evidence_separate(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY','fixture')
    monkeypatch.setenv('ELEVENLABS_VOICE_ID','fixture')
    sources=[article()]
    store.put('briefings','b',{'id':'b','title':'Fixture briefing','text':'WRITTEN EVIDENCE PACKET','articles':sources,'audio_status':'preparing_script'})
    monkeypatch.setattr(pipeline,'generate',lambda *a,**kw:edition(sources))
    spoken=[]
    def provider(*a,**kw):
        spoken.append(kw['json']['text'])
        return httpx.Response(200,content=b'ID3-fixture-only',headers={'content-type':'audio/mpeg'},request=httpx.Request('POST','https://api.elevenlabs.io'))
    monkeypatch.setattr(pipeline.httpx.Client,'post',provider)
    from intelligence.editorial import queue_presentation
    queue_presentation('briefings','b')
    worker.process_job(store.claim('editor'))
    assert store.get('briefings','b')['audio_status']=='queued'
    worker.process_job(store.claim('voice'))
    result=store.get('briefings','b')
    assert result['audio_status']=='ready'
    assert result['text']=='WRITTEN EVIDENCE PACKET'
    assert len(result['audio_segments'])==3
    assert all('WRITTEN EVIDENCE' not in value for value in spoken)
    assert result['audio_segments'][1]['source_ids']==['a']
    assert all(job['status']=='done' for job in store.jobs())


def test_audio_field_update_preserves_newer_editorial_fields():
    store.put('briefings','b',{'id':'b','text':'Evidence','narration_script':'A newly completed script','presentation_version':'spoken-v1'})
    store.patch('briefings','b',{'audio_status':'queued'})
    result=store.get('briefings','b')
    assert result['narration_script']=='A newly completed script'
    assert result['text']=='Evidence'


def test_question_audio_has_reserved_queues(monkeypatch):
    monkeypatch.setenv('ELEVENLABS_API_KEY','fixture')
    monkeypatch.setenv('ELEVENLABS_VOICE_ID','fixture')
    monkeypatch.setattr(pipeline,'generate',lambda *a,**kw:'A short conversational answer based on the evidence.')
    store.put('answers','q',{'id':'q','question':'What does that mean?','text':'Written response','sources':[article()],'audio_status':'not_requested'})
    # A scheduled narration may be occupied; an answer uses separate consumers.
    store.enqueue('voice','audio.generation.requested',{'domain':'briefings','id':'occupied','text':'scheduled'},'occupied')
    occupied=store.claim('voice')
    from intelligence.editorial import queue_presentation
    queue_presentation('answers','q')
    assert store.claim('editor') is None
    worker.process_job(store.claim('answer_editor'))
    assert store.claim('voice') is None
    answer_job=store.claim('answer_voice')
    assert answer_job['payload']['id']=='q'
    def provider(*a,**kw):
        return httpx.Response(200,content=b'ID3-test-only',headers={'content-type':'audio/mpeg'},request=httpx.Request('POST','https://api.elevenlabs.io'))
    monkeypatch.setattr(pipeline.httpx.Client,'post',provider)
    worker.process_job(answer_job)
    assert store.get('answers','q')['audio_status']=='ready'
    assert any(j['id']==occupied['id'] and j['status']=='running' for j in store.jobs())


def test_editor_failure_leaves_readable_evidence_and_actionable_status(monkeypatch):
    store.put('briefings','b',{'id':'b','text':'Evidence stays intact','articles':[article()]})
    def fail(payload):raise RuntimeError('Controlled editorial failure')
    monkeypatch.setitem(worker.HANDLERS,'editor',fail)
    store.enqueue('editor','presentation.requested',{'domain':'briefings','id':'b'},'failed-editor')
    for _ in range(4):
        with store.broker() as db:db.execute('UPDATE jobs SET available=0')
        worker.process_job(store.claim('editor'))
    result=store.get('briefings','b')
    assert result['text']=='Evidence stays intact' and result['audio_status']=='failed'
    assert 'retry' in result['audio_reason']
