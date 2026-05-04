import {
  buildLibraryUrlQuery,
  buildSearchFilters,
  parseLibraryUrlState,
  validateDateRange
} from "./libraryRouteSearchState";

describe("libraryRouteSearchState", () => {
  it("parses certainty defaults when URL does not specify them", () => {
    const state = parseLibraryUrlState("?person=Inez");

    expect(state.personCertaintyMode).toBe("human_only");
    expect(state.suggestionConfidenceMinDraft).toBe("0.8");
    expect(state.pageSize).toBe(60);
  });

  it("serializes certainty mode and threshold into search filters", () => {
    expect(
      buildSearchFilters(
        "",
        "",
        ["inez"],
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
      personCertaintyMode: "include_suggestions",
      suggestionConfidenceMinDraft: "0.82",
      locationRadius: null,
      hasFacesFilter: null,
      pathHintFilters: [],
      page: 1,
      pageSize: 24
    });

    expect(query).toContain("personCertainty=include_suggestions");
    expect(query).toContain("suggestionMin=0.82");
    expect(query).toContain("pageSize=24");
  });

  it("validates descending date ranges", () => {
    expect(validateDateRange("2026-05-10", "2026-05-01")).toBe(
      "From date must be on or before To date."
    );
    expect(validateDateRange("2026-05-01", "2026-05-10")).toBeNull();
  });

  it("builds person filters without machine suggestion threshold for human-only mode", () => {
    expect(
      buildSearchFilters("", "", ["Inez"], "human_only", "0.95", null, null, [])
    ).toEqual({
      person_names: ["Inez"],
      person_certainty_mode: "human_only"
    });
  });

  it("returns null when no search filters are active", () => {
    expect(buildSearchFilters("", "", [], "human_only", "0.8", null, null, [])).toBeNull();
  });
});
