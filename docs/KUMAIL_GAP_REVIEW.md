# KUMAIL: comparison with the new autonomous-assistant brief

The product name is **KUMAIL**. JARVIS describes the desired experience, not the application name. This review compares repository evidence with the latest supplied brief. It does not equate code in a release candidate with validation on the user's Windows computer.

## Direction

The right product is a proactive intelligence assistant with a listening interface, optional reading, controlled autonomy and persistent context. A dashboard that reads its report aloud is insufficient. The current local application is a foundation, not the completed autonomous MVP. The new brief narrows the initial scope: podcasts, books, social feeds, native mobile apps, wake-word listening, SaaS billing and elaborate agent frameworks should not consume the next milestones.

## Requirements and gaps

| Requirement | Current evidence | Gap / acceptance still needed |
|---|---|---|
| Approved sources | Source registry, RSS/Atom ingestion, per-feed failures, 33 supplied URLs in an importer; user reports sources and news working locally | Rich credibility rules, geographic expertise, access restrictions, source health history and authorised publisher APIs |
| Four Oman-time editions | Persistent scheduler, unique edition IDs, job status and retries | Requires the host to remain awake. User-editable trigger times, pause controls and broader missed-run policy are absent |
| Laptop-off operation | Docker can run the application on a host | No always-on Linux host has been deployed. A Windows laptop that is off cannot perform the work |
| Email delivery | None | Approved mail provider, destination, delivery queue, retries and acceptance test |
| Windows / Android delivery | No push implementation | Web Push or ntfy, explicit permissions, actionable links, offline handling and delivery history. The manifest alone is not a push/PWA implementation |
| Short natural audio | ElevenLabs works according to user feedback; release candidate introduces separate scripts, chapters and duration targets | Live evaluation of naturalness, completeness and duration with the user's sources and voice. Fixed ten minutes must not encourage filler |
| Voice conversation | Release candidate adds explicit microphone interruption, current-story context, spoken answers and position-preserving resume | Real-device microphone and latency validation. Always-listening and acoustic barge-in are not claimed or required for this MVP |
| High-signal selection | Explicit-interest keyword score, content-version deduplication; the all-source release takes three candidates per enabled feed and adds validated AI-assisted event grouping | Semantic topic clustering, significance scoring, publisher authority weighting, story timelines and explicit changes since prior editions |
| Content depth | Current collection uses publisher feed excerpts | Substantive longer editions need sufficient authorised article/API content. Thin RSS evidence must not be inflated to meet a listening target |
| Source verification | Provenance is retained; conservative quotation/independence verifier exists and is tested | Verifier is not an integrated research pipeline. Publisher attribution is not independent verification |
| Deep Dive | Approved stored-evidence retrieval and conversation history; release candidate binds a selected story | No authorised wider-web search, claim decomposition, primary-record lookup, contradiction resolution or automated three-independent-source corroboration |
| Preference memory | Explicit flat interests, persistent history and separate bounded inferred topic adjustments | Hierarchical topic relationships, separate short-/long-term models and time-limited follows/exclusions; basic repeated-signal weighting and decay now exist |
| Interaction feedback | Question/replay/seek/skip/completion events now persist; bounded topic adjustments require multiple articles and decay over time | Save/dismiss semantics, richer explicit feedback and hierarchical scoring remain incomplete; basic inference now has review, opt-out and reset controls. Dismissal must not automatically mean disinterest |
| Persistence / modularity | Service processes, separate queues, per-domain SQLite files, private audio volume | PostgreSQL migration and service-owned credentials; current shared files remain a single-host boundary and failure point |
| Reliability | Bounded retries, dead-letter state, leased jobs and heartbeat data; release candidate renews long-running leases | End-to-end soak/failure-injection coverage, operational alerting, restore drills and measured 99% success target |
| Costs | Token/character counts and storage totals | Actual configured prices, budget caps, per-day limits and enforced stopping behaviour |
| Privacy / control | Authenticated private APIs/audio, environment-based secrets, source restrictions, document deletion/export | Complete audit trail, retention policy enforcement, encrypted credential storage/rotation, remote HTTPS deployment and security review |
| Email drafting agent | Not implemented | Separate later agent: authorised mailbox access, draft-only workflow and explicit approval before sending |
| Productisation | Not implemented | Correctly deferred until private utility is proven; tenant isolation, licensing and billing are not initial work |

## Priority order

1. **Finish the listening correction already requested.** Separate spoken scripts from evidence; make Play, interrupt/question and resume the primary journey. Keep reading optional. Validate with actual sources and the chosen voice.
2. **Deliver genuine autonomy.** Deploy to an approved always-on Linux host, then add reliable email delivery and execution monitoring. This is the largest difference between the running local app and Phase 1's acceptance condition.
3. **Add story intelligence and controlled memory.** Story clusters and change history, source authority, explicit feedback and hierarchical interest scoring with decay. Protect essential global coverage from over-personalisation.
4. **Connect real Deep Dive research.** Licensed search/retrieval, primary documents, independence checks, contradictions and honest claim labels. Preserve partial evidence without inventing three confirmations.
5. **Add permissioned device delivery.** Windows and Android notifications with Listen, Read and Ask actions; expand actions after delivery reliability is proven.
6. **Introduce the separate email drafting agent**, then assess commercial packaging only after personal utility is measured.

The supplied brief sequences autonomy before advanced voice. The user's immediate correction makes the current listening repair urgent; it should remain a bounded milestone rather than displace the missing autonomy work.

## Decisions and prerequisites outside code

Always-on operation needs a hosting location and authorisation for any charges. Email delivery needs an approved account/provider and recipient configuration. Deep Dive needs an authorised retrieval provider. Android and Windows notifications need user permissions and an appropriate secure deployment. None of these should be represented as functioning simply because an interface or configuration field exists.

No provider credentials belong in this document, source control or chat. Email sending to the owner for briefings must be explicitly authorised/configured. The future email agent may create drafts, but must not send replies without approval.

## Definition of the next successful milestone

The user opens KUMAIL, presses Play, hears a concise natural edition without citation hashes or report headings, interrupts to ask about the current story, hears an evidence-bounded answer and resumes at the saved position. The system gives a shorter edition when evidence is thin. The written record remains inspectable. New scheduled content never starts playback on its own.

This milestone does **not** satisfy laptop-off delivery, adaptive learning, broader-web verification or the complete new brief. Those remain explicit subsequent acceptance gates.
