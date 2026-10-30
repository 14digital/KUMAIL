"""Narration diagnostics contain controlled messages, never provider response bodies."""
import os
import uuid
from . import store


class NarrationError(RuntimeError):
    def __init__(self, reason, retryable=False, code='provider_error'):
        super().__init__(reason)
        self.reason=reason
        self.retryable=retryable
        self.code=code


def provider_error(response):
    try:
        detail=response.json().get('detail',{})
        code=detail.get('status','') if isinstance(detail,dict) else ''
    except (ValueError,AttributeError):
        code=''
    if not isinstance(code,str):
        code=''
    known={
        'invalid_api_key': ('ElevenLabs rejected the API key. Check ELEVENLABS_API_KEY, save .env and run the updater.',False),
        'quota_exceeded': ('ElevenLabs reports insufficient credits or quota. Check your ElevenLabs balance and plan, then retry audio.',False),
        'insufficient_credits': ('ElevenLabs reports insufficient credits. Check your account balance, then retry audio.',False),
        'paid_plan_required': ('This ElevenLabs voice or model requires a paid plan. Choose an eligible voice or update the plan, then retry.',False),
        'voice_not_found': ('ElevenLabs could not find this voice. Use the voice ID, rather than its name or share URL, and ensure your account can use it.',False),
        'missing_permissions': ('The ElevenLabs key lacks permission for this request. Check text-to-speech access and voice permissions.',False),
        'detected_unusual_activity': ('ElevenLabs blocked this request under its account or network policy. Review the account with ElevenLabs; no access workaround is attempted.',False),
        'too_many_concurrent_requests': ('ElevenLabs is busy with concurrent requests. A bounded retry will be attempted.',True),
        'rate_limit_exceeded': ('ElevenLabs rate-limited narration. A bounded retry will be attempted.',True),
    }
    if code in known:
        reason,retryable=known[code]
        return NarrationError(reason,retryable,code)
    status=response.status_code
    reason={
        401:'ElevenLabs did not authorise narration. Check the key, its text-to-speech permissions and your account credits.',
        402:'ElevenLabs requires credits or a plan change before narration can run.',
        403:'ElevenLabs denied access. Check the key permissions and whether your account can use this voice.',
        404:'ElevenLabs could not find the selected voice. Check ELEVENLABS_VOICE_ID and account access.',
        400:'ElevenLabs rejected the narration settings. Check the voice ID and model availability.',
        422:'ElevenLabs rejected the narration settings. Check the voice ID and model availability.',
        429:'ElevenLabs rate-limited narration. A bounded retry will be attempted.',
    }.get(status,'ElevenLabs is temporarily unavailable. A bounded retry will be attempted.' if status>=500 else 'ElevenLabs rejected narration. Review the account and voice configuration.')
    return NarrationError(reason,status==429 or status>=500,'http_'+str(status))


def queue_audio(domain, record_id, text):
    """Single active narration request per record; repeat clicks reuse its job."""
    return store.enqueue_record_job('answer_voice' if domain=='answers' else 'voice','audio.generation.requested',{'domain':domain,'id':record_id,'text':text})


def recover_unavailable_audio():
    """On credential reload recover at most the latest eligible record per domain."""
    if not os.getenv('ELEVENLABS_API_KEY','').strip() or not os.getenv('ELEVENLABS_VOICE_ID','').strip():
        return []
    recovered=[]
    for domain in ('briefings','answers'):
        # An older archive remains available for user-triggered retries.
        eligible=[r for r in store.all_docs(domain) if r.get('text') and (domain!='briefings' or r.get('articles'))]
        if not eligible:
            continue
        record=eligible[0]
        if record.get('audio_status') not in ('unavailable','not_requested'):
            continue
        from .editorial import PRESENTATION_VERSION,queue_presentation
        job_id=queue_audio(domain,record['id'],record['narration_script']) if record.get('presentation_version')==PRESENTATION_VERSION and record.get('narration_script') else queue_presentation(domain,record['id'],force=True)
        store.patch(domain,record['id'],{'audio_status':'queued','audio_reason':'Narration queued after loading ElevenLabs configuration.','audio_job_id':job_id})
        recovered.append(job_id)
    return recovered
