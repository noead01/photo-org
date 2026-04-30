import {
  buildLocationRadiusFilter,
  formatLocationChipLabel,
  parseLocationDraft,
  validateLocationDraft
} from "./locationFilter";

describe("locationFilter helpers", () => {
  it("parses valid drafts to numeric location state", () => {
    expect(parseLocationDraft("37.7749", "-122.4194", "12.5")).toEqual({
      latitude: 37.7749,
      longitude: -122.4194,
      radiusKm: 12.5
    });
  });

  it("returns validation error for out-of-range latitude", () => {
    const parsed = parseLocationDraft("91", "0", "10");
    expect(validateLocationDraft(parsed)).toBe("Latitude must be between -90 and 90.");
  });

  it("builds location_radius payload only when state is valid", () => {
    const valid = parseLocationDraft("37.7749", "-122.4194", "10");
    expect(buildLocationRadiusFilter(valid)).toEqual({
      latitude: 37.7749,
      longitude: -122.4194,
      radius_km: 10
    });
  });

  it("formats deterministic location chip label", () => {
    expect(
      formatLocationChipLabel({
        latitude: 37.774912,
        longitude: -122.419488,
        radiusKm: 12.54
      })
    ).toBe("location: 37.7749, -122.4195 (12.5 km)");
  });
});
