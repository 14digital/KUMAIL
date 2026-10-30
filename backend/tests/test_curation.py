import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
from intelligence import store,pipeline
from intelligence.api import app
from intelligence.curation import collect_candidates,cluster_candidates,already_delivered
from intelligence.editorial import build_briefing_presentation
from intelligence.feedback import record_interaction,topic_adjustments

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'ROOT',tmp_path)
    monkeypatch.setenv('APP_TOKEN','fixture-'+'x'*40)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)


def article(source,index,title=None):
    return {'id':f'{source}-{index}','source_id':source,'publisher':source,'title':title or f'{source} development number {index}',
            'text':f'Evidence for {source} report {index}.','url':f'https://{source}.example/{index}','categories':['AI'],
            'published_at':f'2026-10-30T{12+index:02d}:00:00+00:00'}


def test_three_candidates_from_every_feed_without_global_family_cap():
    collected=[({'id':s,'name':s},[article(s,i) for i in range(5)],None) for s in ['bbc-world','bbc-uk','dawn','guardian','oman']]
    pool,coverage=collect_candidates(collected,[],[],{})
    assert len(pool)==15 and all(c['candidates']==3 for c in coverage)
    assert all('readership unavailable' in c['ranking'] for c in coverage)
    assert all(len([a for a in pool if a['source_id']==s])==3 for s in ['bbc-world','bbc-uk','dawn','guardian','oman'])


def test_no_invented_candidates_for_failed_or_sparse_feeds():
    pool,coverage=collect_candidates([({'id':'sparse'},[article('sparse',0)],None),({'id':'failed'},[],'HTTP 403')],[],[],{})
    assert len(pool)==1
    assert coverage[0]['status']=='fewer_than_requested'
    assert coverage[1]['status']=='failed' and coverage[1]['candidates']==0


def test_only_publisher_popularity_provenance_is_ranked_as_popular():
    items=[article('publisher',i) for i in range(5)]
    items[0].update(popularity_rank=1,popularity_provenance='https://publisher.example/most-read/rss')
    pool,coverage=collect_candidates([({'id':'publisher'},items,None)],[],[],{})
    assert pool[0]['id']==items[0]['id']
    assert 'publisher-provided' in coverage[0]['ranking']
    assert all('views' not in item for item in pool)


def test_cross_publisher_paraphrases_are_grouped_once_with_all_sources():
    a=article('one',0,'Oman approves new artificial intelligence law')
    b=article('two',0,'New artificial intelligence law approved in Oman')
    c=article('three',0,'England wins cricket final at Lords')
    groups,method=cluster_candidates([a,b,c])
    assert len(groups)==2
    assert any(set(g['article_ids'])=={a['id'],b['id']} for g in groups)


def test_semantic_grouping_validates_complete_partition_and_handles_languages():
    items=[article('en',0,'Oman announces technology programme'),article('urdu',0,'عمان میں ٹیکنالوجی پروگرام'),article('sport',0,'Warwickshire cricket academy report')]
    groups,_=cluster_candidates(items,lambda *a,**kw:json.dumps({'groups':[['c0','c1'],['c2']]}))
    assert len(groups)==2
    groups,_=cluster_candidates(items,lambda *a,**kw:json.dumps({'groups':[['invented','c0']]}))
    assert len(groups)==3


def test_material_update_is_not_hidden_by_near_identical_body():
    old=article('one',0,'Oman announces programme')
    updated={**old,'id':'new-version','text':old['text']+' The deadline is now tomorrow.'}
    assert already_delivered(old,[old])
    assert not already_delivered(updated,[old])


def test_all_unique_groups_are_narrated_beyond_eight():
    articles=[article('feed'+str(i),0) for i in range(21)]
    groups=[{'id':'g'+str(i),'representative_id':a['id'],'article_ids':[a['id']],'headline':a['title']} for i,a in enumerate(articles)]
    result=build_briefing_presentation({'id':'manual:all','articles':articles,'story_groups':groups},lambda *a,**kw:None)
    assert len(result['stories'])==21
    assert {s['source_ids'][0] for s in result['stories']}=={a['id'] for a in articles}
    assert [s['story_index'] for s in result['narration_segments'] if s['story_index'] is not None]==list(range(21))
    assert len([s for s in result['narration_segments'] if s['title']=='Your briefing'])==1
    assert len([s for s in result['narration_segments'] if s['title']=='The outlook'])==1


def test_merged_reports_make_one_spoken_story_with_multiple_citations():
    articles=[article('one',0),article('two',0)]
    groups=[{'id':'same-event','representative_id':articles[0]['id'],'article_ids':[a['id'] for a in articles]}]
    result=build_briefing_presentation({'articles':articles,'story_groups':groups},lambda *a,**kw:None)
    assert len(result['stories'])==1 and len(result['stories'][0]['source_ids'])==2


def seed_feedback_story(index):
    a=article('publisher',index)
    store.put('briefings','b'+str(index),{'id':'b'+str(index),'articles':[a]})
    return {'briefing_id':'b'+str(index),'article_id':a['id']}


def test_feedback_is_idempotent_bounded_and_requires_multiple_stories():
    for i in range(2):
        context=seed_feedback_story(i)
        event={'id':'event'+str(i),**context,'action':'question','progress':0}
        record_interaction(event);record_interaction(event)
    assert len(store.all_docs('interactions'))==2
    assert topic_adjustments()=={}
    context=seed_feedback_story(2)
    record_interaction({'id':'third',**context,'action':'replay','progress':.2})
    weights=topic_adjustments()
    assert 0<weights['ai']<=1
    assert store.get('preferences','user',{})=={}
    assert topic_adjustments(datetime.now(timezone.utc)+timedelta(days=31))['ai']<weights['ai']


