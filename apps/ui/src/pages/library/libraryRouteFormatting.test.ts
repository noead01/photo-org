import { formatFilesize, formatShotTimestamp } from "./libraryRouteFormatting";

describe("libraryRouteFormatting", () => {
  it("formats null or invalid timestamps deterministically", () => {
    expect(formatShotTimestamp(null)).toBe("Unknown capture time");
    expect(formatShotTimestamp("not-a-timestamp")).toBe("not-a-timestamp");
  });

  it("formats valid timestamps in UTC", () => {
    expect(formatShotTimestamp("2026-05-01T15:30:00Z")).toBe("May 1, 2026, 3:30 PM");
  });

  it("formats file sizes across byte, KB, and MB ranges", () => {
    expect(formatFilesize(512)).toBe("512 B");
    expect(formatFilesize(1536)).toBe("1.5 KB");
    expect(formatFilesize(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});
