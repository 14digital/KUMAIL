# KUMAIL implementation status

## All-source curation update

Every enabled feed now supplies up to three eligible new candidates before duplicate grouping. The publisher-family and eight-story edition caps are gone. All distinct grouped events are retained in the spoken edition, processed in bounded editorial batches. Per-feed counts and failure/ranking statuses are recorded. Publisher most-read order is used only for an explicitly configured publisher ranking feed; ordinary RSS does not imply verified popularity.

Private question, replay, skip, completion and seek events feed small decaying topic adjustments after engagement with multiple articles. Forward seeks alone are neutral. Explicit interests remain separate; review, opt-out and reset controls are available. This is initial tag-based adaptation, not the full hierarchical memory system. AI-assisted grouping is a heuristic and is not a claim of independently verified facts or perfect semantic deduplication.

## Current listening release

The UI is now a listening room with KUMAIL branding, one primary Play control, optional headline/evidence reading and settings/library tucked away. The separate editor worker creates original conversational scripts with source-attributed chapter metadata. Narration never uses the analyst record directly. Edition-specific duration targets are adjustable; thin evidence produces a shorter edition or labelled headline fallback. Audio is split without truncation, cached by script and delivered as ordered chapters.

Explicit microphone interruption, typed questions, current-story context, spoken answers and chapter/position resume are implemented. Browser tests use controlled fixtures and a simulated speech recogniser; real Windows microphone behaviour and live provider editorial quality still require the user's acceptance check. There is no wake-word listener. The existing Windows updater remains compatible, with KUMAIL-named launcher aliases added.

See [the latest brief comparison](KUMAIL_GAP_REVIEW.md) for the complete outstanding autonomy, delivery, memory, research and reliability gaps. This is not the complete autonomous assistant.


## Working foundation

- Next.js responsive dashboard with permanent Ask field, source administration, explicit preference editing, research history, operations and read/verify views.
- Bearer authentication; random local bootstrap key; no hardcoded credentials; browser memory-only token.
- Approved HTTPS RSS registry, bounded retrieval, provenance, per-publisher failure handling, content-version deduplication and labelled relevance rankings.
- Four Oman-time scheduled editions, today's missed-run catch-up, durable queues, bounded retry/dead letters and redelivery IDs.
- OpenAI synthesis client with honest extractive fallback; independent ElevenLabs worker with cached private media and retry status.
- User-authorised plain-text document ingestion/deletion/export; lexical retrieval, follow-up context and stored conversations.
- Opportunity hypothesis generation from source-backed briefings when OpenAI is configured.
- Separate research/deep/news/audio worker queues, basic heartbeats, usage counts and storage totals.
- Persistent browser player with user-triggered play/pause, rewind, forward, seek and speed control.
- Conservative three-source/quotation verifier tested in isolation.

## Not complete / not production-ready

- Live OpenAI and ElevenLabs verification requires credentials. No authorised publishers were supplied. There is no live personalised news or narration acceptance result.
- Podcast discovery, book recommendations, Instagram/watchlist ingestion and their daily scheduling are not implemented. Dashboard cards report unavailable access; they are not simulations.
- Deep Dive wider retrieval, automated claim decomposition, contradiction analysis and integrated three-source corroboration are not implemented.
- No PostgreSQL service-owned credentials, Redis, S3, full event catalogue, transactional outbox, lease renewal or multi-host recovery.
- No OAuth identity provider, token encryption/rotation UI, retention policy enforcement, complete audit trail, rate limiting, budget enforcement or external security audit.
- Source registry does not yet implement publisher APIs, verified popularity feeds, columnist ranking or full geographic/credibility configuration.
- Opportunity output is a labelled narrative hypothesis report, not structured scored opportunities with save/dismiss workflows.
- PWA manifest is present; offline caching, install icons, continuous queue, playback persistence and background media controls remain incomplete.
- Automated testing covers the implemented backend foundations, not all 20 master-spec acceptance requirements. Browser failure-injection and full provider/production deployment acceptance remain outstanding.

The master specification is retained in the user's uploaded request. This implementation is an initial usable milestone and must not be represented as completion of its definition of done.
