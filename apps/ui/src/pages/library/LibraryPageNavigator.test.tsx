import { fireEvent, render, screen } from "@testing-library/react";
import { LibraryPageNavigator } from "./LibraryPageNavigator";

describe("LibraryPageNavigator", () => {
  it("renders classic page controls and current page state", () => {
    render(
      <LibraryPageNavigator
        requestedPage={6}
        lastKnownPage={12}
        canGoPrevious
        canGoNext
        pageSize={60}
        pageSizeOptions={[24, 60, 120]}
        onSelectPage={vi.fn()}
        onPageSizeChange={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "Previous page" })).toHaveAttribute(
      "aria-disabled",
      "false"
    );
    expect(screen.getByRole("button", { name: "Next page" })).toHaveAttribute("aria-disabled", "false");
    expect(screen.getByRole("button", { name: "Page 6" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Page 5" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 7" })).toBeInTheDocument();
    expect(screen.getAllByText("...")).toHaveLength(2);
  });

  it("wires button actions to callbacks", () => {
    const onSelectPage = vi.fn();
    const onPageSizeChange = vi.fn();

    render(
      <LibraryPageNavigator
        requestedPage={2}
        lastKnownPage={3}
        canGoPrevious
        canGoNext
        pageSize={60}
        pageSizeOptions={[24, 60, 120]}
        onSelectPage={onSelectPage}
        onPageSizeChange={onPageSizeChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Photos per page" }), {
      target: { value: "120" }
    });

    expect(onSelectPage).toHaveBeenCalledWith(1);
    expect(onSelectPage).toHaveBeenCalledWith(3);
    expect(onPageSizeChange).toHaveBeenCalledWith(120);
  });

  it("respects disabled navigation flags", () => {
    render(
      <LibraryPageNavigator
        requestedPage={1}
        lastKnownPage={1}
        canGoPrevious={false}
        canGoNext={false}
        pageSize={60}
        pageSizeOptions={[24, 60, 120]}
        onSelectPage={vi.fn()}
        onPageSizeChange={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "Previous page" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
    expect(screen.getByRole("button", { name: "Next page" })).toHaveAttribute("aria-disabled", "true");
  });
});
