"""Run through Import Publishers.cmd; feed checks happen on the user's machine.

This file is streamed into the existing API container, so no image rebuild is needed.
The JSON list is delivered on stdin as part of the payload by import-publishers.ps1.
"""
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlsplit
import feedparser
import httpx
from intelligence.security import retrieve


def source_for(name, url, category):
    host = urlsplit(url).hostname
    if not host:
        raise ValueError('Missing feed hostname')
    domains = {host}
    if host == 'feeds.bbci.co.uk':
        domains.update(['www.bbc.com','bbc.com','www.bbc.co.uk','bbc.co.uk'])
    elif host == 'feeds.npr.org':
        domains.update(['www.npr.org','npr.org'])
    elif host == 'news.crunchbase.com':
        domains.update(['crunchbase.com','www.crunchbase.com'])
    else:
        domains.add(host[4:] if host.startswith('www.') else 'www.'+host)
    return {'name':name,'rss':url,'domains':sorted(domains),'categories':[category],
            'authors':[],'enabled':True,'opinion':category=='strategy mindset'}


def inspect_feed(source, fetch=retrieve):
    feed=feedparser.parse(fetch(source['rss'],source['domains']))
    if not feed.version or not feed.entries:
        raise ValueError('Response is not a parsable, non-empty RSS/Atom feed')
    eligible=[entry for entry in feed.entries if entry.get('title') and
              urlsplit(entry.get('link','')).scheme=='https' and
              urlsplit(entry.get('link','')).hostname in source['domains']]
    if not eligible:
        raise ValueError('No feed items link to approved publisher domains')
    return {'entries':len(feed.entries),'approved_links':len(eligible),'parse_warning':bool(feed.bozo)}


def main(rows):
    token=os.getenv('APP_TOKEN','')
    if not token:
        print('APP_TOKEN is missing from the running API container.');return 1
    base='http://127.0.0.1:8000'
    headers={'Authorization':'Bearer '+token}
    # Bypass Internet proxies only for loopback calls to this same container.
    # Publisher retrieval uses the normal configured proxy and TLS verification.
    with httpx.Client(base_url=base,headers=headers,trust_env=False,timeout=20) as api:
        response=api.get('/api/dashboard');response.raise_for_status()
        existing={s['rss'] for s in response.json()['sources']}
    def add(row):
        name,url,category=row
        result={'name':name,'rss':url,'checked_at':datetime.now(timezone.utc).isoformat()}
        if url in existing:
            return {**result,'status':'preserved_existing'}
        try:
            source=source_for(name,url,category)
            evidence=inspect_feed(source)
            with httpx.Client(base_url=base,headers=headers,trust_env=False,timeout=20) as api:
                response=api.post('/api/sources',json=source)
                response.raise_for_status()
            return {**result,'status':'added','check':evidence}
        except httpx.HTTPStatusError as exc:
            return {**result,'status':'needs_review','reason':'HTTP '+str(exc.response.status_code)+'; no access workaround attempted'}
        except (httpx.HTTPError,ValueError,OSError) as exc:
            # Do not log provider responses, request headers or credentials.
            return {**result,'status':'needs_review','reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(add,rows))
    for result in results:
        print(result['status'].upper()+': '+result['name']+(' — '+result['reason'] if result.get('reason') else ''))
    added=sum(r['status']=='added' for r in results)
    preserved=sum(r['status']=='preserved_existing' for r in results)
    print(f'\nAdded {added}; preserved {preserved}; needs review {len(results)-added-preserved}.')
    print('Full feed parsing was checked, not full-article access or licensing. Date eligibility is applied when briefings run.')
    print('IMPORT_REPORT_JSON='+json.dumps(results,ensure_ascii=True))
    return 0 if all(r['status']!='needs_review' for r in results) else 2
