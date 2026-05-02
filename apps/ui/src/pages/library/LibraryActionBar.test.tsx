import { render, screen } from "@testing-library/react";
import { LibraryActionBar } from "./LibraryActionBar";
import type { LibraryActionBarState } from "./libraryActionBarState";

function buildActionState(overrides: Partial<LibraryActionBarState> = {}): LibraryActionBarState {
  return {
    addToAlbum: { enabled: true, reason: null },
    export: { enabled: true, reason: null },
    ...overrides
  };
}

describe("LibraryActionBar", () => {
  it("renders only when selection count is positive", () => {
    const { rerender } = render(
      <LibraryActionBar selectionCount={0} actionState={buildActionState()} onAction={vi.fn()} />
    );
    expect(screen.queryByLabelText("Library actions")).not.toBeInTheDocument();

    rerender(
      <LibraryActionBar selectionCount={2} actionState={buildActionState()} onAction={vi.fn()} />
    );
    expect(screen.getByLabelText("Library actions")).toBeInTheDocument();
  });

  it("binds disabled explanation text with aria-describedby", () => {
    render(
      <LibraryActionBar
        selectionCount={2}
        actionState={{
          addToAlbum: {
            enabled: false,
            reason: "You do not have permission for this action."
          },
          export: { enabled: true, reason: null }
        }}
        onAction={vi.fn()}
      />
    );

    const addButton = screen.getByRole("button", { name: "Add to album" });
    const reason = screen.getByText("You do not have permission for this action.");
    expect(reason).toHaveAttribute("id");
    expect(addButton).toHaveAttribute("aria-describedby", reason.id);
  });
});
