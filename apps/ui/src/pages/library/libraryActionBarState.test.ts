import { resolveLibraryActionState } from "./libraryActionBarState";

describe("libraryActionBarState", () => {
  it("enables both actions when selection, permissions, and conflict state allow it", () => {
    const state = resolveLibraryActionState({
      selectionCount: 3,
      canAddToAlbum: true,
      canExport: true,
      hasConflictingJob: false
    });

    expect(state.addToAlbum).toEqual({ enabled: true, reason: null });
    expect(state.export).toEqual({ enabled: true, reason: null });
  });

  it("disables actions when no selection scope is active", () => {
    const state = resolveLibraryActionState({
      selectionCount: 0,
      canAddToAlbum: true,
      canExport: true,
      hasConflictingJob: false
    });

    expect(state.addToAlbum.enabled).toBe(false);
    expect(state.addToAlbum.reason).toBe("No selection scope active.");
    expect(state.export.enabled).toBe(false);
    expect(state.export.reason).toBe("No selection scope active.");
  });

  it("disables action when permission is missing even with active selection", () => {
    const state = resolveLibraryActionState({
      selectionCount: 3,
      canAddToAlbum: false,
      canExport: true,
      hasConflictingJob: false
    });

    expect(state.addToAlbum.enabled).toBe(false);
    expect(state.addToAlbum.reason).toBe("You do not have permission for this action.");
    expect(state.export.enabled).toBe(true);
    expect(state.export.reason).toBeNull();
  });

  it("disables both actions when conflicting ingest processing is active", () => {
    const state = resolveLibraryActionState({
      selectionCount: 2,
      canAddToAlbum: true,
      canExport: true,
      hasConflictingJob: true
    });

    expect(state.addToAlbum.enabled).toBe(false);
    expect(state.addToAlbum.reason).toBe(
      "Action temporarily unavailable while ingest processing is active."
    );
    expect(state.export.enabled).toBe(false);
    expect(state.export.reason).toBe(
      "Action temporarily unavailable while ingest processing is active."
    );
  });
});
