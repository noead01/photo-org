import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LibraryRoutePage } from "./LibraryRoutePage";

describe("LibraryRoutePage", () => {
  it("renders library query controls and results scaffold on /library", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ hits: { total: 0, cursor: null, items: [] }, facets: {} })
      })) as typeof fetch
    );

    render(
      <MemoryRouter
        initialEntries={["/library"]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/library" element={<LibraryRoutePage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Search query" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Photo gallery" })).toBeInTheDocument();
  });
});
