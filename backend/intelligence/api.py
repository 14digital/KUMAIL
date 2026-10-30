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

app=FastAPI(title='My Intelligence',version='0.1.0',dependencies=[Depends(authenticate)])

class Source(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    domains:list[str]=Field(min_length=1,max_length=20)
    rss:str
    categories:list[str]=[]
    authors:list[str]=[]
    enabled:bool=True
    opinion:bool=False

class Question(BaseModel):
    question:str=Field(min_length=1,max_length=4000)
    mode:Literal['trusted','deep']='trusted'
    conversation_id:str=Field(default_factory=lambda:str(uuid.uuid4()))

class Document(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=100000)
    permission_confirmed:bool

class Preferences(BaseModel):
    interests:list[str]=Field(default_factory=list,max_length=50)
    notifications:bool=False
    research_mode:Literal['trusted','deep']='trusted'
    playback_speed:float=Field(default=1,ge=.5,le=2)

@app.get('/health')
def health():
    return {'status':'ok','time':now()}

@app.get('/api/dashboard')
def dashboard():
    return {'briefings':store.all_docs('briefings')[:12], 'opportunities':store.all_docs('opportunities')[:3],
            'answers':store.all_docs('answers')[:30], 'sources':store.all_docs('sources'),
            'preferences':store.get('preferences','user',{}), 'integrations':integration_status()}

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
    key=str(uuid.uuid4())
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
    return {domain:store.all_docs(domain) for domain in ['documents','answers','preferences','sources']}

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
    if record.get('audio_status')=='ready' and record.get('audio_file') and (store.ROOT/'audio'/record['audio_file']).is_file():
        return {'id':body.id,'status':'ready'}
    # Mark queued before making a new job visible; a fast cache hit must not be
    # overwritten back to queued after the worker has saved its ready result.
    store.put(body.domain,body.id,{**record,'audio_status':'queued','audio_reason':'Narration queued. Playback starts when you press Play.'})
    job_id=queue_audio(body.domain,body.id,record['text'])
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
