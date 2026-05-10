import {
  buildLibraryUrlQuery,
  buildSearchFilters,
  parseLibraryUrlState,
  resolvePersonCertaintyPercent,
  validateDateRange
} from "./libraryRouteSearchState";

describe("libraryRouteSearchState", () => {
  it("parses certainty defaults when URL does not specify them", () => {
    const state = parseLibraryUrlState("?person=Inez");

    expect(state.personCertaintyMode).toBe("human_only");
    expect(state.suggestionConfidenceMinDraft).toBe("0.8");
    expect(state.pageSize).toBe(60);
    expect(state.sortDirection).toBe("desc");
  });

  it("serializes certainty mode and threshold into search filters", () => {
    expect(
      buildSearchFilters(
        "",
        "",
        ["inez"],
        [],
        "include_suggestions",
        "0.8",
        null,
        null,
        []
      )
    ).toEqual({
      person_names: ["inez"],
      person_certainty_mode: "include_suggestions",
      suggestion_confidence_min: 0.8
    });
  });

  it("persists certainty fields in library URL query", () => {
    const query = buildLibraryUrlQuery({
      queryChips: [],
      fromDate: "",
      toDate: "",
      selectedPersonNames: ["Inez"],
      selectedAlbumIds: [],
      personCertaintyMode: "include_suggestions",
      suggestionConfidenceMinDraft: "0.82",
      locationRadius: null,
      hasFacesFilter: null,
      pathHintFilters: [],
      page: 1,
      pageSize: 24,
      sortDirection: "asc"
    });

    expect(query).toContain("personCertainty=include_suggestions");
    expect(query).toContain("suggestionMin=0.82");
    expect(query).toContain("pageSize=24");
    expect(query).toContain("sort=asc");
  });

  it("persists certainty fields in URL query even before selecting people", () => {
    const query = buildLibraryUrlQuery({
      queryChips: [],
      fromDate: "",
      toDate: "",
      selectedPersonNames: [],
      selectedAlbumIds: [],
      personCertaintyMode: "include_suggestions",
      suggestionConfidenceMinDraft: "0.91",
      locationRadius: null,
      hasFacesFilter: null,
      pathHintFilters: [],
      page: 1,
      pageSize: 60,
      sortDirection: "desc"
    });

    expect(query).toContain("personCertainty=include_suggestions");
    expect(query).toContain("suggestionMin=0.91");
  });

  it("validates descending date ranges", () => {
    expect(validateDateRange("2026-05-10", "2026-05-01")).toBe(
      "From date must be on or before To date."
    );
    expect(validateDateRange("2026-05-01", "2026-05-10")).toBeNull();
  });

  it("builds person filters without machine suggestion threshold for human-only mode", () => {
    expect(
      buildSearchFilters("", "", ["Inez"], [], "human_only", "0.95", null, null, [])
    ).toEqual({
      person_names: ["Inez"],
      person_certainty_mode: "human_only"
    });
  });

  it("resolves person certainty percent for each certainty mode", () => {
    expect(resolvePersonCertaintyPercent("human_only", "0.25")).toBe(100);
    expect(resolvePersonCertaintyPercent("include_suggestions", "0.91")).toBe(91);
    expect(resolvePersonCertaintyPercent("include_suggestions", "not-a-number")).toBe(80);
  });

  it("returns null when no search filters are active", () => {
    expect(buildSearchFilters("", "", [], [], "human_only", "0.8", null, null, [])).toBeNull();
  });

  it("parses and serializes album filters in URL and search payload", () => {
    const state = parseLibraryUrlState("?album=album-1&album=album-2");
    expect(state.selectedAlbumIds).toEqual(["album-1", "album-2"]);

    const query = buildLibraryUrlQuery({
      queryChips: [],
      fromDate: "",
      toDate: "",
      selectedPersonNames: [],
      selectedAlbumIds: ["album-1"],
      personCertaintyMode: "human_only",
      suggestionConfidenceMinDraft: "0.8",
      locationRadius: null,
      hasFacesFilter: null,
      pathHintFilters: [],
      page: 1,
      pageSize: 60,
      sortDirection: "desc"
    });
    expect(query).toContain("album=album-1");

    expect(buildSearchFilters("", "", [], ["album-1"], "human_only", "0.8", null, null, [])).toEqual({
      album_ids: ["album-1"]
    });
  });

  it("parses and serializes faces filter params", () => {
    const state = parseLibraryUrlState(
      "?facesMin=2&facesMax=7&facesCertMin=60&facesCertMax=95&facesUnknown=1"
    );
    expect(state.facesFilter).toEqual({
      minCount: 2,
      maxCount: 7,
      certaintyMinPct: 60,
      certaintyMaxPct: 95,
      hasUnknownPerson: true
    });

    const query = buildLibraryUrlQuery({
      queryChips: [],
      fromDate: "",
      toDate: "",
      selectedPersonNames: [],
      selectedAlbumIds: [],
      personCertaintyMode: "human_only",
      suggestionConfidenceMinDraft: "0.8",
      locationRadius: null,
      hasFacesFilter: null,
      pathHintFilters: [],
      facesFilter: state.facesFilter,
      page: 1,
      pageSize: 60,
      sortDirection: "desc"
    });

    expect(query).toContain("facesMin=2");
    expect(query).toContain("facesMax=7");
    expect(query).toContain("facesCertMin=60");
    expect(query).toContain("facesCertMax=95");
    expect(query).toContain("facesUnknown=1");
  });

  it("omits faces count defaults 0..infinity in URL and payload", () => {
    const query = buildLibraryUrlQuery({
      queryChips: [],
      fromDate: "",
      toDate: "",
      selectedPersonNames: [],
      selectedAlbumIds: [],
      personCertaintyMode: "human_only",
      suggestionConfidenceMinDraft: "0.8",
      locationRadius: null,
      hasFacesFilter: null,
      pathHintFilters: [],
      facesFilter: {
        minCount: 0,
        maxCount: null,
        certaintyMinPct: 0,
        certaintyMaxPct: 100,
        hasUnknownPerson: false
      },
      page: 1,
      pageSize: 60,
      sortDirection: "desc"
    });
    expect(query).not.toContain("facesMin=");
    expect(query).not.toContain("facesMax=");
  });

  it("omits face-attribute clauses when range is 0..0", () => {
    const filters = buildSearchFilters("", "", [], [], "human_only", "0.8", null, null, [], {
      minCount: 0,
      maxCount: 0,
      certaintyMinPct: 65,
      certaintyMaxPct: 95,
      hasUnknownPerson: true
    });
    expect(filters?.faces).toEqual({ min_count: 0, max_count: 0 });
  });
});
