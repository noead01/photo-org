import {
  dedupeTrimmedValues,
  parseNullableBooleanParam,
  parsePositiveIntParam
} from "./urlSerialization";

describe("library URL serialization helpers", () => {
  it("dedupes and trims non-empty values while preserving order", () => {
    expect(dedupeTrimmedValues(["  lake ", "", "lake", "coast", " coast "])).toEqual([
      "lake",
      "coast"
    ]);
  });

  it("parses positive int params from URL search strings", () => {
    expect(parsePositiveIntParam("?page=3", "page")).toBe(3);
    expect(parsePositiveIntParam("?page=0", "page")).toBe(1);
    expect(parsePositiveIntParam("?page=abc", "page")).toBe(1);
    expect(parsePositiveIntParam("", "page")).toBe(1);
  });

  it("parses nullable booleans from query values", () => {
    expect(parseNullableBooleanParam("true")).toBe(true);
    expect(parseNullableBooleanParam("false")).toBe(false);
    expect(parseNullableBooleanParam("  true ")).toBe(true);
    expect(parseNullableBooleanParam("")).toBeNull();
    expect(parseNullableBooleanParam(null)).toBeNull();
    expect(parseNullableBooleanParam("nope")).toBeNull();
  });
});
