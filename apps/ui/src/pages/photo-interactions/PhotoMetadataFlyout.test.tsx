import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PhotoMetadataFlyout } from "./PhotoMetadataFlyout";

describe("PhotoMetadataFlyout", () => {
  it("shows active photo identity and closes without mutating route state", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <PhotoMetadataFlyout
        isOpen
        summary={{
          photoId: "photo-1",
          title: "lake.jpg",
          path: "/photos/lake.jpg",
          thumbnail: {
            mimeType: "image/jpeg",
            width: 100,
            height: 80,
            dataBase64: "abc",
          },
        }}
        detail={null}
        isLoadingDetail={false}
        detailError={null}
        onClose={onClose}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByRole("complementary", { name: /metadata for lake.jpg/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /close metadata/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows scoped retry when detail loading fails", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    render(
      <PhotoMetadataFlyout
        isOpen
        summary={{ photoId: "photo-1", title: "lake.jpg", path: "/photos/lake.jpg", thumbnail: null }}
        detail={null}
        isLoadingDetail={false}
        detailError="Could not load metadata."
        onClose={vi.fn()}
        onRetry={onRetry}
      />
    );

    expect(screen.getByText("Could not load metadata.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry metadata/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
