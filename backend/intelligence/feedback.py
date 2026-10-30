"""Bounded, reviewable behaviour-based topic adjustments, separate from explicit interests."""
import math
from datetime import datetime,timezone
from . import store
from .curation import canonical_url

WEIGHTS={'question':.75,'replay':.5,'seek_backward':.2,'completed':.2,'skip':-.2,'seek_forward':0}


def record_interaction(event):
    briefing=store.get('briefings',event['briefing_id'])
    if not briefing:raise ValueError('Briefing not found')
    article=next((a for a in briefing.get('articles',[]) if a['id']==event['article_id']),None)
    if not article:raise ValueError('Article is not in this briefing')
    if store.get('preferences','user',{}).get('adaptive_curation',True) is False:return {'id':event['id'],'status':'learning disabled; signal not stored'}
    record={**event,'at':datetime.now(timezone.utc).isoformat(),'topics':list(dict.fromkeys(t.lower().strip() for t in article.get('categories',[]) if isinstance(t,str) and t.strip()))[:20],
            'story_key':canonical_url(article.get('url','')) or article['id'],'preference_kind':'inferred_signal'}
    import json
    with store.connect('interactions') as db:
        db.execute('INSERT OR IGNORE INTO documents(id,value) VALUES (?,?)',(event['id'],json.dumps(record)))
    return store.get('interactions',event['id'])


def topic_adjustments(at=None):
    if store.get('preferences','user',{}).get('adaptive_curation',True) is False:return {}
    at=at or datetime.now(timezone.utc)
    topics={}
    # One action of each kind per story/day; dragging a slider cannot flood the score.
    seen=set()
    for event in store.all_docs('interactions'):
        try:age=max(0,(at-datetime.fromisoformat(event['at'])).total_seconds()/86400)
        except (KeyError,TypeError,ValueError):continue
        if age>180:continue
        action=event['action'];weight=WEIGHTS.get(action,0)
        if action=='skip' and event.get('progress',0)>=.5:weight=0
        unique=(event['story_key'],event['at'][:10],action)
        if unique in seen or not weight:continue
        seen.add(unique)
        for topic in event.get('topics',[]):
            item=topics.setdefault(topic,{'stories':set(),'score':0,'events':0})
            item['stories'].add(event['story_key']);item['score']+=weight*math.pow(.5,age/30);item['events']+=1
    return {topic:max(-1,min(1,item['score']/3)) for topic,item in topics.items() if len(item['stories'])>=3 and abs(item['score'])>1e-6}


def learning_summary():
    return {'adjustments':topic_adjustments(),'kind':'inferred, not explicit preferences',
            'rules':'At least three different stories; 30-day half-life; small bounded adjustments. Forward seeking alone is neutral. A skip is not an instruction to exclude a topic.'}
