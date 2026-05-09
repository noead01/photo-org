import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AlbumActionSurface } from "./AlbumActionSurface";
import type { AlbumTarget } from "./photoInteractionTypes";

const albums: AlbumTarget[] = [
  { albumId: "album-1", name: "Family", kind: "manual", canAcceptManualAdditions: true },
  { albumId: "album-2", name: "Saved filter", kind: "saved_filter", canAcceptManualAdditions: false },
];

describe("AlbumActionSurface", () => {
  it("submits selected photo ids to an eligible album", async () => {
    const user = userEvent.setup();
    const onAddToAlbum = vi.fn();

    render(
      <AlbumActionSurface
        albums={albums}
        selectedPhotoIds={["photo-1", "photo-2"]}
        isSubmitting={false}
        resultMessage={null}
        onAddToAlbum={onAddToAlbum}
        onCreateAlbumAndAdd={vi.fn()}
      />
    );

    await user.selectOptions(screen.getByLabelText(/album target/i), "album-1");
    await user.click(screen.getByRole("button", { name: /^add 2 photos$/i }));

    expect(onAddToAlbum).toHaveBeenCalledWith("album-1", ["photo-1", "photo-2"]);
  });

  it("does not offer saved-filter albums as manual targets", () => {
    render(
      <AlbumActionSurface
        albums={albums}
        selectedPhotoIds={["photo-1"]}
        isSubmitting={false}
        resultMessage={null}
        onAddToAlbum={vi.fn()}
        onCreateAlbumAndAdd={vi.fn()}
      />
    );

    expect(screen.queryByRole("option", { name: "Saved filter" })).toBeNull();
  });
});
