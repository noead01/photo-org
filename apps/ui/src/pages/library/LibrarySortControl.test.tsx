import { fireEvent, render, screen } from "@testing-library/react";
import { LibrarySortControl } from "./LibrarySortControl";

describe("LibrarySortControl", () => {
  it("renders the selected sort direction", () => {
    render(<LibrarySortControl sortDirection="desc" onSortDirectionChange={vi.fn()} />);

    expect(screen.getByRole("combobox", { name: "Sort order" })).toHaveValue("desc");
  });

  it("emits sort direction changes from select input", () => {
    const onSortDirectionChange = vi.fn();
    render(<LibrarySortControl sortDirection="desc" onSortDirectionChange={onSortDirectionChange} />);

    fireEvent.change(screen.getByRole("combobox", { name: "Sort order" }), {
      target: { value: "asc" }
    });

    expect(onSortDirectionChange).toHaveBeenCalledWith("asc");
  });
});
