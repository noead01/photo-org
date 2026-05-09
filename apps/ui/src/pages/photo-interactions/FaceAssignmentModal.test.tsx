import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FaceAssignmentModal } from "./FaceAssignmentModal";
import type { PhotoFace, PhotoSummary } from "./photoInteractionTypes";

const face: PhotoFace = {
  faceId: "face-1",
  personId: null,
  bbox: { x: 10, y: 10, width: 40, height: 40, spaceWidth: 100, spaceHeight: 100 },
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

const photo: PhotoSummary = {
  photoId: "photo-1",
  path: "/photos/lake.jpg",
  title: "lake.jpg",
  shotTs: null,
  filesize: 1,
  people: [],
  media: {
    thumbnail: { mimeType: "image/jpeg", width: 100, height: 100, dataBase64: "abc" },
    originalIntent: "detail-only",
    originalAvailability: null,
  },
  faces: [face],
  albumMembership: null,
  defaultFaceBoxesVisible: false,
};

describe("FaceAssignmentModal", () => {
  it("shows full thumbnail context independent from the underlying grid", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <FaceAssignmentModal
        isOpen
        photo={photo}
        face={face}
        people={[]}
        onClose={onClose}
        onFaceUpdated={vi.fn()}
        onFaceDismissed={vi.fn()}
        onPersonCreated={vi.fn()}
      />
    );

    expect(screen.getByRole("dialog", { name: /face assignment/i })).toBeInTheDocument();
    expect(screen.getByAltText("Preview of /photos/lake.jpg")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /close face assignment modal/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
