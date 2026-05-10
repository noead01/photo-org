import { describe, expect, it } from "vitest";
import { buildFaceActionSummary, resolveFaceConfidenceIndicator } from "./faceActionSummary";
import type { PhotoFace } from "./photoInteractionTypes";

function buildFace(overrides: Partial<PhotoFace> = {}): PhotoFace {
  return {
    faceId: "face-1",
    personId: null,
    assignedPerson: null,
    bbox: { x: 0.1, y: 0.1, width: 0.2, height: 0.2, spaceWidth: 1, spaceHeight: 1 },
    labelSource: null,
    confidence: null,
    modelVersion: null,
    provenance: null,
    labelRecordedTs: null,
    suggestions: [],
    canAssign: true,
    canCorrect: false,
    canDismiss: true,
    canConfirm: false,
    ...overrides
  };
}

describe("buildFaceActionSummary", () => {
  it("formats the top suggestion name for unassigned faces", () => {
    const summary = buildFaceActionSummary(
      buildFace({
        suggestions: [
          { personId: "person-2", displayName: "Blair", rank: 2, confidence: 0.71, modelVersion: null, provenance: null },
          { personId: "person-1", displayName: "Alex", rank: 1, confidence: 0.89, modelVersion: null, provenance: null }
        ]
      })
    );

    expect(summary).toBe("Alex");
  });

  it("formats assigned faces with resolved display names", () => {
    const summary = buildFaceActionSummary(
      buildFace({
        personId: "person-1",
        labelSource: "machine_suggested",
        confidence: 0.93,
        suggestions: [
          { personId: "person-1", displayName: "Alex", rank: 1, confidence: 0.93, modelVersion: null, provenance: null }
        ]
      })
    );

    expect(summary).toBe("Alex");
  });

  it("returns person id for human-confirmed assignments when display name is unavailable", () => {
    const summary = buildFaceActionSummary(
      buildFace({
        personId: "person-1",
        labelSource: "human_confirmed"
      })
    );

    expect(summary).toBe("person-1");
  });

  it("returns no label text for unknown-person assignments", () => {
    const summary = buildFaceActionSummary(
      buildFace({
        personId: "unknown-person",
        assignedPerson: { personId: "unknown-person", displayName: "Unknown person" }
      })
    );

    expect(summary).toBeNull();
  });
});

describe("resolveFaceConfidenceIndicator", () => {
  it("returns unknown for unknown-person assignments", () => {
    const indicator = resolveFaceConfidenceIndicator(
      buildFace({
        personId: "unknown-person",
        assignedPerson: { personId: "unknown-person", displayName: "Unknown person" }
      })
    );

    expect(indicator).toBe("unknown");
  });

  it("returns assigned for known assignments", () => {
    const indicator = resolveFaceConfidenceIndicator(
      buildFace({
        personId: "person-1",
        assignedPerson: { personId: "person-1", displayName: "Alex" }
      })
    );

    expect(indicator).toBe("assigned");
  });

  it("maps top-suggestion confidence to battery levels", () => {
    expect(
      resolveFaceConfidenceIndicator(
        buildFace({
          suggestions: [{ personId: "person-a", displayName: "A", rank: 1, confidence: 0.39, modelVersion: null, provenance: null }]
        })
      )
    ).toBe("empty");
    expect(
      resolveFaceConfidenceIndicator(
        buildFace({
          suggestions: [{ personId: "person-a", displayName: "A", rank: 1, confidence: 0.5, modelVersion: null, provenance: null }]
        })
      )
    ).toBe("low");
    expect(
      resolveFaceConfidenceIndicator(
        buildFace({
          suggestions: [{ personId: "person-a", displayName: "A", rank: 1, confidence: 0.7, modelVersion: null, provenance: null }]
        })
      )
    ).toBe("medium");
    expect(
      resolveFaceConfidenceIndicator(
        buildFace({
          suggestions: [{ personId: "person-a", displayName: "A", rank: 1, confidence: 0.9, modelVersion: null, provenance: null }]
        })
      )
    ).toBe("strong");
  });
});
