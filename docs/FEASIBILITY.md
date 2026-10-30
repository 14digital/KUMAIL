# Integration feasibility and access limits

This report distinguishes implemented protocol clients from end-to-end account verification. No provider credentials were supplied, so **none of the paid or account integrations has been live-verified**. Prices and account eligibility must be checked before deployment; no subscriptions are assumed.

| Capability | Implemented / access needed | Limits and authoritative reference |
|---|---|---|
| Publisher RSS | Implemented; user approves each endpoint/domain | Feed access is not permission to republish full articles. Only available feed content is processed. No paywall bypass. Publisher terms must be reviewed per source. |
| OpenAI | Responses API HTTP client; API key and model access | [Responses API](https://platform.openai.com/docs/api-reference/responses). Usage tokens recorded, not invented currency charges. Provider failure falls back to attributed excerpts. |
| ElevenLabs | Text-to-speech HTTP client; key and authorised voice ID | [Text to speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert). Voice subscription limits and terms apply. Not live-tested. |
| YouTube | Not connected or implemented | [YouTube Data API](https://developers.google.com/youtube/v3). Metadata discovery needs project credentials/quota. Caption download requires appropriate OAuth ownership/permission; arbitrary public-video transcripts are not assumed accessible. No audio downloading. |
| Audible | No account integration | No general consumer-library public API is assumed. Use authorised app links only until an approved partner mechanism is established. No DRM bypass or daily-free-book assumption. |
| Blinkist | No account integration | Partner/account permissions must be established directly. No private API scraping or proprietary-summary narration. |
| Instagram | No feed integration | [Instagram platform](https://developers.facebook.com/docs/instagram-platform/). Do not assume personal following-feed access. A watchlist is a future user-managed input, not evidence of retrieved updates. |
| Wider-web research | Not implemented | Needs a licensed search/retrieval provider, destination permissions and independent-source review. Selecting Deep Dive currently returns approved-source evidence with an explicit wider-search limitation. |
| Microphone | Browser recognition where supported | Browser vendor permissions and processing apply; text input remains available. No separate speech-to-text provider has been configured. |

The references above identify the authoritative integration documentation; contractual eligibility and current pricing are not confirmed merely by linking them. No scraping workaround is implemented.

## Cost model

No fabricated monthly bill is shown. Estimate using your actual contracted rates:

- OpenAI: `(input tokens × input rate + output tokens × output rate) / 1,000,000`.
- Narration: billed characters or provider credits at the selected plan's rate; four daily editions can be a significant component.
- Storage: accumulated audio bytes × storage rate; the MVP uses a local volume, not S3.
- Hosting: one private host plus encrypted backups and an HTTPS endpoint.

A 30-day baseline schedules 120 news editions. Actual cost depends on feed volume, script length, model, voice and on-demand research. The operations API records tokens/characters and reports unknown currency costs as unknown. Monthly budget enforcement, pricing configuration and S3 lifecycle policies remain unimplemented.
