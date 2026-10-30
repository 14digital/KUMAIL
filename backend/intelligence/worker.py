import logging
import os
import time
from . import store
from .pipeline import briefing, narrate, now, schedule
from .research import answer, opportunities

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
HANDLERS={'news':briefing,'voice':narrate,'research':answer,'deep':answer,'opportunities':opportunities}


def main():
    role=os.getenv('SERVICE_ROLE','news')
    while True:
        try:
            store.put('health',role,{'id':role,'heartbeat':now()})
            if role=='scheduler':
                schedule(); time.sleep(20); continue
            job=store.claim(role)
            if not job:
                time.sleep(1); continue
            try:
                HANDLERS[role](job['payload'])
                store.finish(job)
            except Exception as exc:
                logging.warning('job_failed role=%s id=%s type=%s',role,job['id'],type(exc).__name__)
                store.finish(job,type(exc).__name__)
        except Exception:
            logging.exception('worker_loop_failed role=%s',role)
            time.sleep(5)

if __name__=='__main__':
    main()
