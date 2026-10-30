"""Conservative evidence rules. Independence is reviewed metadata, never inferred from host count."""

def verify_claim(claim, sources):
    evidence = []
    for item in claim.get('evidence', []):
        source = sources.get(item.get('source_id'))
        quote = item.get('quote','').strip()
        if not source or not quote or len(quote)>400 or quote not in source.get('text',''):
            raise ValueError('Unsupported quotation or missing source')
        evidence.append({**item, 'source':source})
    groups = {e['source']['independence_group'] for e in evidence
              if e['source'].get('independence_reviewed') and e['source'].get('credible') and e['source'].get('independence_group')}
    status = 'Disputed' if claim.get('disputed') else 'Confirmed' if len(groups)>=3 else 'Partially Verified' if evidence else 'Unverified'
    return {**claim,'status':status,'evidence':evidence}
