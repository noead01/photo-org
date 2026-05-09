import { fireEvent, render, screen } from "@testing-library/react";

import { BrowsePagination } from "./BrowsePagination";

describe("BrowsePagination", () => {
  it("renders current page and neighbors", () => {
    render(
      <BrowsePagination
        currentPage={6}
        pageCount={12}
        canGoPrevious
        canGoNext
        ariaLabel="Suggestion pagination"
        onPageChange={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "Previous page" })).toHaveAttribute("aria-disabled", "false");
    expect(screen.getByRole("button", { name: "Page 6" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Page 5" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 7" })).toBeInTheDocument();
  });

  it("converts page selections to one-based pages", () => {
    const onPageChange = vi.fn();

    render(
      <BrowsePagination
        currentPage={2}
        pageCount={3}
        canGoPrevious
        canGoNext
        ariaLabel="Library pagination"
        onPageChange={onPageChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    fireEvent.click(screen.getByRole("button", { name: "Page 3" }));

    expect(onPageChange).toHaveBeenCalledWith(1);
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("suppresses disabled previous and next actions", () => {
    const onPageChange = vi.fn();

    render(
      <BrowsePagination
        currentPage={1}
        pageCount={1}
        canGoPrevious={false}
        canGoNext={false}
        ariaLabel="Library pagination"
        onPageChange={onPageChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));

    expect(onPageChange).not.toHaveBeenCalled();
  });

  it("clamps out-of-range current page to the known page count", () => {
    render(
      <BrowsePagination
        currentPage={7}
        pageCount={1}
        canGoPrevious={false}
        canGoNext={false}
        ariaLabel="Library pagination"
        onPageChange={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("button", { name: "Page 7" })).not.toBeInTheDocument();
  });
});
