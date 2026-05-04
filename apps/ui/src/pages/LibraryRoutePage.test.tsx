import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { LibraryRoutePage } from "./LibraryRoutePage";

type SearchResponsePayload = {
  hits: {
    total: number;
    cursor: string | null;
    items: Array<{
      photo_id: string;
      path: string;
      ext: string;
      shot_ts: string | null;
      filesize: number;
      people: string[];
      faces: Array<{
        person_id: string | null;
        label_source?: "human_confirmed" | "machine_suggested" | null;
        confidence?: number | null;
      }>;
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
      };
    }>;
  };
};

function buildPayload(
  photoIds: string[],
  total = photoIds.length,
  includeDetectedFaces = false
): SearchResponsePayload {
  return {
    hits: {
      total,
      cursor: null,
      items: photoIds.map((photoId, index) => ({
        photo_id: photoId,
        path: `/library/${photoId}.jpg`,
        ext: "jpg",
        shot_ts: `2026-04-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
        filesize: 1024 + index,
        people: [],
        faces: includeDetectedFaces ? [{ person_id: null }] : [],
        thumbnail: null,
        original: {
          is_available: true,
          availability_state: "available",
          last_failure_reason: null
        }
      }))
    }
  };
}

function renderLibraryAt(path = "/library") {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/library" element={<LibraryRoutePage />} />
      </Routes>
    </MemoryRouter>
  );
}

function LibraryTestDetailReturn() {
  const location = useLocation();
  const state = (location.state ?? {}) as {
    returnToLibrarySearch?: string;
    returnFocusPhotoId?: string;
    librarySelection?: unknown;
    libraryViewState?: unknown;
  };

  return (
    <section>
      <h1>Library test detail</h1>
      <Link
        to={{
          pathname: "/library",
          search: state.returnToLibrarySearch ?? ""
        }}
        state={{
          restoreFocusPhotoId: state.returnFocusPhotoId,
          librarySelection: state.librarySelection,
          libraryViewState: state.libraryViewState
        }}
      >
        Back to library
      </Link>
    </section>
  );
}

function renderLibraryWithDetailAt(path = "/library") {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/library" element={<LibraryRoutePage />} />
        <Route path="/library/:photoId" element={<LibraryTestDetailReturn />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("LibraryRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    window.__PHOTO_ORG_SESSION__ = {
      userId: "operator-1",
      displayName: "Operator One",
      email: "op1@photo-org.local",
      capabilities: { addToAlbum: true, export: true }
    };
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.__PHOTO_ORG_SESSION__ = undefined;
  });

  it("renders library query controls and simplified photo cards", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library");

    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Search query" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Filter labels" })).toBeInTheDocument();
    expect(screen.queryByLabelText("From date")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Filter labels" }));

    expect(screen.getByLabelText("From date")).toBeInTheDocument();
    expect(screen.getByLabelText("To date")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Person filter" })).toBeInTheDocument();
    expect(screen.getByLabelText("Person certainty mode")).toBeInTheDocument();
    expect(screen.getByLabelText("Latitude")).toBeInTheDocument();
    expect(screen.getByLabelText("Longitude")).toBeInTheDocument();
    expect(screen.getByLabelText("Radius (km)")).toBeInTheDocument();
    expect(screen.getByLabelText("Facet filters")).toBeInTheDocument();
    expect(await screen.findByRole("list", { name: "Photo gallery" })).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Review faces" })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Select photo photo-a" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Show face boxes on all photos" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View details" })).not.toBeInTheDocument();
  });

  it("links thumbnail previews to photo detail", async () => {
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      const payload = buildPayload(["photo-a"]);
      payload.hits.items[0].thumbnail = {
        mime_type: "image/jpeg",
        width: 120,
        height: 80,
        data_base64: "dGh1bWI="
      };

      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");
    const thumbnailLink = await screen.findByRole("link", {
      name: "Open details for /library/photo-a.jpg"
    });

    expect(thumbnailLink).toHaveAttribute("href", "/library/photo-a");
  });

  it("shows source-relative path labels in the grid", async () => {
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      const payload = buildPayload(["photo-a"]);
      payload.hits.items[0].path =
        "/storage-sources/1f9a5c89-b49c-47aa-b000-3fb56c21f9ce/folder/photo123.jpg";
      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");

    expect(await screen.findByText(".../folder/photo123.jpg")).toBeInTheDocument();
    expect(screen.queryByText(/\/storage-sources\/1f9a5c89/)).not.toBeInTheDocument();
  });

  it("shows face metrics on cards", async () => {
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      const payload = buildPayload(["photo-a"]);
      payload.hits.items[0].faces = [
        { person_id: "person-1", label_source: "human_confirmed", confidence: null },
        { person_id: "person-1", label_source: "machine_suggested", confidence: 0.91 },
        { person_id: "person-2", label_source: "machine_suggested", confidence: 0.77 },
        { person_id: null, label_source: null, confidence: null }
      ];
      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    expect(screen.getByText("Faces detected")).toBeInTheDocument();
    expect(screen.getByText("People assigned (human)")).toBeInTheDocument();
    expect(screen.getByText("Machine suggestions")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("advances to the next cursor-backed page when Next is clicked", async () => {
    const user = userEvent.setup();

    const pageOneIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 1}`);
    const pageTwoIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 61}`);
    const pageThreeIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 121}`);

    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }

      if (url !== "/api/v1/search") {
        throw new Error(`Unhandled fetch: ${url}`);
      }

      const requestBody = JSON.parse((init?.body as string | undefined) ?? "{}") as {
        page?: { cursor?: string | null };
      };
      const requestCursor = requestBody.page?.cursor ?? null;

      if (requestCursor === "cursor-page-2") {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 181,
              cursor: "cursor-page-3",
              items: buildPayload(pageTwoIds, 181).hits.items
            }
          })
        } as Response;
      }

      if (requestCursor === "cursor-page-3") {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 181,
              cursor: "cursor-page-4",
              items: buildPayload(pageThreeIds, 181).hits.items
            }
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 181,
            cursor: "cursor-page-2",
            items: buildPayload(pageOneIds, 181).hits.items
          }
        })
      } as Response;
    });

    renderLibraryAt("/library");

    expect(await screen.findByText("Showing 60 of 181 photos")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Page 4" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next page" }));

    expect(await screen.findByRole("button", { name: "Page 2" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getAllByRole("link", { name: /Open details for/ }).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Page 1" }));
    expect(await screen.findByRole("button", { name: "Page 1" })).toHaveAttribute(
      "aria-current",
      "page"
    );

    await user.click(screen.getByRole("button", { name: "Page 3" }));
    expect(await screen.findByRole("button", { name: "Page 3" })).toHaveAttribute(
      "aria-current",
      "page"
    );

    const searchRequestCursors = fetchMock.mock.calls
      .filter(([input]) => String(input) === "/api/v1/search")
      .map(([, init]) => {
        const parsedBody = JSON.parse((init?.body as string | undefined) ?? "{}") as {
          page?: { cursor?: string | null };
        };
        return parsedBody.page?.cursor ?? null;
      });

    expect(searchRequestCursors).toContain("cursor-page-2");
    expect(searchRequestCursors).toContain("cursor-page-3");
  });

  it("updates search page limit when photos-per-page selector changes", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }
      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }
      if (url !== "/api/v1/search") {
        throw new Error(`Unhandled fetch: ${url}`);
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 3,
            cursor: null,
            items: buildPayload(["photo-a", "photo-b", "photo-c"], 3).hits.items
          }
        })
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByText("Showing 3 of 3 photos")).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Photos per page" }), "24");

    const searchRequests = fetchMock.mock.calls.filter(([input]) => String(input) === "/api/v1/search");
    const limits = searchRequests.map(([, init]) => {
      const parsedBody = JSON.parse((init?.body as string | undefined) ?? "{}") as {
        page?: { limit?: number };
      };
      return parsedBody.page?.limit;
    });

    expect(limits[0]).toBe(60);
    expect(limits[limits.length - 1]).toBe(24);
  });

  it("keeps page and photo selections when navigating to detail and back", async () => {
    const user = userEvent.setup();
    const pageOneIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 1}`);
    const pageTwoIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 61}`);

    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }
      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }
      if (url !== "/api/v1/search") {
        throw new Error(`Unhandled fetch: ${url}`);
      }

      const requestBody = JSON.parse((init?.body as string | undefined) ?? "{}") as {
        page?: { cursor?: string | null };
      };
      const requestCursor = requestBody.page?.cursor ?? null;

      if (requestCursor === "cursor-page-2") {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 121,
              cursor: "cursor-page-3",
              items: buildPayload(pageTwoIds, 121).hits.items
            }
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 121,
            cursor: "cursor-page-2",
            items: buildPayload(pageOneIds, 121).hits.items
          }
        })
      } as Response;
    });

    renderLibraryWithDetailAt("/library");

    expect(await screen.findByText("Showing 60 of 121 photos")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("button", { name: "Page 2" })).toHaveAttribute(
      "aria-current",
      "page"
    );

    await user.click(screen.getByRole("checkbox", { name: "Select photo photo-61" }));
    expect(screen.getByRole("checkbox", { name: "Select photo photo-61" })).toBeChecked();

    await user.click(screen.getByRole("link", { name: "Open details for /library/photo-61.jpg" }));
    expect(await screen.findByRole("heading", { name: "Library test detail", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Back to library" }));

    expect(await screen.findByRole("button", { name: "Page 2" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getByRole("checkbox", { name: "Select photo photo-61" })).toBeChecked();
  });

  it("shows action bar when selection scope is set to page", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library");

    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.queryByLabelText("Library actions")).not.toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "This page" }));
    expect(screen.getByLabelText("Library actions")).toBeInTheDocument();
  });

  it("disables actions while operations conflict is active", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 1 } } })
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "This page" }));

    expect(screen.getByRole("button", { name: "Add to album" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Export" })).toBeDisabled();
    expect(
      screen.getAllByText("Action temporarily unavailable while ingest processing is active.")
        .length
    ).toBeGreaterThan(0);
  });
});