def test_forward_seek_and_late_skip_do_not_imply_disinterest():
    for i in range(4):
        context=seed_feedback_story(i)
        record_interaction({'id':'f'+str(i),**context,'action':'seek_forward','progress':.4})
        record_interaction({'id':'s'+str(i),**context,'action':'skip','progress':.9})
    assert topic_adjustments()=={}


def test_learning_api_auth_context_and_reset_keep_explicit_interests():
    client=TestClient(app,headers={'Authorization':'Bearer '+'fixture-'+'x'*40})
    context=seed_feedback_story(0)
    body={'id':'one',**context,'action':'replay','progress':.1}
    assert TestClient(app).post('/api/interactions',json=body).status_code==401
    assert client.post('/api/interactions',json={**body,'article_id':'wrong'}).status_code==422
    assert client.post('/api/interactions',json=body).status_code==201
    store.put('preferences','user',{'interests':['Cricket']})
    assert client.delete('/api/learning').status_code==200
    assert store.all_docs('interactions')==[]
    assert store.get('preferences','user')['interests']==['Cricket']


def test_feedback_changes_future_ranking_without_changing_source_quota():
    for i in range(3):
        context=seed_feedback_story(i)
        record_interaction({'id':'q'+str(i),**context,'action':'question','progress':0})
    articles=[{**article('newfeed',i),'categories':['AI'] if i==0 else ['Business']} for i in range(5)]
    baseline,_=collect_candidates([({'id':'newfeed'},articles,None)],[],[],{})
    personalised,_=collect_candidates([({'id':'newfeed'},articles,None)],[],[],topic_adjustments())
    assert baseline[0]['id']=='newfeed-4'
    assert personalised[0]['id']=='newfeed-0'
    assert len(personalised)==3


def test_learning_can_be_disabled_without_storing_new_signals():
    context=seed_feedback_story(0)
    store.put('preferences','user',{'interests':['AI'],'adaptive_curation':False})
    result=record_interaction({'id':'private',**context,'action':'question','progress':0})
    assert 'disabled' in result['status']
    assert not store.all_docs('interactions')
    assert topic_adjustments()=={}


def test_upgrade_prepares_one_fresh_edition_automatically():
    store.put('sources','feed',{'id':'feed','enabled':True})
    store.put('briefings','old',{'id':'old','articles':[]})
    first=pipeline.refresh_curation_on_upgrade()
    assert first is not None
    assert pipeline.refresh_curation_on_upgrade()==first
    assert len(store.jobs())==1 and store.jobs()[0]['queue']=='news'
    store.put('briefings','new',{'id':'new','curation_version':'all-sources-v2'})
    assert pipeline.refresh_curation_on_upgrade() is None


def test_similar_headlines_about_different_countries_or_teams_are_not_lost():
    a=article('one',0,'UK annual inflation rises after energy price increases')
    b=article('two',0,'US annual inflation rises after energy price increases')
    groups,_=cluster_candidates([a,b],lambda *a,**kw:json.dumps({'groups':[['c0','c1']]}))
    assert len(groups)==2
    a=article('one',0,'Warwickshire cricket academy wins under nineteen tournament')
    b=article('two',0,'Yorkshire cricket academy wins under nineteen tournament')
    groups,_=cluster_candidates([a,b])
    assert len(groups)==2


def test_full_briefing_pipeline_preserves_all_feed_quotas_and_all_unique_stories(monkeypatch):
    for source in ['alpha','beta','gamma','delta','epsilon']:
        store.put('sources',source,{'id':source,'name':source,'rss':'https://'+source+'.example/rss'})
    monkeypatch.setattr(pipeline,'ingest',lambda source:[article(source['id'],i) for i in range(5)])
    result=pipeline.briefing({'id':'manual:all-feeds','title':'Test edition'})
    assert result['candidate_count']==15
    assert len(result['articles'])==result['unique_story_count']==15
    assert all(source['candidates']==3 for source in result['source_coverage'])
    presentation=build_briefing_presentation(result,lambda *a,**kw:None)
    assert len(presentation['stories'])==15


def test_popularity_position_is_taken_from_the_configured_feed(monkeypatch):
    from email.utils import format_datetime
    date=format_datetime(datetime.now(timezone.utc))
    xml=f'<rss version="2.0"><channel><title>Publisher most read</title><item><title>First</title><link>https://publisher.example/first</link><pubDate>{date}</pubDate></item><item><title>Second</title><link>https://publisher.example/second</link><pubDate>{date}</pubDate></item></channel></rss>'
    monkeypatch.setattr(pipeline,'retrieve',lambda *args:xml.encode())
    source={'id':'publisher','name':'Publisher','rss':'https://publisher.example/rss','domains':['publisher.example'],'_endpoint':'https://publisher.example/popular','_popular':True}
    found=pipeline.ingest(source)
    assert [a['popularity_rank'] for a in found]==[1,2]
    assert all(a['popularity_provenance']=='https://publisher.example/popular' for a in found)
    source.pop('_popular');normal=pipeline.ingest(source)
    assert all('popularity_rank' not in a for a in normal)


def test_short_interest_keywords_do_not_match_unrelated_word_fragments():
    from intelligence.curation import relevance
    daily={**article('one',0),'title':'Daily markets report','text':'Daily financial coverage','categories':[]}
    ai={**daily,'categories':['AI']}
    assert relevance(daily,['AI'],{})==0
    assert relevance(ai,['AI'],{})>0
