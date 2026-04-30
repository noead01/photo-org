import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { BrowseRoutePage } from "./BrowseRoutePage";

interface SearchResponsePayload {
  hits: {
    total: number;
    cursor: string | null;
    items: Array<{
      photo_id: string;
      path: string;
      ext: string;
      camera_make: string | null;
      orientation: string | null;
      shot_ts: string | null;
      filesize: number;
      tags: string[];
      people: string[];
      faces: Array<{ person_id: string | null }>;
      thumbnail: {
        mime_type: string;
        width: number;
        height: number;
        data_base64: string;
      } | null;
      original: {
        is_available: boolean;
        availability_state: string;
        last_failure_reason: string | null;
      } | null;
      relevance: number | null;
    }>;
  };
  facets: Record<string, unknown>;
}

function buildPayload(
  photoIds: string[],
  cursor: string | null,
  total = photoIds.length
): SearchResponsePayload {
  return {
    hits: {
      total,
      cursor,
      items: photoIds.map((photoId, index) => ({
        photo_id: photoId,
        path: `/library/${photoId}.jpg`,
        ext: "jpg",
        camera_make: "Canon",
        orientation: "landscape",
        shot_ts: `2026-04-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
        filesize: 1024 + index,
        tags: [],
        people: [],
        faces: [],
        thumbnail: null,
        original: {
          is_available: true,
          availability_state: "available",
          last_failure_reason: null
        },
        relevance: null
      }))
    },
    facets: {}
  };
}

function renderBrowseAt(path: string) {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/browse" element={<BrowseRoutePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("BrowseRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads page one with deterministic default sort", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload(["photo-a", "photo-b"], "cursor-page-2", 7)
    } as Response);

    renderBrowseAt("/browse");

    expect(await screen.findByRole("heading", { name: "Browse", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("photo-a")).toBeInTheDocument();
    expect(screen.getByText("photo-b")).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/search");

    const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const parsedBody = JSON.parse(String(requestInit.body));
    expect(parsedBody.sort).toEqual({ by: "shot_ts", dir: "desc" });
    expect(parsedBody.page).toEqual({ limit: 24, cursor: null });
    expect(screen.getByText("Page 1")).toBeInTheDocument();
  });

  it("advances to next page with returned cursor and supports previous", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload(["photo-a"], "cursor-page-2", 3)
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload(["photo-b"], "cursor-page-3", 3)
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload(["photo-a"], "cursor-page-2", 3)
      } as Response);

    renderBrowseAt("/browse");

    expect(await screen.findByText("photo-a")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next page" }));

    expect(await screen.findByText("photo-b")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();

    const secondRequest = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(JSON.parse(String(secondRequest.body)).page).toEqual({
      limit: 24,
      cursor: "cursor-page-2"
    });

    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(await screen.findByText("photo-a")).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();
  });

  it("resets to page one when sort order changes", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload(["photo-a"], "cursor-page-2", 2)
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload(["photo-b"], "cursor-page-2-asc", 2)
      } as Response);

    renderBrowseAt("/browse");

    expect(await screen.findByText("photo-a")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Sort order"), "asc");

    expect(await screen.findByText("photo-b")).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();

    const secondRequest = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(JSON.parse(String(secondRequest.body)).sort).toEqual({ by: "shot_ts", dir: "asc" });
    expect(JSON.parse(String(secondRequest.body)).page).toEqual({ limit: 24, cursor: null });
  });

  it("falls back to page one for unsupported direct page navigation", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload(["photo-a"], "cursor-page-2", 2)
    } as Response);

    renderBrowseAt("/browse?page=3");

    expect(await screen.findByText("photo-a")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Page 1")).toBeInTheDocument();
    });

    expect(screen.getByText("Reset to page 1 because that page position is unavailable.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("renders ingest status badges and legend entries", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        hits: {
          total: 3,
          cursor: null,
          items: [
            {
              ...buildPayload(["photo-complete"], null).hits.items[0],
              photo_id: "photo-complete",
              thumbnail: {
                mime_type: "image/jpeg",
                width: 10,
                height: 10,
                data_base64: "dGh1bWI="
              },
              original: {
                is_available: true,
                availability_state: "active",
                last_failure_reason: null
              }
            },
            {
              ...buildPayload(["photo-pending"], null).hits.items[0],
              photo_id: "photo-pending",
              thumbnail: null,
              original: {
                is_available: true,
                availability_state: "active",
                last_failure_reason: null
              }
            },
            {
              ...buildPayload(["photo-unknown"], null).hits.items[0],
              photo_id: "photo-unknown",
              thumbnail: null,
              original: {
                is_available: true,
                availability_state: "mystery",
                last_failure_reason: null
              }
            }
          ]
        },
        facets: {}
      })
    } as Response);

    renderBrowseAt("/browse");

    expect(await screen.findByText("photo-complete")).toBeInTheDocument();
    expect(screen.getByText("Ingest status legend")).toBeInTheDocument();
    expect(screen.getAllByText("Complete").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
  });

  it("restores focus to the previously selected photo when returning from detail", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload(["photo-a", "photo-b"], null, 2)
    } as Response);

    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/browse",
            state: { restoreFocusPhotoId: "photo-b" }
          }
        ]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/browse" element={<BrowseRoutePage />} />
        </Routes>
      </MemoryRouter>
    );

    const targetLink = await screen.findByRole("link", { name: "photo-b" });
    await waitFor(() => {
      expect(targetLink).toHaveFocus();
    });
  });

  it("falls back to the browse heading when return-focus target is unavailable", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload(["photo-a"], null, 1)
    } as Response);

    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/browse",
            state: { restoreFocusPhotoId: "photo-missing" }
          }
        ]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/browse" element={<BrowseRoutePage />} />
        </Routes>
      </MemoryRouter>
    );

    const heading = await screen.findByRole("heading", { name: "Browse", level: 1 });
    await waitFor(() => {
      expect(heading).toHaveFocus();
    });
  });
});
