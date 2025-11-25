# Structured carousel and badge heuristics

This document describes how result badges differ from carousel eligibility and what backend signals we should expand to improve precision across schema.org types.

**Admin shortcuts:** The new controls on `ConfigSearchPage_p` let you test stricter or more permissive rules without redeploying:
- Require thumbnails and schema metadata before a card can be considered for a carousel.
- Adjust the minimum snippet length and minimum candidate count used to render a carousel strip.
- Toggle whether a relaxed fallback is allowed when strict candidates are missing.

## Badge vs. carousel
- **Badges**: continue to light up when a result is classified into a content category (schema primary type or fallback heuristics). Badges are intentionally permissive so users can spot context quickly.
- **Carousel entries**: require richer signals to avoid duplicating the same set of results. Cards are chosen only when they have a thumbnail and type-specific completeness (recipe meta, video meta, event date, etc.). If no results satisfy the strict checks, the carousel relaxes to the best available candidates but still demands a thumbnail and some metadata.

### Type-specific carousel requirements (strict pass)
- **Recipe**: schema-driven recipe type *and* at least one of cook time, servings, or difficulty pills plus a thumbnail.
- **Video**: schema-driven video type *and* duration/platform metadata plus a thumbnail.
- **Event**: schema-driven event type *and* a start/end date plus a thumbnail.
- **How-To / FAQ / Q&A / Product / Software / Article-like**: thumbnail plus a sufficiently long snippet, and ideally a schema type. Snippet-length thresholds differentiate richer guides from terse summaries.

### Relaxed fallback (when strict filters yield nothing)
- Still requires a thumbnail.
- Allows schema type alone to qualify when meta pills are missing.
- Uses shorter snippet-length thresholds for text-heavy types.

## Backend improvements to widen structured coverage
- **Schema completeness**: extract and store per-type quality flags (e.g., HowTo supplies/tools/steps count, FAQ question count, QAPage answer count, Product price/availability) so the carousel can stay strict without hiding good results.
- **Image quality**: persist image dimensions or aspect ratio to drop tiny icons from carousel eligibility.
- **Engagement hints**: capture aggregateRating/reviewCount and interactionStatistic fields for ranking carousel candidates within a type.
- **Freshness windows**: expose publish/modified timestamps for recency boosting on carousels that benefit from it (e.g., events, how-tos).
- **Domain-level overrides**: maintain a small allow/deny list for high-noise domains per schema type to reduce accidental badge triggers.

These additions keep badges broad while ensuring carousels only feature the best-structured items for each schema.
