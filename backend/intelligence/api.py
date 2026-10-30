import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from . import store
from .pipeline import now, EDITIONS
from .security import authenticate, approved_url

app=FastAPI(title='KUMAIL',version='0.1.0',dependencies=[Depends(authenticate)])

class Source(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    domains:list[str]=Field(min_length=1,max_length=20)
    rss:str
    popular_rss:str|None=None
    categories:list[str]=[]
    authors:list[str]=[]
    enabled:bool=True
    opinion:bool=False

class Question(BaseModel):
    question:str=Field(min_length=1,max_length=4000)
    mode:Literal['trusted','deep']='trusted'
    conversation_id:str=Field(default_factory=lambda:str(uuid.uuid4()))
    briefing_id:str|None=Field(default=None,max_length=200)
    article_id:str|None=Field(default=None,max_length=200)

class Document(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=100000)
    permission_confirmed:bool

class BriefingDurations(BaseModel):
    morning:int=Field(default=9,ge=2,le=15)
    midday:int=Field(default=4,ge=2,le=15)
    afternoon:int=Field(default=6,ge=2,le=15)
    evening:int=Field(default=9,ge=2,le=15)
    manual:int=Field(default=10,ge=2,le=15)

class Preferences(BaseModel):
    interests:list[str]=Field(default_factory=list,max_length=50)
    adaptive_curation:bool=True
    notifications:bool=False
    research_mode:Literal['trusted','deep']='trusted'
    playback_speed:float=Field(default=1,ge=.5,le=2)
    briefing_minutes:BriefingDurations=Field(default_factory=BriefingDurations)

@app.get('/health')
def health():
    return {'status':'ok','time':now()}

@app.get('/api/dashboard')
def dashboard():
    return {'briefings':store.all_docs('briefings')[:12], 'opportunities':store.all_docs('opportunities')[:3],
            'answers':store.all_docs('answers')[:30], 'sources':store.all_docs('sources'),
            'preferences':store.get('preferences','user',{}), 'integrations':integration_status()}

class Interaction(BaseModel):
    id:str=Field(min_length=1,max_length=150)
    briefing_id:str=Field(min_length=1,max_length=200)
    article_id:str=Field(min_length=1,max_length=200)
    action:Literal['question','replay','seek_backward','seek_forward','completed','skip']
    progress:float=Field(default=0,ge=0,le=1)

@app.post('/api/interactions',status_code=201)
def interaction(body:Interaction):
    from .feedback import record_interaction
    try:return record_interaction(body.model_dump())
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.get('/api/learning')
def learning():
    from .feedback import learning_summary
    return learning_summary()

@app.delete('/api/learning')
def reset_learning():
    with store.connect('interactions') as db:db.execute('DELETE FROM documents')
    return {'status':'inferred listening history cleared; explicit interests unchanged'}

@app.get('/api/integrations')
def integration_status():
    return {'openai': 'configured_not_verified' if os.getenv('OPENAI_API_KEY') else 'not_configured',
            'elevenlabs':'configured_not_verified' if os.getenv('ELEVENLABS_API_KEY') and os.getenv('ELEVENLABS_VOICE_ID') else 'not_configured',
            'youtube':'not_connected', 'audible':'authorised_deep_links_only','blinkist':'authorised_deep_links_only',
            'instagram':'watchlist_only_no_feed_access','deep_search':'not_configured'}

@app.post('/api/sources',status_code=201)
def add_source(source:Source):
    try:
        approved_url(source.rss,source.domains)
        if source.popular_rss:approved_url(source.popular_rss,source.domains)
    except (ValueError,OSError) as exc:
        raise HTTPException(422,'Source must use an approved public HTTPS domain') from exc
    key=hashlib.sha256(source.rss.encode()).hexdigest()
    return store.put('sources',key,{'id':key,**source.model_dump()})

@app.delete('/api/sources/{key}')
def remove_source(key:str):
    store.delete('sources',key)
    return {'deleted':key}

@app.post('/api/briefings',status_code=202)
def run_briefing():
    key='manual:'+str(uuid.uuid4())
    store.enqueue('news','briefing.scheduled',{'id':key,'title':'On-demand Intelligence','scheduled_at':now()},key)
    return {'id':key,'status':'queued'}

@app.post('/api/questions',status_code=202)
def ask(question:Question):
    if question.briefing_id:
        briefing=store.get('briefings',question.briefing_id)
        if not briefing:raise HTTPException(404,'The referenced briefing was not found')
        if question.article_id and question.article_id not in {s['id'] for s in briefing.get('articles',[])}:
            raise HTTPException(422,'This article does not belong to the referenced briefing')
    elif question.article_id:
        raise HTTPException(422,'An article context requires its briefing')
    key=str(uuid.uuid4())
    if question.briefing_id and question.article_id:
        from .feedback import record_interaction
        record_interaction({'id':'question:'+key,'briefing_id':question.briefing_id,'article_id':question.article_id,'action':'question','progress':0})
    store.enqueue('deep' if question.mode=='deep' else 'research','research.requested',{'id':key,**question.model_dump()},key)
    return {'id':key,'status':'queued','conversation_id':question.conversation_id}

@app.get('/api/answers/{key}')
def answer(key:str):
    result=store.get('answers',key)
    return result or {'id':key,'status':'pending'}

@app.put('/api/preferences')
def preferences(body:Preferences):
    return store.put('preferences','user',body.model_dump())

@app.post('/api/documents',status_code=201)
def document(body:Document):
    if not body.permission_confirmed:
        raise HTTPException(422,'Confirm permission to store and process this document')
    key=str(uuid.uuid4())
    return store.put('documents',key,{'id':key,**body.model_dump(),'retrieved_at':now(),'provenance':'User-authorised upload'})

@app.get('/api/documents')
def documents():
    return store.all_docs('documents')

@app.delete('/api/documents/{key}')
def delete_document(key:str):
    store.delete('documents',key)
    return {'deleted':key}

@app.delete('/api/answers/{key}')
def delete_answer(key:str):
    store.delete('answers',key)
    return {'deleted':key}

@app.get('/api/export')
def export():
    return {domain:store.all_docs(domain) for domain in ['documents','answers','preferences','sources','interactions']}

class NarrationRequest(BaseModel):
    domain:Literal['briefings','answers']
    id:str=Field(min_length=1,max_length=200)


@app.post('/api/narration',status_code=202)
def request_narration(body:NarrationRequest):
    from .narration import queue_audio
    record=store.get(body.domain,body.id)
    if not record:
        raise HTTPException(404,'Completed written report not found')
    if not os.getenv('ELEVENLABS_API_KEY','').strip() or not os.getenv('ELEVENLABS_VOICE_ID','').strip():
        raise HTTPException(503,'ElevenLabs key or voice ID is not loaded in the app. Save .env and run Update My Intelligence.cmd, then retry audio.')
    if not record.get('text','').strip():
        raise HTTPException(422,'There is no completed text to narrate')
    from .editorial import PRESENTATION_VERSION,queue_presentation
    if record.get('presentation_version')!=PRESENTATION_VERSION or not record.get('narration_script'):
        store.patch(body.domain,body.id,{'audio_status':'preparing_script','audio_reason':'Preparing your conversational listening edition.'})
        job_id=queue_presentation(body.domain,body.id,force=True)
        return {'id':body.id,'status':'preparing_script','job_id':job_id}
    if record.get('audio_status')=='ready' and record.get('audio_file') and (store.ROOT/'audio'/record['audio_file']).is_file():
        return {'id':body.id,'status':'ready'}
    # Mark queued before making a new job visible; a fast cache hit must not be
    # overwritten back to queued after the worker has saved its ready result.
    store.patch(body.domain,body.id,{'audio_status':'queued','audio_reason':'Narration queued. Playback starts when you press Play.'})
    job_id=queue_audio(body.domain,body.id,record['narration_script'])
    return {'id':body.id,'status':'queued','job_id':job_id}


@app.get('/api/audio/{filename}')
def audio(filename:str):
    if len(filename)!=68 or not filename.endswith('.mp3') or any(c not in '0123456789abcdef' for c in filename[:-4]):
        raise HTTPException(404)
    path=store.ROOT/'audio'/filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path,media_type='audio/mpeg',headers={'Cache-Control':'private, max-age=3600'})

@app.get('/api/operations')
def operations():
    return {'jobs':store.jobs(),'workers':store.all_docs('health'),'schedule':{'timezone':'Asia/Muscat','hours':list(EDITIONS)},
            'usage':store.all_docs('usage')[:100], 'cost_note':'Actual currency costs unavailable until provider billing rates are configured. Token and character usage are recorded.',
            'storage_bytes':sum(p.stat().st_size for p in store.ROOT.rglob('*') if p.is_file())}
