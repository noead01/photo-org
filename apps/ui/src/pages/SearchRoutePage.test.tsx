import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SearchRoutePage } from "./SearchRoutePage";

interface SearchResponsePayload {
  hits: {
    total: number;
    cursor: string | null;
    items: Array<{
      photo_id: string;
      path: string;
      ext: string;
      shot_ts: string | null;
      filesize: number;
    }>;
  };
  facets: Record<string, unknown>;
}

function buildPayload(photoIds: string[], total = photoIds.length): SearchResponsePayload {
  return {
    hits: {
      total,
      cursor: null,
      items: photoIds.map((photoId, index) => ({
        photo_id: photoId,
        path: `/library/${photoId}.jpg`,
        ext: "jpg",
        shot_ts: `2026-04-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
        filesize: 1024 + index
      }))
    },
    facets: {}
  };
}

function renderSearchAt(path = "/search") {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/search" element={<SearchRoutePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("SearchRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => buildPayload([], 0)
    } as Response);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits a phrase chip with Enter and sends q using chip-order serialization", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "lake weekend{enter}");

    expect(await screen.findByRole("button", { name: "Remove query lake weekend" })).toBeInTheDocument();

    const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    expect(lastCall?.[0]).toBe("/api/v1/search");
    const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
    expect(body.q).toBe("lake weekend");
    expect(body.sort).toEqual({ by: "shot_ts", dir: "desc" });
    expect(body.page).toEqual({ limit: 24, cursor: null });
  });

  it("submits with Search button and appends phrase as a new chip", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "first phrase");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.type(input, "second phrase");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByRole("button", { name: "Remove query first phrase" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove query second phrase" })).toBeInTheDocument();

    const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
    expect(body.q).toBe("first phrase second phrase");
  });

  it("ignores whitespace-only submit and keeps existing chips and request count unchanged", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "coastline");
    await user.click(screen.getByRole("button", { name: "Search" }));
    const callsAfterFirstSubmit = fetchMock.mock.calls.length;

    await user.clear(input);
    await user.type(input, "   ");
    await user.keyboard("{Enter}");

    expect(fetchMock.mock.calls.length).toBe(callsAfterFirstSubmit);
    expect(screen.getByRole("button", { name: "Remove query coastline" })).toBeInTheDocument();
  });

  it("removes dismissed chip and re-fetches using remaining chip order", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "alpha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.type(input, "beta");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.click(screen.getByRole("button", { name: "Remove query alpha" }));

    const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
    expect(body.q).toBe("beta");
    expect(screen.queryByRole("button", { name: "Remove query alpha" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove query beta" })).toBeInTheDocument();
  });

  it("renders loading status while the search request is pending", async () => {
    let resolveResponse!: (value: Response) => void;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveResponse = resolve;
        })
    );

    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "harbor");
    await user.keyboard("{Enter}");

    expect(screen.getByRole("status")).toHaveTextContent("Loading search workflow.");

    resolveResponse({
      ok: true,
      json: async () => buildPayload([], 0)
    } as Response);

    expect(await screen.findByText("No matching photos for the active query.")).toBeInTheDocument();
  });

  it("shows retry UI on failure and retries with active chips", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({ ok: false, status: 503 } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload(["photo-1"], 1)
      } as Response);

    renderSearchAt();
    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "storm coast");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(
      await screen.findByRole("heading", {
        name: "Could not load Search",
        level: 2
      })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
    expect(body.q).toBe("storm coast");
    expect(await screen.findByText("photo-1")).toBeInTheDocument();
  });
});
