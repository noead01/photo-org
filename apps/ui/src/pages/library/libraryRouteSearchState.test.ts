import {
  buildLibraryUrlQuery,
  buildSearchFilters,
  parseLibraryUrlState
} from "./libraryRouteSearchState";

describe("libraryRouteSearchState", () => {
  it("parses certainty defaults when URL does not specify them", () => {
    const state = parseLibraryUrlState("?person=Inez");

    expect(state.personCertaintyMode).toBe("human_only");
    expect(state.suggestionConfidenceMinDraft).toBe("0.8");
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
      page: 1
    });

    expect(query).toContain("personCertainty=include_suggestions");
    expect(query).toContain("suggestionMin=0.82");
  });
});
