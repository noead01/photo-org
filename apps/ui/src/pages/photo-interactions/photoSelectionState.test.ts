import {
  createPhotoSelectionState,
  DEFAULT_PHOTO_SELECTION_STATE,
  formatPhotoSelectionScopeLabel,
  parsePhotoSelectionRouteState,
  photoSelectionReducer,
  resolvePhotoSelectionScopeCount,
  serializePhotoSelectionState,
  type PhotoSelectionState
} from "./photoSelectionState";

function buildState(
  overrides: Partial<PhotoSelectionState> = {}
): PhotoSelectionState {
  return {
    scope: overrides.scope ?? DEFAULT_PHOTO_SELECTION_STATE.scope,
    selectedPhotoIds: overrides.selectedPhotoIds ?? new Set<string>(),
    allFilteredFingerprint:
      overrides.allFilteredFingerprint ?? DEFAULT_PHOTO_SELECTION_STATE.allFilteredFingerprint
  };
}

describe("photoSelectionState", () => {
  it("keeps selected ids independent from inspector actions", () => {
    const selected = photoSelectionReducer(DEFAULT_PHOTO_SELECTION_STATE, {
      type: "togglePhotoSelection",
      photoId: "photo-1",
    });

    expect(selected.selectedPhotoIds.has("photo-1")).toBe(true);
    expect(serializePhotoSelectionState(selected)).toMatchObject({
      scope: "selected",
      selectedPhotoIds: ["photo-1"],
      allFilteredFingerprint: null,
    });
  });

  it("toggles explicit selection ids", () => {
    const state = buildState();
    const selected = photoSelectionReducer(state, {
      type: "togglePhotoSelection",
      photoId: "photo-1"
    });

    expect(selected.selectedPhotoIds.has("photo-1")).toBe(true);

    const unselected = photoSelectionReducer(selected, {
      type: "togglePhotoSelection",
      photoId: "photo-1"
    });
    expect(unselected.selectedPhotoIds.size).toBe(0);
  });

  it("switches to allFiltered and stores filter fingerprint", () => {
    const state = buildState();
    const nextState = photoSelectionReducer(state, {
      type: "setScope",
      scope: "allFiltered",
      activeFilterFingerprint: "filters:v1"
    });

    expect(nextState.scope).toBe("allFiltered");
    expect(nextState.allFilteredFingerprint).toBe("filters:v1");
  });

  it("clears allFiltered scope when filters change", () => {
    const state = buildState({
      scope: "allFiltered",
      allFilteredFingerprint: "filters:v1",
      selectedPhotoIds: new Set<string>(["photo-a"])
    });

    const nextState = photoSelectionReducer(state, {
      type: "filtersChanged",
      activeFilterFingerprint: "filters:v2"
    });

    expect(nextState.scope).toBe("selected");
    expect(nextState.allFilteredFingerprint).toBeNull();
    expect(nextState.selectedPhotoIds.has("photo-a")).toBe(true);
  });

  it("keeps allFiltered scope when sort-only context remains same fingerprint", () => {
    const state = buildState({
      scope: "allFiltered",
      allFilteredFingerprint: "filters:v1"
    });

    const nextState = photoSelectionReducer(state, {
      type: "filtersChanged",
      activeFilterFingerprint: "filters:v1"
    });

    expect(nextState).toBe(state);
  });

  it("serializes and restores route-local state", () => {
    const state = buildState({
      scope: "page",
      selectedPhotoIds: new Set<string>(["photo-b", "photo-a"]),
      allFilteredFingerprint: "ignored-when-not-allFiltered"
    });

    const serialized = serializePhotoSelectionState(state);
    expect(serialized).toEqual({
      scope: "page",
      selectedPhotoIds: ["photo-a", "photo-b"],
      allFilteredFingerprint: null
    });

    const restored = createPhotoSelectionState(serialized);
    expect(restored.scope).toBe("page");
    expect(Array.from(restored.selectedPhotoIds)).toEqual(["photo-a", "photo-b"]);
    expect(restored.allFilteredFingerprint).toBeNull();
  });

  it("parses route-local payload and rejects invalid shapes", () => {
    expect(
      parsePhotoSelectionRouteState({
        scope: "selected",
        selectedPhotoIds: ["photo-1", "photo-1", " "],
        allFilteredFingerprint: null
      })
    ).toEqual({
      scope: "selected",
      selectedPhotoIds: ["photo-1"],
      allFilteredFingerprint: null
    });

    expect(
      parsePhotoSelectionRouteState({
        scope: "bogus",
        selectedPhotoIds: [],
        allFilteredFingerprint: null
      })
    ).toBeNull();
  });

  it("resolves selection counts by active scope", () => {
    const selectedState = buildState({
      scope: "selected",
      selectedPhotoIds: new Set(["a", "b", "c"])
    });
    expect(
      resolvePhotoSelectionScopeCount(selectedState, { currentPageCount: 7, totalFilteredCount: 99 })
    ).toBe(3);

    const pageState = buildState({ scope: "page" });
    expect(
      resolvePhotoSelectionScopeCount(pageState, { currentPageCount: 7, totalFilteredCount: 99 })
    ).toBe(7);

    const allFilteredState = buildState({ scope: "allFiltered" });
    expect(
      resolvePhotoSelectionScopeCount(allFilteredState, {
        currentPageCount: 7,
        totalFilteredCount: 99
      })
    ).toBe(99);
  });

  it("formats selection scope labels", () => {
    expect(formatPhotoSelectionScopeLabel("selected")).toBe("Selected");
    expect(formatPhotoSelectionScopeLabel("page")).toBe("This page");
    expect(formatPhotoSelectionScopeLabel("allFiltered")).toBe("All filtered");
  });
});
