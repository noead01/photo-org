import { isLibraryActionConflictActive } from "./operationsActivity";

describe("operationsActivity", () => {
  it("marks conflict active when queue processing count is non-zero", () => {
    expect(
      isLibraryActionConflictActive({
        ingest_queue: { summary: { processing_count: 1 } }
      })
    ).toBe(true);

    expect(
      isLibraryActionConflictActive({
        ingest_queue: { summary: { processing_count: 0 } }
      })
    ).toBe(false);
  });

  it("returns false for malformed payloads", () => {
    expect(isLibraryActionConflictActive(null)).toBe(false);
    expect(isLibraryActionConflictActive({})).toBe(false);
    expect(isLibraryActionConflictActive({ ingest_queue: {} })).toBe(false);
    expect(
      isLibraryActionConflictActive({
        ingest_queue: { summary: { processing_count: "1" } }
      })
    ).toBe(false);
  });
});
