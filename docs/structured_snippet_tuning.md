# Tuning badge and carousel eligibility

This quick guide explains where to tighten or relax structured-snippet eligibility in YaCy’s modern search UI.

**UI controls:** Administrators can now tune these switches without touching code on `ConfigSearchPage_p`:
- Allow or disable heuristic badges when no schema.org type is present (`search.result.badge.allowHeuristics`).
- Require thumbnails and/or schema metadata before a result can enter the carousel (`search.result.carousel.requireThumbnail`, `search.result.carousel.requireSchema`).
- Toggle relaxed fallback, snippet-length threshold, and the minimum number of cards needed to render a carousel (`search.result.carousel.allowRelaxedFallback`, `search.result.carousel.minSnippetLength`, `search.result.carousel.minResults`).

## Badges (result-level labels)
Badges render whenever a result is classified into a `contentCategory`. To change what counts as a recipe/video/how-to/etc.:

1. **Adjust schema/heuristic mapping** in `source/net/yacy/htroot/yacysearchitem.java` where `contentCategory` is derived. This is the switch that sets `content_isRecipe`, `content_isHowTo`, `content_isFaq`, etc., which drive the badge blocks in `htroot/yacysearchitem.html`.
2. Keep badges permissive: broaden or narrow type detection here without affecting carousel inclusion. For example, require a schema type before setting `contentCategory = "recipe"` if you want only structured recipes to receive the recipe badge.

Relevant code:
- Category detection and badge flags: `source/net/yacy/htroot/yacysearchitem.java` around the `contentCategory` setters and `content_is*` puts.
- Badge markup: `htroot/yacysearchitem.html` top-of-card badge blocks.

## Carousel eligibility (stricter)
Carousels reuse the same results but gate entries on richer signals. To tune the rules:

1. **Data flags emitted per result**: `htroot/yacysearchitem.html` attaches `data-has-thumbnail`, `data-has-schema`, `data-has-recipe-meta`, `data-has-video-meta`, `data-has-event-date`, and `data-snippet-length` to each `<article>`.
2. **Selection logic**: `htroot/yacysearch.html` `filterCandidates()` uses those flags per type. Edit the strict/relaxed branches to change requirements—e.g., raise `snippetThreshold`, demand schema for more types, or require additional meta flags.
3. **Type list**: In the same file, `typeConfigs` controls which schema types can drive a carousel (recipes, videos, how-tos, products, software, FAQ, Q&A, events). Add/remove types or swap icons/labels here.

### Examples
- Require schema for all text-based carousels: in `filterCandidates`, change the default branch to `return hasThumb && snippetLength >= snippetThreshold && hasSchema;` for both strict and relaxed paths.
- Make recipes stricter: add `hasRecipeMeta && hasSchema` to both branches so missing cook time/servings drop out of the carousel without affecting the recipe badge.
- Reduce duplication: increase `snippetThreshold` for relaxed candidates so only fuller snippets can enter a carousel when strict picks are empty.

## Ranking boosts (pre-RWI)
Structured results can also be prioritized via YaCy’s RWI ranking boosts without changing badge or carousel rules:

- Open **Ranking › RankingRWI** (`/RankingRWI_p.html`) and add boost entries for schema fields, such as `schema_org_primary_type_s:10` to favor any structured result or `schema_org_types_sxt:8` to favor documents declaring rich types.
- Combine with type-specific boosts (for example, `recipe_total_time_s:4` or `recipe_rating_d:3`) to surface richer recipes ahead of bare links.
- These boosts adjust result ordering only; eligibility for badges and carousels still follows the heuristics above, so you can promote structured hits without overpopulating carousels.

## Recrawl considerations
Badges and carousels depend on stored schema fields (`hasSchema`, recipe/video/event metadata). After tightening rules, previously indexed documents without those fields may lose eligibility. A recrawl repopulates the new fields so stricter checks still find candidates.
