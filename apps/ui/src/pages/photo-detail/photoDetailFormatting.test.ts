import {
  MISSING_VALUE,
  formatExifAttributeValue,
  formatFilesize,
  formatGps,
  formatOptionalText,
  formatTimestamp,
} from "./photoDetailFormatting";

describe("photoDetailFormatting", () => {
  it("formats missing timestamp values as fallback", () => {
    expect(formatTimestamp(null)).toBe(MISSING_VALUE);
  });

  it("formats valid UTC timestamps", () => {
    expect(formatTimestamp("2026-03-28T19:30:00Z")).toContain("Mar");
  });

  it("formats file sizes in bytes, kilobytes, and megabytes", () => {
    expect(formatFilesize(512)).toBe("512 B");
    expect(formatFilesize(4096)).toBe("4.0 KB");
    expect(formatFilesize(2 * 1024 * 1024)).toBe("2.0 MB");
  });

  it("formats gps coordinates and fallback values", () => {
    expect(formatGps(12.3456, -45.6789)).toBe("12.3456, -45.6789");
    expect(formatGps(null, -45.6789)).toBe(MISSING_VALUE);
  });

  it("formats optional text values", () => {
    expect(formatOptionalText("Camera")).toBe("Camera");
    expect(formatOptionalText(null)).toBe(MISSING_VALUE);
    expect(formatOptionalText("   ")).toBe(MISSING_VALUE);
  });

  it("truncates long exif attribute values", () => {
    expect(formatExifAttributeValue("123456789012345678901234567890EXTRA")).toBe(
      "123456789012345678901234567890..."
    );
  });
});
