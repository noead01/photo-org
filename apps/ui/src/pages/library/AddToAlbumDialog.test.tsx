import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AddToAlbumDialog } from "./AddToAlbumDialog";

describe("AddToAlbumDialog", () => {
  it("does not render when closed", () => {
    render(
      <AddToAlbumDialog
        isOpen={false}
        isSaving={false}
        photoCount={0}
        albumKind="editable"
        albumName=""
        showAlbumTypeInfo={false}
        error={null}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        onAlbumKindChange={vi.fn()}
        onAlbumNameChange={vi.fn()}
        onToggleAlbumTypeInfo={vi.fn()}
      />
    );

    expect(screen.queryByRole("dialog", { name: "Add to album" })).not.toBeInTheDocument();
  });

  it("supports kind toggle, name change, close actions, and submit", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onSubmit = vi.fn((event: React.FormEvent<HTMLFormElement>) => event.preventDefault());
    const onAlbumKindChange = vi.fn();
    const onAlbumNameChange = vi.fn();
    const onToggleAlbumTypeInfo = vi.fn();

    render(
      <AddToAlbumDialog
        isOpen
        isSaving={false}
        photoCount={3}
        albumKind="editable"
        albumName=""
        showAlbumTypeInfo={false}
        error={null}
        onClose={onClose}
        onSubmit={onSubmit}
        onAlbumKindChange={onAlbumKindChange}
        onAlbumNameChange={onAlbumNameChange}
        onToggleAlbumTypeInfo={onToggleAlbumTypeInfo}
      />
    );

    expect(screen.getByText("Selection snapshot: 3 photos.")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Album type info"));
    expect(onToggleAlbumTypeInfo).toHaveBeenCalledTimes(1);

    await user.click(screen.getByLabelText("Saved Filter"));
    expect(onAlbumKindChange).toHaveBeenCalledWith("saved_filter");

    fireEvent.change(screen.getByLabelText("Album name"), {
      target: { value: "Trip Highlights" }
    });
    expect(onAlbumNameChange).toHaveBeenCalledWith("Trip Highlights");

    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByLabelText("Close add to album modal"));
    expect(onClose).toHaveBeenCalledTimes(3);

    await user.click(screen.getByRole("button", { name: "Save to album" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
