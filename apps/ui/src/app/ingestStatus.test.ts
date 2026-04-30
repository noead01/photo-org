import { deriveIngestStatus } from "./ingestStatus";

describe("deriveIngestStatus", () => {
  it("returns complete for active and hydrated items", () => {
    const status = deriveIngestStatus({
      availabilityState: "active",
      isAvailable: true,
      hasThumbnail: true
    });

    expect(status.label).toBe("Complete");
    expect(status.tone).toBe("complete");
  });

  it("returns pending when thumbnail is missing", () => {
    const status = deriveIngestStatus({
      availabilityState: "active",
      hasThumbnail: false
    });

    expect(status.label).toBe("Pending");
    expect(status.tone).toBe("pending");
  });

  it("returns pending when detail face-detection timestamp is missing", () => {
    const status = deriveIngestStatus({
      availabilityState: "active",
      hasThumbnail: true,
      includeFaceDetection: true,
      facesDetectedTs: null
    });

    expect(status.label).toBe("Pending");
    expect(status.tone).toBe("pending");
  });

  it("returns failed when an explicit failure reason is present", () => {
    const status = deriveIngestStatus({
      availabilityState: "active",
      hasThumbnail: true,
      lastFailureReason: "folder_unmounted"
    });

    expect(status.label).toBe("Failed");
    expect(status.tone).toBe("failed");
  });

  it("returns unknown when the API returns an unrecognized availability state", () => {
    const status = deriveIngestStatus({
      availabilityState: "mystery-state",
      hasThumbnail: true
    });

    expect(status.label).toBe("Unknown");
    expect(status.tone).toBe("unknown");
    expect(status.description).toContain("mystery-state");
  });
});
