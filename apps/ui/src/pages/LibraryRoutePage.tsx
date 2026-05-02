export function LibraryRoutePage() {
  return (
    <section aria-labelledby="page-title" className="page">
      <h1 id="page-title">Library</h1>
      <p>Unified library route for search and browsing workflows.</p>
      <label>
        Search query
        <input aria-label="Search query" />
      </label>
      <button type="button">Search</button>
      <ol aria-label="Photo gallery" />
    </section>
  );
}
