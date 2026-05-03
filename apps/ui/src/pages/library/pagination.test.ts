import {
  INVALID_PAGE_MESSAGE,
  updateCursorByPage
} from "./pagination";

describe("library pagination primitives", () => {
  it("keeps the deterministic invalid page messaging copy", () => {
    expect(INVALID_PAGE_MESSAGE).toBe(
      "Reset to page 1 because that page position is unavailable."
    );
  });

  it("updates page cursor map and tracks the next page cursor", () => {
    const next = updateCursorByPage({ 1: null }, 2, "cursor-page-2", "cursor-page-3");
    expect(next).toEqual({
      1: null,
      2: "cursor-page-2",
      3: "cursor-page-3"
    });
  });

  it("clears stale next page cursor when there is no following page", () => {
    const next = updateCursorByPage(
      { 1: null, 2: "cursor-page-2", 3: "stale-cursor" },
      2,
      "cursor-page-2",
      null
    );
    expect(next).toEqual({
      1: null,
      2: "cursor-page-2"
    });
  });

});
