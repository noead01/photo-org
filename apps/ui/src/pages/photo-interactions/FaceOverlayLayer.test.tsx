import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FaceOverlayLayer } from "./FaceOverlayLayer";
import type { PhotoFace } from "./photoInteractionTypes";

const face: PhotoFace = {
  faceId: "face-1",
  personId: null,
  bbox: { x: 10, y: 10, width: 20, height: 20, spaceWidth: 100, spaceHeight: 100 },
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
};

const faceWithoutBBox: PhotoFace = {
  ...face,
  faceId: "face-2",
  bbox: { x: null, y: null, width: null, height: null, spaceWidth: null, spaceHeight: null },
};

describe("FaceOverlayLayer", () => {
  it("renders face controls and delegates face clicks", async () => {
    const user = userEvent.setup();
    const onOpenFace = vi.fn();

    render(
      <FaceOverlayLayer
        faces={[face]}
        thumbnailSize={{ width: 100, height: 100 }}
        visible
        onOpenFace={onOpenFace}
      />
    );

    await user.click(screen.getByRole("button", { name: /open face 1 actions/i }));

    expect(onOpenFace).toHaveBeenCalledWith("face-1", 0);
  });

  it("renders nothing when face boxes are hidden", () => {
    render(
      <FaceOverlayLayer
        faces={[face]}
        thumbnailSize={{ width: 100, height: 100 }}
        visible={false}
        onOpenFace={vi.fn()}
      />
    );

    expect(screen.queryByRole("button", { name: /open face/i })).toBeNull();
  });

  it("renders fallback face controls when region coordinates are unavailable", async () => {
    const user = userEvent.setup();
    const onOpenFace = vi.fn();

    render(
      <FaceOverlayLayer
        faces={[faceWithoutBBox]}
        thumbnailSize={{ width: 100, height: 100 }}
        visible
        onOpenFace={onOpenFace}
      />
    );

    await user.click(screen.getByRole("button", { name: /open face 1 actions/i }));
    expect(onOpenFace).toHaveBeenCalledWith("face-2", 0);
  });

  it("shows question-mark indicator without name text for unknown assignments", () => {
    render(
      <FaceOverlayLayer
        faces={[
          {
            ...face,
            personId: "unknown-person",
            assignedPerson: { personId: "unknown-person", displayName: "Unknown person" }
          }
        ]}
        thumbnailSize={{ width: 100, height: 100 }}
        visible
        onOpenFace={vi.fn()}
      />
    );

    expect(screen.queryByText("Unknown person")).not.toBeInTheDocument();
    expect(screen.getByText("?")).toBeInTheDocument();
  });

  it("renders 0 to 3 battery blocks for empty, low, medium, and strong suggestion confidence", () => {
    render(
      <FaceOverlayLayer
        faces={[
          {
            ...face,
            faceId: "face-empty",
            suggestions: [{ personId: "person-1", displayName: "Alex", rank: 1, confidence: 0.39, modelVersion: null, provenance: null }]
          },
          {
            ...face,
            faceId: "face-low",
            suggestions: [{ personId: "person-1", displayName: "Alex", rank: 1, confidence: 0.5, modelVersion: null, provenance: null }]
          },
          {
            ...face,
            faceId: "face-medium",
            suggestions: [{ personId: "person-1", displayName: "Alex", rank: 1, confidence: 0.7, modelVersion: null, provenance: null }]
          },
          {
            ...face,
            faceId: "face-strong",
            suggestions: [{ personId: "person-1", displayName: "Alex", rank: 1, confidence: 0.9, modelVersion: null, provenance: null }]
          }
        ]}
        thumbnailSize={{ width: 100, height: 100 }}
        visible
        onOpenFace={vi.fn()}
      />
    );

    const indicators = Array.from(
      document.querySelectorAll<HTMLElement>(".photo-face-confidence-indicator.is-battery")
    );
    expect(indicators).toHaveLength(4);

    const filledCounts = indicators.map((indicator) =>
      indicator.querySelectorAll(".photo-face-battery-cell.is-filled").length
    );
    expect(filledCounts).toEqual([0, 1, 2, 3]);
  });
});
