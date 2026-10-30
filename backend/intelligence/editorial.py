"""Create a listening edition independently of its written evidence packet."""
import json
import re
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ValidationError
from . import store

PRESENTATION_VERSION='spoken-v1'


class SpokenStory(BaseModel):
    source_ids:list[str]=Field(min_length=1,max_length=3)
    headline:str=Field(min_length=1,max_length=200)
    summary:str=Field(min_length=1,max_length=700)
    script:str=Field(min_length=1,max_length=5000)


class SpokenEdition(BaseModel):
    intro:str=Field(max_length=700)
    stories:list[SpokenStory]=Field(min_length=1,max_length=10)
    outro:str=Field(max_length=700)


def speech_text(text):
    # Written citation machinery must never reach a speech provider.
    text=re.sub(r'\([^)]*(?:source\s*id|https?://)[^)]*\)','',text,flags=re.I)
    text=re.sub(r'https?://\S+','',text)
    text=re.sub(r'\b[0-9a-f]{24,}\b','',text,flags=re.I)
    text=re.sub(r'\[(?:\d+|source[^\]]*)\]','',text,flags=re.I)
    text=re.sub(r'(?im)^\s*(?:what happened|importance|limitations|possible next actions|verified findings|three.source evidence|briefing|source ids?)\s*:\s*','',text)
    text=re.sub(r'(?m)^\s*(?:#{1,6}\s*|[-*]\s+|\d+\.\s+)','',text)
    text=text.replace('**','').replace('`','')
    return re.sub(r'[ \t]+',' ',text).strip()


def segment(text,title,source_ids=None,story_index=None):
    text=speech_text(text)
    return {'title':title,'text':text,'source_ids':source_ids or [],'story_index':story_index,
            'estimated_seconds':max(1,round(len(text.split())/145*60))}


def fallback_edition(sources):
    stories=[]
    for source in sources:
        title=speech_text(source.get('title','Untitled story'))
        publisher=source.get('publisher','Your approved source')
        stories.append(SpokenStory(source_ids=[source['id']],headline=title[:200],
                                   summary='Headline from '+publisher+'. Open the evidence if you need more detail.',
                                   script=publisher+' reports: '+title+'.'))
    return SpokenEdition(intro='Here is a short headline update from your approved sources. Detailed spoken analysis is unavailable right now.',
                         stories=stories,outro="That is the headline update. The source links are available whenever you need them.")


def target_minutes(record):
    from zoneinfo import ZoneInfo
    defaults={'morning':9,'midday':4,'afternoon':6,'evening':9,'manual':10}
    category='manual'
    if not record.get('id','').startswith('manual:'):
        try:
            hour=datetime.fromisoformat(record['scheduled_at']).astimezone(ZoneInfo('Asia/Muscat')).hour
            category={7:'morning',11:'midday',15:'afternoon',21:'evening'}.get(hour,'manual')
        except (KeyError,TypeError,ValueError):pass
    saved=store.get('preferences','user',{}).get('briefing_minutes',{})
    value=saved.get(category,defaults[category])
    return value if isinstance(value,int) and 2<=value<=15 else defaults[category]


