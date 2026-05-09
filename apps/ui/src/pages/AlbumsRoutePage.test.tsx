import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { AlbumsRoutePage } from "./AlbumsRoutePage";

function LibraryLocationProbe() {
  const location = useLocation();
  return <p>Library location: {location.pathname}{location.search}</p>;
}

function renderAlbumsRoute(path = "/albums") {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/albums" element={<AlbumsRoutePage />} />
        <Route path="/library" element={<LibraryLocationProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AlbumsRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists albums and opens detail", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/albums") {
        return {
          ok: true,
          json: async () => [
            {
              album_id: "album-1",
              name: "Weekend",
              owner_user_id: "demo-user",
              kind: "editable",
              created_ts: "2026-05-08T12:00:00Z",
              updated_ts: "2026-05-08T12:00:00Z",
              item_count: 1,
              saved_filter: null
            }
          ]
        } as Response;
      }

      if (url === "/api/v1/albums/album-1?page=1&page_size=24") {
        return {
          ok: true,
          json: async () => ({
            album_id: "album-1",
            name: "Weekend",
            owner_user_id: "demo-user",
            kind: "editable",
            created_ts: "2026-05-08T12:00:00Z",
            updated_ts: "2026-05-08T12:00:00Z",
            item_count: 1,
            items_total: 1,
            items: [
              {
                photo_id: "photo-1",
                path: "/library/photo-1.jpg",
                ext: "jpg",
                shot_ts: null,
                filesize: 1024,
                thumbnail: {
                  mime_type: "image/jpeg",
                  width: 120,
                  height: 80,
                  data_base64: "dGh1bWI="
                }
              }
            ],
            page: 1,
            page_size: 24,
            total_pages: 1,
            saved_filter: null
          })
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();

    expect(await screen.findByRole("heading", { name: "Albums", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("1 photos")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show content Weekend" }));

    expect(await screen.findByRole("img", { name: "/library/photo-1.jpg" })).toBeInTheDocument();
  });

  it("creates new albums and removes photo membership for editable albums", async () => {
    const user = userEvent.setup();

    let listPayload: Array<{
      album_id: string;
      name: string;
      owner_user_id: string;
      kind: "editable" | "saved_filter";
      created_ts: string;
      updated_ts: string;
      item_count: number;
      saved_filter: Record<string, unknown> | null;
    }> = [
      {
        album_id: "album-1",
        name: "Weekend",
        owner_user_id: "demo-user",
        kind: "editable",
        created_ts: "2026-05-08T12:00:00Z",
        updated_ts: "2026-05-08T12:00:00Z",
        item_count: 1,
        saved_filter: null
      }
    ];

    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/albums" && (!init || !init.method || init.method === "GET")) {
        return {
          ok: true,
          json: async () => listPayload
        } as Response;
      }
      if (url === "/api/v1/albums" && init?.method === "POST") {
        listPayload = [
          ...listPayload,
          {
            album_id: "album-2",
            name: "Needs review",
            owner_user_id: "demo-user",
            kind: "saved_filter",
            created_ts: "2026-05-08T12:00:00Z",
            updated_ts: "2026-05-08T12:00:00Z",
            item_count: 0,
            saved_filter: { person_names: ["Inez"] }
          }
        ];
        return {
          ok: true,
          json: async () => listPayload[1]
        } as Response;
      }
      if (url === "/api/v1/albums/album-1?page=1&page_size=24") {
        return {
          ok: true,
          json: async () => ({
            album_id: "album-1",
            name: "Weekend",
            owner_user_id: "demo-user",
            kind: "editable",
            created_ts: "2026-05-08T12:00:00Z",
            updated_ts: "2026-05-08T12:00:00Z",
            item_count: 1,
            items_total: 1,
            items: [
              {
                photo_id: "photo-1",
                path: "/library/photo-1.jpg",
                ext: "jpg",
                shot_ts: null,
                filesize: 1024,
                thumbnail: null
              }
            ],
            page: 1,
            page_size: 24,
            total_pages: 1,
            saved_filter: null
          })
        } as Response;
      }
      if (url === "/api/v1/albums/album-1/items/photo-1" && init?.method === "DELETE") {
        return { ok: true, status: 204 } as Response;
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();
    expect(await screen.findByRole("heading", { name: "Albums", level: 1 })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Album name"), "Needs review");
    await user.selectOptions(screen.getByLabelText("Album type"), "saved_filter");
    fireEvent.change(screen.getByLabelText("Saved filter JSON"), {
      target: { value: '{"person_names":["Inez"]}' }
    });
    await user.click(screen.getByRole("button", { name: "Create album" }));

    expect(await screen.findByRole("button", { name: "Open album Needs review" })).toBeInTheDocument();
    expect(screen.getByLabelText("Saved filter JSON for Needs review")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show content Weekend" }));
    await user.click(await screen.findByRole("button", { name: "Remove photo photo-1" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/albums/album-1/items/photo-1", expect.objectContaining({ method: "DELETE" }));
    });
  });

  it("opens editable albums in library with album query filters", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/albums") {
        return {
          ok: true,
          json: async () => [
            {
              album_id: "album-editable",
              name: "Beach",
              owner_user_id: "demo-user",
              kind: "editable",
              created_ts: "2026-05-08T12:00:00Z",
              updated_ts: "2026-05-08T12:00:00Z",
              item_count: 1,
              saved_filter: null
            }
          ]
        } as Response;
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();
    expect(await screen.findByRole("heading", { name: "Albums", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open album Beach" }));
    expect(await screen.findByText("Library location: /library?album=album-editable")).toBeInTheDocument();
  });

  it("opens saved-filter albums in library with mapped query filters", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/albums") {
        return {
          ok: true,
          json: async () => [
            {
              album_id: "album-filter",
              name: "People only",
              owner_user_id: "demo-user",
              kind: "saved_filter",
              created_ts: "2026-05-08T12:00:00Z",
              updated_ts: "2026-05-08T12:00:00Z",
              item_count: 0,
              saved_filter: {
                person_names: ["Inez Rivera"],
                person_certainty_mode: "include_suggestions",
                suggestion_confidence_min: 0.91,
                has_faces: true
              }
            }
          ]
        } as Response;
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();
    expect(await screen.findByRole("heading", { name: "Albums", level: 1 })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open album People only" }));
    expect(await screen.findByText(
      "Library location: /library?person=Inez+Rivera&personCertainty=include_suggestions&suggestionMin=0.91&hasFaces=true"
    )).toBeInTheDocument();
  });
});
