import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { PhotoSurface } from "./PhotoSurface";
import type { PhotoSummary } from "./photoInteractionTypes";

const photo: PhotoSummary = {
  photoId: "photo-1",
  path: "/photos/lake.jpg",
  title: "lake.jpg",
  shotTs: null,
  filesize: 123,
  people: [],
  media: {
    thumbnail: {
      mimeType: "image/jpeg",
      width: 100,
      height: 80,
      dataBase64: "abc",
    },
    originalIntent: "detail-only",
    originalAvailability: null,
  },
  faces: [],
  albumMembership: null,
  defaultFaceBoxesVisible: false,
};

describe("PhotoSurface", () => {
  it("keeps selection, metadata, and detail navigation separate", async () => {
    const user = userEvent.setup();
    const onToggleSelected = vi.fn();
    const onOpenMetadata = vi.fn();

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <PhotoSurface
          photo={photo}
          selected={false}
          faceBoxesVisible={false}
          activeMetadata={false}
          detailTo="/library/photo-1"
          onToggleSelected={onToggleSelected}
          onOpenMetadata={onOpenMetadata}
          onOpenFace={vi.fn()}
        />
      </MemoryRouter>
    );

    await user.click(screen.getByRole("checkbox", { name: /select photo lake.jpg/i }));
    expect(onToggleSelected).toHaveBeenCalledWith("photo-1");
    expect(onOpenMetadata).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /show metadata for lake.jpg/i }));
    expect(onOpenMetadata).toHaveBeenCalledWith("photo-1", "photo-surface-photo-1");
    expect(onToggleSelected).toHaveBeenCalledTimes(1);

    expect(screen.getByRole("link", { name: /open details for lake.jpg/i })).toHaveAttribute(
      "href",
      "/library/photo-1"
    );
  });

  it("marks the active metadata source", () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <PhotoSurface
          photo={photo}
          selected={false}
          faceBoxesVisible={false}
          activeMetadata
          detailTo="/library/photo-1"
          onToggleSelected={vi.fn()}
          onOpenMetadata={vi.fn()}
          onOpenFace={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByTestId("photo-surface-photo-1")).toHaveClass("photo-surface-active-metadata");
  });
});
