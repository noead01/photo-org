# Issue 34 Text Search Design

## Summary

Issue `#34` should define a narrow, explicit Phase 3 text-search contract over cataloged photo paths and tags. The goal is not to build full ranking or natural-language interpretation, but to make `q` a predictable tokenized text clause instead of the current single-token fallback.

## Goals

- Treat `q` as a first-class text-search input over `photos.path` and `photo_tags.tag`.
- Tokenize the query into meaningful non-empty terms.
- Require every token to match somewhere across the indexed text surfaces for a photo.
- Preserve the existing sort behavior rather than introducing relevance ranking.

## Non-Goals

- Relevance scoring or ranked result ordering.
- Phrase search, quoted search, fuzzy matching, stemming, or typo tolerance.
- Searching people, geo data, or arbitrary metadata outside path and tags.
- Natural-language normalization beyond simple tokenization.

## Design Decisions

### Text search remains distinct from typed filters

The Phase 3 scenario catalog separates free-text discovery from typed filter clauses. `q` should stay a dedicated text-search field and should not absorb responsibilities that belong to `camera_make`, `date`, `has_faces`, or other typed filters.

### Search surfaces are path and tags only

For this issue, a photo matches text search if query tokens can be found in either:

- `photos.path`
- related `photo_tags.tag`

This is enough to satisfy the current seed-corpus scenarios without introducing new indexing infrastructure.

### Query terms use AND semantics across the whole query

Each non-empty token in `q` should be required. A photo matches only if every token appears somewhere across the supported text surfaces. This avoids overly broad results for multi-word queries and fits the current catalog expectation for coherent query narrowing.

### Matching stays simple and case-insensitive

Token matching should be case-insensitive substring matching for now. This keeps the implementation small and deterministic across the current SQLAlchemy-backed stack.

## Expected Request Contract

Example:

```json
{
  "q": "city break",
  "filters": {
    "extension": ["jpeg"]
  }
}
```

Semantics:

- split `q` into normalized non-empty tokens
- each token must match either the canonical photo path or a related tag
- typed filters still combine with text search using `AND`

## Test Strategy

Add or tighten coverage for:

- multiple text tokens with AND semantics
- case-insensitive token matching
- empty or whitespace-only queries behaving like no text query
- composition of text search with existing typed filters such as `extension`
- the existing seed-corpus text fixtures remaining valid

## Seed-Corpus Contract

The current fixture catalog already covers representative text-search scenarios:

- `SF01` for lake-based discovery
- `SF04` for multi-clause text plus extension filtering

`#34` should keep those green and can add another typed text fixture only if the existing catalog no longer covers the intended semantics well enough.
