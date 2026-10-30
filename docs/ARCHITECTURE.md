# Architecture decision: single-host foundation

```mermaid
flowchart LR
  User --> Web[Next.js dashboard / same-origin BFF]
  Web --> API[Authenticated FastAPI gateway]
  API --> Broker[(Durable leased job queues)]
  Scheduler --> Broker
  Broker --> News[News worker]
  Broker --> Research[Trusted research worker]
  Broker --> Deep[Separate Deep Dive worker]
  Broker --> Voice[ElevenLabs worker]
  Broker --> Opportunities[Opportunity worker]
  News --> RSS[Approved public RSS]
  Research --> AI[OpenAI Responses API]
  Voice --> Media[(Private audio files)]
```

Six independent worker processes and one API process can be restarted separately. The scheduler only enqueues; it never performs retrieval. Research and Deep Dive have separate queues. Queue inserts are durable SQLite transactions, claims use an immediate transaction, expired leases can be recovered, and failed work backs off into a dead-letter state after four attempts. Event names have `.v1` suffixes. Execution IDs deduplicate scheduler runs and audio requests. Consumers must tolerate at-least-once delivery.

This is a **single-host deployment grouping**, using per-domain SQLite files and a shared SQLite broker as a low-cost alternative to PostgreSQL/Redis. It is not a horizontally distributed production deployment. Persistence initialisation is the first migration (`documents` and `jobs`, created idempotently). No external migration runner is required at this version.

Known boundary gaps: the current API and workers use shared repository functions, and voice updates a completed record's audio status. Database access is not yet isolated by service credentials. This does not satisfy the specification's full independent data ownership requirement. A subsequent production migration must add PostgreSQL service-owned schemas, an outbox/inbox and API/event-only cross-domain updates. Do not scale multiple hosts against these SQLite files or place them on NFS.

The shared host, volume, broker and gateway remain failure points. A long publisher request does not block the research worker, but a large number of publishers can delay news. One worker per queue is the supported configuration. A lease is 180 seconds; jobs must stay below it. The current broker fences stale completion, but domain writes do not yet have complete fencing. Multi-worker production operation needs a lease-renewal/outbox implementation.

## Contracts

- `briefing.scheduled.v1`: news queue, edition ID, title, scheduled ISO time.
- `briefing.text.ready.v1`: opportunities queue, briefing ID.
- `research.requested.v1`: research/deep queue, ID, question, mode, conversation ID.
- `audio.generation.requested.v1`: voice queue, originating domain, completed text and ID.

These are the implemented events; the broader master-spec event catalogue is not yet implemented. The gateway exposes typed request models through FastAPI OpenAPI. Worker status and bounded job history are available through `/api/operations`.

## Scheduling and evidence

Oman editions run at 07:00, 11:00, 15:00 and 21:00 in `Asia/Muscat`. Startup catches up today's elapsed slots; older missed days are not replayed. Source feed items need a usable publication date. Retrieval is bounded to 2 MB per feed with no redirects. The last two days are eligible; identical URL/content versions already published are excluded. Changed content can be selected again. Rankings are explicitly relevance rankings, never invented readership counts.

The evidence verifier accepts only exact bounded quotations from supplied documents and counts **reviewed** independent source groups. It is unit tested, but not yet wired into an automated broader-web claim decomposition pipeline. AI research output is never promoted to Confirmed. Trusted retrieval is lexical, with conversation context; semantic/hybrid retrieval is future work.
