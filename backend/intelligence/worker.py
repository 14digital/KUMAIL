import logging
import os
import time
from . import store
from .pipeline import briefing, narrate, now, schedule
from .research import answer, opportunities

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
HANDLERS={'news':briefing,'voice':narrate,'research':answer,'deep':answer,'opportunities':opportunities}


def process_job(job):
    try:
        HANDLERS[job['queue']](job['payload'])
        store.finish(job)
    except Exception as exc:
        terminal=job['attempts']>=4 or not getattr(exc,'retryable',True)
        logging.warning('job_failed role=%s id=%s type=%s',job['queue'],job['id'],type(exc).__name__)
        store.finish(job,type(exc).__name__,terminal=terminal)
        if job['queue']=='voice' and terminal:
            payload=job['payload']
            record=store.get(payload['domain'],payload['id'])
            if record and record.get('audio_status')=='failed':
                store.put(payload['domain'],payload['id'],{**record,'audio_retry_pending':False})


def main():
    role=os.getenv('SERVICE_ROLE','news')
    if role=='voice':
        from .narration import recover_unavailable_audio
        recover_unavailable_audio()
    while True:
        try:
            health={'id':role,'heartbeat':now()}
            if role=='voice':
                health.update(elevenlabs_key_loaded=bool(os.getenv('ELEVENLABS_API_KEY','').strip()),elevenlabs_voice_loaded=bool(os.getenv('ELEVENLABS_VOICE_ID','').strip()))
            store.put('health',role,health)
            if role=='scheduler':
                schedule(); time.sleep(20); continue
            job=store.claim(role)
            if not job:
                time.sleep(1); continue
            process_job(job)
        except Exception:
            logging.exception('worker_loop_failed role=%s',role)
            time.sleep(5)

if __name__=='__main__':
    main()
