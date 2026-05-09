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

    expect(onOpenFace).toHaveBeenCalledWith("face-1");
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
});
