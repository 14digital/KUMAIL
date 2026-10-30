"""Per-feed candidate quotas, conservative duplicate grouping and truthful rankings."""
import hashlib
import json
import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit
from . import store

STOP={'the','a','an','and','or','to','in','of','for','on','as','is','at','with','from','by','after','says','say','news','latest','live','updates'}


def canonical_url(url):
    parsed=urlsplit(url)
    query=[(k,v) for k,v in parse_qsl(parsed.query) if not k.lower().startswith('utm_') and k.lower() not in {'fbclid','gclid','mc_cid','mc_eid'}]
    host=(parsed.hostname or '').lower().removeprefix('www.')
    return urlunsplit(('https',host,parsed.path.rstrip('/'),urlencode(sorted(query)),''))


def words(text):
    return set(re.findall(r'\w+',text.lower()))-STOP


def locations(text):
    aliases={'usa':'us','america':'us','britain':'uk','england':'uk','scotland':'uk','wales':'uk'}
    known={'oman','pakistan','india','uk','us','usa','britain','america','england','scotland','wales','china','russia','ukraine','israel','iran'}
    return {aliases.get(word,word) for word in words(text)&known}


def location_conflict(a,b):
    left=locations(a['title']);right=locations(b['title'])
    return bool(left and right and not left&right)


def same_story(a,b):
    # Do not collapse separate developments just because they share an organisation.
    if a.get('url') and b.get('url') and canonical_url(a['url'])==canonical_url(b['url']):return True
    if location_conflict(a,b):return False
    entities=lambda text:set(re.findall(r'\b[A-Z][A-Za-z]+\b',text))-{'The','New','Latest','Breaking','Report','AI','CEO','PM','BBC','News','World','After'}
    one=entities(a['title']);two=entities(b['title'])
    if one and two and not one&two:return False
    left=words(a['title']);right=words(b['title'])
    if not left or not right:return False
    overlap=len(left&right)/max(1,len(left|right))
    common=len(left&right)
    return left==right or (common>=4 and overlap>=.62) or (common>=4 and SequenceMatcher(None,a['title'].lower(),b['title'].lower()).ratio()>=.82)


def already_delivered(article,history):
    for previous in history:
        if article['id']==previous['id']:return True
        if same_story(article,previous):
            text=article.get('text','').strip();old=previous.get('text','').strip()
            # A small factual change may be material; never discard it merely
            # because most of the article body stayed the same.
            if text==old and words(article['title'])==words(previous['title']):return True
    return False


def relevance(article,interests,adjustments):
    text=(article['title']+' '+article.get('text','')+' '+' '.join(article.get('categories',[]))).lower()
    explicit=sum(2 for interest in interests if re.search(r'(?<!\w)'+re.escape(interest.lower().strip())+r'(?!\w)',text))
    adaptive=sum(adjustments.get(topic.lower(),0) for topic in article.get('categories',[]))
    # Inferred behaviour can adjust the order but cannot override an explicit interest.
    return explicit+max(-1,min(1,adaptive))


def collect_candidates(per_source,history,interests,adjustments,per_feed=3):
    pool={};checks=[]
    history_ids={a['id'] for a in history}
    history_content={(frozenset(words(a['title'])),a.get('text','').strip()) for a in history if words(a['title'])}
    for source,articles,error in per_source:
        unique=list({a['id']:a for a in articles}.values())
        fresh=[a for a in unique if a['id'] not in history_ids and (frozenset(words(a['title'])),a.get('text','').strip()) not in history_content]
        ranked=sorted(fresh,key=lambda a:(a.get('popularity_rank') is not None,-a.get('popularity_rank',10**9),relevance(a,interests,adjustments),a.get('published_at','')),reverse=True)
        chosen=ranked[:per_feed]
        for article in chosen:
            existing=pool.get(article['id'])
            if not existing or article.get('popularity_rank',10**9)<existing.get('popularity_rank',10**9):pool[article['id']]=article
        checks.append({'source_id':source['id'],'name':source.get('name',source['id']),'eligible_new':len(fresh),'retrieved_qualifying':len(unique),'excluded_as_delivered':len(unique)-len(fresh),'candidates':len(chosen),
                       'ranking':'publisher-provided most-read feed order' if any(a.get('popularity_rank') is not None for a in chosen) else 'relevance and freshness; readership unavailable',
                       'status':('partial_failure' if articles else 'failed') if error else 'fewer_than_requested' if len(chosen)<per_feed else 'ok','error':error})
    return list(pool.values()),checks


def cluster_candidates(articles,generator=None):
    """Optional semantic grouping; validate an exact partition before accepting it."""
    if not articles:return [],'No new candidates'
    groups=[]
    for article in articles:
        match=next((g for g in groups if any(same_story(article,other) for other in g)),None)
        if match is None:groups.append([article])
        else:match.append(article)
    method='URL and headline similarity grouping'
    if generator and len(groups)>1:
        # Compact aliases prevent fabrication of source identifiers and reduce token cost.
        aliases={f'c{i}':group for i,group in enumerate(groups)}
        context=[{'id':key,'title':group[0]['title'],'excerpt':group[0].get('text','')[:500],'publisher':group[0].get('publisher')} for key,group in aliases.items()]
        output=generator('Group only reports about the SAME concrete news development, including paraphrases or different languages. Do not merge different events, locations, decisions or developments just because they share a topic/person. Return JSON {"groups":[["c0","c1"],["c2"]]}. Every supplied ID must appear exactly once. Singleton groups are valid. No rankings or invented popularity.',json.dumps(context,ensure_ascii=False),max_output_tokens=4500)
        try:
            parsed=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',output.strip()))['groups'] if output else None
            flattened=[key for group in parsed for key in group] if parsed else []
            if not parsed or any(not isinstance(group,list) or not group for group in parsed) or len(flattened)!=len(set(flattened)) or set(flattened)!=set(aliases):raise ValueError('Invalid grouping partition')
            proposed=[[article for alias in group for article in aliases[alias]] for group in parsed]
            if any(location_conflict(a,b) for group in proposed for i,a in enumerate(group) for b in group[i+1:]):raise ValueError('Distinct country developments merged')
            groups=proposed
            method='AI-assisted event grouping, with URL/headline fallback; not independent verification'
        except (ValueError,TypeError,KeyError,AttributeError):pass
    output=[]
    for group in groups:
        representative=max(group,key=lambda a:a.get('published_at',''))
        key=hashlib.sha256('|'.join(sorted(canonical_url(a.get('url','')) or a['id'] for a in group)).encode()).hexdigest()
        output.append({'id':key,'article_ids':[a['id'] for a in group],'representative_id':representative['id'],'headline':representative['title']})
    return output,method
