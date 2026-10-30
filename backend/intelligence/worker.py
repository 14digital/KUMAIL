import logging
import os
import time
import threading
from . import store
from .pipeline import briefing, narrate, now, schedule
from .research import answer, opportunities

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
from .editorial import prepare_presentation

HANDLERS={'editor':prepare_presentation,'answer_editor':prepare_presentation,'answer_voice':narrate,'news':briefing,'voice':narrate,'research':answer,'deep':answer,'opportunities':opportunities}


def process_job(job):
    stop=threading.Event()
    def keep_lease():
        while not stop.wait(30):
            try:
                if not store.renew(job):return
            except Exception:logging.warning('lease_renewal_failed id=%s',job['id'])
    keeper=threading.Thread(target=keep_lease,daemon=True);keeper.start()
    try:
        HANDLERS[job['queue']](job['payload'])
        store.finish(job)
    except Exception as exc:
        terminal=job['attempts']>=4 or not getattr(exc,'retryable',True)
        logging.warning('job_failed role=%s id=%s type=%s',job['queue'],job['id'],type(exc).__name__)
        store.finish(job,type(exc).__name__,terminal=terminal)
        if job['queue'] in ('voice','answer_voice','editor','answer_editor') and terminal:
            payload=job['payload']
            record=store.get(payload['domain'],payload['id'])
            if record and job['queue'] in ('editor','answer_editor'):
                store.patch(payload['domain'],payload['id'],{'audio_status':'failed','audio_reason':'The spoken edition could not be prepared after bounded retries. Your written evidence is intact; you can retry listening preparation.','audio_retry_pending':False})
            elif record and record.get('audio_status')=='failed':
                store.patch(payload['domain'],payload['id'],{'audio_retry_pending':False})

    finally:
        stop.set();keeper.join(timeout=1)


def consume(role):
    while True:
        try:
            health={'id':role,'heartbeat':now()}
            if role in ('voice','answer_voice'):
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

def main():
    role=os.getenv('SERVICE_ROLE','news')
    if role=='voice':
        from .narration import recover_unavailable_audio
        recover_unavailable_audio()
    # One reserved consumer for answers; long scheduled editions cannot occupy it.
    child={'editor':'answer_editor','voice':'answer_voice'}.get(role)
    if child:threading.Thread(target=consume,args=(child,),daemon=True).start()
    consume(role)

if __name__=='__main__':
    main()
