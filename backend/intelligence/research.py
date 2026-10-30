import json
from . import store
from .pipeline import generate, now


def answer(payload):
    if store.get('answers',payload['id']):
        return
    question=payload['question']
    history=[a for a in store.all_docs('answers') if a.get('conversation_id')==payload['conversation_id']][:6]
    words=set((question+' '+' '.join(a['question'] for a in history)).lower().split())
    documents=store.all_docs('articles')+store.all_docs('documents')
    ranked=sorted(documents,key=lambda a:sum(w in (a.get('title','')+' '+a.get('text','')).lower() for w in words),reverse=True)
    sources=[a for a in ranked if any(w in (a.get('title','')+' '+a.get('text','')).lower() for w in words)][:6]
    limitation='Uses stored approved evidence; retrieved timestamps are not fresh independent verification.'
    if payload['mode']=='deep':
        limitation+=' Wider-web discovery is unavailable: an authorised search provider has not been configured. No claim is labelled Confirmed.'
    text='No relevant evidence was found in your approved sources.'
    if sources:
        output=generate('Answer this question using cited source IDs. Use conversation context where relevant. Do not label claims Confirmed. Question: '+question,
                        json.dumps({'history':history,'sources':sources}))
        text=output or 'AI synthesis is unavailable. Relevant source excerpts:\n\n'+'\n\n'.join('['+s['id']+'] '+s.get('title','')+'\n'+s.get('text','')[:500] for s in sources)
    record={**payload,'text':text,'sources':sources,'ready_at':now(),'limitations':limitation,'verification':'Partially Verified' if sources else 'Unverified','audio_status':'not_requested'}
    store.put('answers',payload['id'],record)
    store.enqueue('voice','audio.generation.requested',{'domain':'answers','id':payload['id'],'text':text},'voice:'+payload['id'])


def opportunities(payload):
    briefing=store.get('briefings',payload['briefing_id'])
    if not briefing or not briefing['articles']:
        return
    text=generate('Identify up to three software opportunity hypotheses for 14Digital in Oman, GCC, UK or US. Include title, evidence, market, customer, problem, proposed solution, relevance, hypothesis, confidence rationale, complexity, urgency and next action. Do not invent demand or financial figures.',json.dumps(briefing['articles']))
    if text:
        store.put('opportunities',payload['briefing_id'],{'id':payload['briefing_id'],'text':text,'sources':briefing['articles'],'ready_at':now(),'status':'hypotheses_requiring_review'})
