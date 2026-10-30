import json
from . import store
from .pipeline import generate, now


def answer(payload):
    if store.get('answers',payload['id']):
        return
    question=payload['question']
    history=[a for a in store.all_docs('answers') if a.get('conversation_id')==payload['conversation_id']][:6]
    words=set((question+' '+' '.join(a['question'] for a in history)).lower().split())
    briefing_id=payload.get('briefing_id') or next((a.get('briefing_id') for a in history if a.get('briefing_id')),None)
    article_id=payload.get('article_id') if payload.get('briefing_id') else payload.get('article_id') or next((a.get('article_id') for a in history if a.get('article_id')),None)
    briefing_context=store.get('briefings',briefing_id,{}) if briefing_id else {}
    contextual=briefing_context.get('articles',[])
    if article_id:
        supporting={article_id}
        for story in briefing_context.get('stories',[]):
            if article_id in story.get('source_ids',[]):supporting.update(story['source_ids'])
        contextual=[a for a in contextual if a['id'] in supporting]
    documents=store.all_docs('articles')+store.all_docs('documents')
    ranked=sorted(documents,key=lambda a:sum(w in (a.get('title','')+' '+a.get('text','')).lower() for w in words),reverse=True)
    relevant=[a for a in ranked if any(w in (a.get('title','')+' '+a.get('text','')).lower() for w in words)]
    sources=list({a['id']:a for a in contextual+relevant}.values())[:6]
    limitation='Uses stored approved evidence; retrieved timestamps are not fresh independent verification.'
    if payload['mode']=='deep':
        limitation+=' Wider-web discovery is unavailable: an authorised search provider has not been configured. No claim is labelled Confirmed.'
    text='No relevant evidence was found in your approved sources.'
    if sources:
        output=generate('Answer this question directly and concisely, normally 120 to 220 words. Use cited source IDs in this written answer. Use the current story and conversation context to resolve references. Never invent personal or project context. Do not label claims Confirmed. Question: '+question,
                        json.dumps({'history':history,'current_briefing':briefing_context.get('title'),'current_story':contextual,'sources':sources}))
        text=output or 'AI synthesis is unavailable. Relevant source excerpts:\n\n'+'\n\n'.join('['+s['id']+'] '+s.get('title','')+'\n'+s.get('text','')[:500] for s in sources)
    record={**payload,'briefing_id':briefing_id,'article_id':article_id,'text':text,'sources':sources,'ready_at':now(),'limitations':limitation,'verification':'Partially Verified' if sources else 'Unverified','audio_status':'not_requested'}
    store.put('answers',payload['id'],record)
    from .editorial import queue_presentation
    queue_presentation('answers',payload['id'])


def opportunities(payload):
    briefing=store.get('briefings',payload['briefing_id'])
    if not briefing or not briefing['articles']:
        return
    text=generate('Identify up to three software opportunity hypotheses for 14Digital in Oman, GCC, UK or US. Include title, evidence, market, customer, problem, proposed solution, relevance, hypothesis, confidence rationale, complexity, urgency and next action. Do not invent demand or financial figures.',json.dumps(briefing['articles']))
    if text:
        store.put('opportunities',payload['briefing_id'],{'id':payload['briefing_id'],'text':text,'sources':briefing['articles'],'ready_at':now(),'status':'hypotheses_requiring_review'})