def build_briefing_presentation(record,generator=None):
    if generator is None:
        from .pipeline import generate
        generator=generate
    minutes=target_minutes(record)
    sources=[s for s in record.get('articles',[]) if s.get('id') and s.get('title')][:8]
    if not sources:
        intro='There are no new qualifying stories in this edition. Your next scheduled briefing will check your approved publishers again.'
        return {'presentation_version':PRESENTATION_VERSION,'headline_summary':'No new qualifying stories.',
                'stories':[],'narration_script':intro,'narration_segments':[segment(intro,'No new headlines')],
                'estimated_duration_seconds':round(len(intro.split())/145*60),'narration_method':'empty edition','target_duration_seconds':minutes*60}
    context=[{k:s.get(k) for k in ('id','title','publisher','published_at','opinion')} | {'excerpt':s.get('text','')[:2500]} for s in sources]
    evidence_words=sum(len(s['excerpt'].split()) for s in context)
    target_words=min(minutes*145,max(100,round(evidence_words*1.5)))
    preferences=store.get('preferences','user',{})
    prompt=f'''You are KUMAIL, a personal intelligence assistant. Create an original, natural spoken news edition in clear British English for one listener. Target around {target_words} spoken words across all stories.
The target is {minutes} minutes at about 145 words per minute, only when the supplied evidence supports it. A shorter honest edition is better than repetition, invented background or filler.
Open with a brief human introduction. Cover the material developments, what they mean and uncertainty in plain conversation. Use smooth transitions. Do not announce analytical section labels, repeat headings, recite hashes, URLs or a bibliography. Attribute naturally to a publisher when useful. Do not force a commercial opportunity into unrelated stories. Only explicitly supplied interests are personal context. Distinguish reporting, opinion and hypotheses.
Return JSON only: {{"intro":"spoken introduction", "stories":[{{"source_ids":["exact supplied id"],"headline":"short headline","summary":"one short original paragraph for optional reading","script":"conversational spoken paragraphs"}}],"outro":"brief closing"}}.
Cover each supplied source story once, or combine truly overlapping stories with their exact source_ids. IDs belong only in source_ids; never in spoken fields. Never claim independent confirmation that the evidence does not establish. Do not instruct the listener to say a wake phrase.'''
    output=generator(prompt,json.dumps({'sources':context,'explicit_interests':preferences.get('interests',[])},ensure_ascii=False),max_output_tokens=6000,spoken=True)
    edition=None
    if output:
        try:
            cleaned=re.sub(r'^```(?:json)?\s*|\s*```$','',output.strip())
            edition=SpokenEdition.model_validate_json(cleaned)
            allowed={s['id'] for s in sources}
            seen=set()
            for story in edition.stories:
                if not set(story.source_ids)<=allowed or seen.intersection(story.source_ids):
                    raise ValueError('Unsupported or repeated story attribution')
                if not speech_text(story.script) or not speech_text(story.headline):raise ValueError('Empty spoken story')
                seen.update(story.source_ids)
            if seen!=allowed:
                raise ValueError('A supplied story was omitted')
            spoken_words=sum(len(speech_text(s.script).split()) for s in edition.stories)+len(speech_text(edition.intro).split())+len(speech_text(edition.outro).split())
            if spoken_words>max(180,round(target_words*1.3)+30):raise ValueError('Spoken edition exceeded its evidence and time budget')
        except (ValidationError,ValueError,TypeError):
            edition=None
    method='Original conversational briefing' if edition else 'Short headline fallback; AI narration editing unavailable'
    edition=edition or fallback_edition(sources)
    stories=[{**s.model_dump(),'script':speech_text(s.script)} for s in edition.stories]
    segments=[]
    if speech_text(edition.intro):segments.append(segment(edition.intro,'Your briefing'))
    for i,story in enumerate(stories):segments.append(segment(story['script'],story['headline'],story['source_ids'],i))
    if speech_text(edition.outro):segments.append(segment(edition.outro,'The outlook'))
    narration='\n\n'.join(s['text'] for s in segments)
    headline_summary=' '.join(s['headline'].rstrip('.')+'.' for s in stories)
    return {'presentation_version':PRESENTATION_VERSION,'headline_summary':headline_summary,'stories':stories,
            'narration_script':narration,'narration_segments':segments,'estimated_duration_seconds':sum(s['estimated_seconds'] for s in segments),
            'target_duration_seconds':minutes*60,'narration_method':method}


def build_answer_presentation(record,generator=None):
    if generator is None:
        from .pipeline import generate
        generator=generate
    sources=record.get('sources',[])
    output=generator('Answer the listener naturally in 80 to 180 spoken words. Be direct and conversational. Use only this answer and its evidence. Never read citation IDs, URLs, Markdown or analytical headings. Be candid about uncertainty. Output only the spoken answer, no JSON.',
                     json.dumps({'question':record.get('question'),'written_answer':record.get('text','')[:10000],'sources':[{'title':s.get('title'),'publisher':s.get('publisher'),'excerpt':s.get('text','')[:1500]} for s in sources]},ensure_ascii=False),max_output_tokens=500,spoken=True)
    spoken=speech_text(output or ("I've found relevant sources, but conversational synthesis is unavailable. The evidence is available if you want to inspect it." if sources else 'I do not have enough relevant evidence in your approved sources to answer that confidently.'))
    return {'presentation_version':PRESENTATION_VERSION,'narration_script':spoken,'narration_segments':[segment(spoken,'Your answer',[s['id'] for s in sources])],
            'estimated_duration_seconds':round(len(spoken.split())/145*60),'narration_method':'Conversational answer' if output else 'Evidence availability notice'}


def queue_presentation(domain,record_id,force=False):
    payload={'domain':domain,'id':record_id}
    queue='answer_editor' if domain=='answers' else 'editor'
    if force:
        return store.enqueue_record_job(queue,'presentation.requested',payload)
    return store.enqueue(queue,'presentation.requested',payload,'presentation:'+PRESENTATION_VERSION+':'+domain+':'+record_id)


def prepare_presentation(payload):
    domain=payload['domain'];record=store.get(domain,payload['id'])
    if not record: return
    if record.get('presentation_version')!=PRESENTATION_VERSION or not record.get('narration_script'):
        fields=build_briefing_presentation(record) if domain=='briefings' else build_answer_presentation(record)
        record={**record,**fields,'audio_status':'queued','audio_file':None,'audio_segments':[],
                'audio_reason':'The spoken edition is ready; ElevenLabs audio is queued.','presentation_ready_at':datetime.now(timezone.utc).isoformat()}
        store.put(domain,payload['id'],record)
    if record.get('audio_status') not in ('ready','failed'):
        store.enqueue('answer_voice' if domain=='answers' else 'voice','audio.generation.requested',{'domain':domain,'id':payload['id'],'text':record['narration_script']},
                      'voice:'+PRESENTATION_VERSION+':'+domain+':'+payload['id'])
