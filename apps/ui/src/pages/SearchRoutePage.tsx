import { FormEvent, useMemo, useState } from "react";

type SearchPhoto = {
  photo_id: string;
  path: string;
  ext: string;
  shot_ts: string | null;
  filesize: number;
};

type SearchResponsePayload = {
  hits: {
    total: number;
    cursor: string | null;
    items: SearchPhoto[];
  };
};

const DEFAULT_SORT = { by: "shot_ts", dir: "desc" } as const;
const DEFAULT_PAGE = { limit: 24, cursor: null } as const;

async function fetchSearchResults(query: string): Promise<SearchResponsePayload> {
  const response = await fetch("/api/v1/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      q: query,
      sort: DEFAULT_SORT,
      page: DEFAULT_PAGE
    })
  });

  if (!response.ok) {
    throw new Error(`Search request failed (${response.status})`);
  }

  return (await response.json()) as SearchResponsePayload;
}

export function SearchRoutePage() {
  const [draftQuery, setDraftQuery] = useState("");
  const [queryChips, setQueryChips] = useState<string[]>([]);
  const [results, setResults] = useState<SearchPhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasRequested, setHasRequested] = useState(false);

  const serializedQuery = useMemo(() => queryChips.join(" "), [queryChips]);

  async function runSearch(chips: string[]) {
    setIsLoading(true);
    setError(null);
    setHasRequested(true);

    try {
      const payload = await fetchSearchResults(chips.join(" "));
      setResults(payload.hits.items);
      setTotalCount(payload.hits.total);
    } catch (caughtError: unknown) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load search results.";
      setError(message);
      setResults([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = draftQuery.trim();
    if (!trimmed) {
      return;
    }

    const nextChips = [...queryChips, trimmed];
    setQueryChips(nextChips);
    setDraftQuery("");
    void runSearch(nextChips);
  }

  function handleDismissChip(indexToRemove: number) {
    const nextChips = queryChips.filter((_, index) => index !== indexToRemove);
    setQueryChips(nextChips);
    void runSearch(nextChips);
  }

  function handleRetry() {
    void runSearch(queryChips);
  }

  const summaryLabel = useMemo(() => {
    if (isLoading) {
      return "Loading search workflow.";
    }

    if (error) {
      return "Search results unavailable.";
    }

    if (!hasRequested) {
      return "Submit a phrase to search the catalog.";
    }

    return `Showing ${results.length} of ${totalCount} photos`;
  }, [error, hasRequested, isLoading, results.length, totalCount]);

  return (
    <section aria-labelledby="page-title" className="page search-page">
      <div>
        <h1 id="page-title">Search</h1>
        <p>Tokenized phrase chips with deterministic submit and reset behavior.</p>
      </div>

      <form className="search-query-form" onSubmit={handleSubmit}>
        <label htmlFor="search-query-input">Search query</label>
        <div className="search-query-row">
          <input
            id="search-query-input"
            type="text"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            aria-describedby="search-query-summary"
          />
          <button type="submit">Search</button>
        </div>
      </form>

      {queryChips.length > 0 ? (
        <ul className="search-chip-list" aria-label="Active query filters">
          {queryChips.map((chip, index) => (
            <li key={`${chip}-${index}`}>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove query ${chip}`}
                onClick={() => handleDismissChip(index)}
              >
                {chip}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <p id="search-query-summary" className="search-summary" aria-live="polite">
        {summaryLabel}
      </p>

      {isLoading ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading search workflow.
        </div>
      ) : null}

      {error ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load Search</h2>
          <p>{error}</p>
          <button type="button" onClick={handleRetry}>
            Retry
          </button>
        </div>
      ) : null}

      {!error && !isLoading && hasRequested && results.length === 0 ? (
        <div className="feedback-panel">
          <p>No matching photos for the active query.</p>
        </div>
      ) : null}

      {!error && !isLoading && results.length > 0 ? (
        <ol className="search-results" aria-label="Search results">
          {results.map((photo) => (
            <li key={photo.photo_id}>
              <h2>{photo.photo_id}</h2>
              <p className="search-result-path" title={photo.path}>
                {photo.path}
              </p>
            </li>
          ))}
        </ol>
      ) : null}

      <p className="search-serialized-query" aria-live="off">
        Active query: {serializedQuery || "(none)"}
      </p>
    </section>
  );
}
