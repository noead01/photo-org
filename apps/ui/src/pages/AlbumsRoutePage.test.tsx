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

    expect(
      await screen.findByRole("img", { name: /preview of \/library\/photo-1.jpg/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Album photo thumbnails" })).toHaveClass("browse-grid");
  });

  it("toggles album face boxes and preloads detail faces for visible photos", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }

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

      if (url === "/api/v1/photos/photo-1") {
        return {
          ok: true,
          json: async () => ({
            photo_id: "photo-1",
            path: "/library/photo-1.jpg",
            ext: "jpg",
            camera_make: null,
            orientation: null,
            shot_ts: null,
            filesize: 1024,
            tags: [],
            people: [],
            faces: [
              {
                face_id: "face-1",
                person_id: null,
                bbox_x: 10,
                bbox_y: 12,
                bbox_w: 18,
                bbox_h: 20,
                bbox_space_width: 120,
                bbox_space_height: 80,
                label_source: null,
                confidence: null,
                model_version: null,
                provenance: null,
                label_recorded_ts: null
              }
            ],
            thumbnail: {
              mime_type: "image/jpeg",
              width: 120,
              height: 80,
              data_base64: "dGh1bWI="
            },
            original: {
              is_available: true,
              availability_state: "available",
              last_failure_reason: null
            },
            metadata: {
              sha256: "sha",
              phash: null,
              shot_ts_source: null,
              camera_model: null,
              software: null,
              gps_latitude: null,
              gps_longitude: null,
              gps_altitude: null,
              exif_attributes: null,
              created_ts: "2026-05-08T12:00:00Z",
              updated_ts: "2026-05-08T12:00:00Z",
              modified_ts: null,
              deleted_ts: null,
              faces_count: 1,
              faces_detected_ts: null
            }
          })
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();

    expect(await screen.findByRole("heading", { name: "Albums", level: 1 })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show content Weekend" }));

    const faceBoxesToggle = screen.getByLabelText("Show face boxes on all photos");
    expect(faceBoxesToggle).not.toBeChecked();
    expect(faceBoxesToggle.closest("label")).toHaveClass("albums-detail-face-boxes-toggle");
    expect(screen.queryByRole("button", { name: "Open face 1 actions" })).not.toBeInTheDocument();

    await user.click(faceBoxesToggle);

    expect(await screen.findByRole("button", { name: "Open face 1 actions" })).toBeInTheDocument();

    await user.click(screen.getByLabelText("Show face boxes on all photos"));
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Open face 1 actions" })).not.toBeInTheDocument();
    });
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

  it("uses shared photo selection and metadata inside album detail", async () => {
    const user = userEvent.setup();

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
      if (url === "/api/v1/photos/photo-1") {
        return {
          ok: true,
          json: async () => ({
            photo_id: "photo-1",
            path: "/library/photo-1.jpg",
            ext: "jpg",
            camera_make: null,
            orientation: null,
            shot_ts: "2026-05-08T12:00:00Z",
            filesize: 1024,
            tags: [],
            people: [],
            faces: [],
            thumbnail: null,
            original: {
              is_available: true,
              availability_state: "available",
              last_failure_reason: null
            },
            metadata: {
              sha256: "photo-1-sha",
              phash: null,
              shot_ts_source: null,
              camera_model: null,
              software: null,
              gps_latitude: null,
              gps_longitude: null,
              gps_altitude: null,
              exif_attributes: null,
              created_ts: "2026-05-08T12:00:00Z",
              updated_ts: "2026-05-08T12:00:00Z",
              modified_ts: null,
              deleted_ts: null,
              faces_count: 0,
              faces_detected_ts: null
            }
          })
        } as Response;
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();

    await user.click(await screen.findByRole("button", { name: /show content/i }));
    await user.click(await screen.findByRole("checkbox", { name: /select photo/i }));
    await user.click(screen.getByRole("button", { name: /show metadata/i }));

    expect(screen.getByRole("checkbox", { name: /select photo/i })).toBeChecked();
    expect(screen.getByRole("complementary", { name: /metadata/i })).toBeInTheDocument();
  });

  it("exports album photos into a selected folder one file at a time", async () => {
    const user = userEvent.setup();
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    let releaseFirstWrite: (() => void) | null = null;
    const firstWritePending = new Promise<void>((resolve) => {
      releaseFirstWrite = resolve;
    });
    const writeSpy = vi.fn(async () => {});
    const closeSpy = vi.fn(async () => {});
    writeSpy.mockImplementationOnce(async () => {
      await firstWritePending;
    });
    const createWritableSpy = vi.fn(async () => ({
      write: writeSpy,
      close: closeSpy
    }));
    const getFileHandleSpy = vi.fn(async () => ({
      createWritable: createWritableSpy
    }));
    const showDirectoryPickerSpy = vi.fn(async () => ({
      name: "AlbumExports",
      getFileHandle: getFileHandleSpy
    }));
    Object.defineProperty(window, "showDirectoryPicker", {
      writable: true,
      value: showDirectoryPickerSpy
    });

    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
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
              item_count: 2,
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
            item_count: 2,
            items_total: 2,
            items: [
              {
                photo_id: "photo-1",
                path: "/library/photo-1.jpg",
                ext: "jpg",
                shot_ts: null,
                filesize: 1024,
                thumbnail: null
              },
              {
                photo_id: "photo-2",
                path: "/library/photo-2.jpg",
                ext: "jpg",
                shot_ts: null,
                filesize: 2048,
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
      if (url === "/api/v1/photos/photo-1/original?download=true") {
        return new Response(new Blob([new Uint8Array([1, 2, 3])], { type: "image/jpeg" }), {
          status: 200,
          headers: {
            "Content-Type": "image/jpeg",
            "Content-Disposition": 'attachment; filename="photo-1-trip-a.jpg"'
          }
        });
      }
      if (url === "/api/v1/photos/photo-2/original?download=true") {
        return new Response(new Blob([new Uint8Array([4, 5, 6])], { type: "image/heic" }), {
          status: 200,
          headers: {
            "Content-Type": "image/heic",
            "Content-Disposition": 'attachment; filename="photo-2-portrait.heic"'
          }
        });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();
    expect(await screen.findByRole("heading", { name: "Albums", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Export album Weekend" }));

    expect(
      screen.getByRole("progressbar", { name: "Export progress for Weekend" })
    ).toBeInTheDocument();
    expect(screen.getByText('Exporting 0 of 2 photos to "AlbumExports".')).toBeInTheDocument();

    releaseFirstWrite?.();

    await waitFor(() => {
      expect(showDirectoryPickerSpy).toHaveBeenCalledTimes(1);
      expect(getFileHandleSpy).toHaveBeenCalledWith("photo-1-trip-a.jpg", { create: true });
      expect(getFileHandleSpy).toHaveBeenCalledWith("photo-2-portrait.heic", { create: true });
    });
    expect(writeSpy).toHaveBeenCalledTimes(2);
    expect(closeSpy).toHaveBeenCalledTimes(2);
    expect(alertSpy).toHaveBeenCalledWith(
      'Export complete: 2 photos saved to "AlbumExports". Open that folder in your file manager to access the photos.'
    );
  });

  it("falls back to zip export when folder picker is unavailable", async () => {
    const user = userEvent.setup();
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    Object.defineProperty(window, "showDirectoryPicker", {
      writable: true,
      value: undefined
    });
    if (!("createObjectURL" in URL)) {
      Object.defineProperty(URL, "createObjectURL", {
        writable: true,
        value: vi.fn()
      });
      Object.defineProperty(URL, "revokeObjectURL", {
        writable: true,
        value: vi.fn()
      });
    }
    const createObjectUrlSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:album-export-fallback");
    const revokeObjectUrlSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
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
              item_count: 2,
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
            item_count: 2,
            items_total: 2,
            items: [
              {
                photo_id: "photo-1",
                path: "/library/photo-1.jpg",
                ext: "jpg",
                shot_ts: null,
                filesize: 1024,
                thumbnail: null
              },
              {
                photo_id: "photo-2",
                path: "/library/photo-2.jpg",
                ext: "jpg",
                shot_ts: null,
                filesize: 2048,
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
      if (url === "/api/v1/exports/photos") {
        const parsedBody = JSON.parse((init?.body as string | undefined) ?? "{}") as {
          photo_ids?: string[];
        };
        expect(parsedBody.photo_ids).toEqual(["photo-1", "photo-2"]);
        return new Response(new Blob([new Uint8Array([7, 8, 9])], { type: "application/zip" }), {
          status: 200,
          headers: {
            "Content-Type": "application/zip",
            "Content-Disposition": 'attachment; filename="album-export.zip"',
            "X-Photo-Org-Exported-Count": "2",
            "X-Photo-Org-Skipped-Count": "0"
          }
        });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderAlbumsRoute();
    expect(await screen.findByRole("heading", { name: "Albums", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Export album Weekend" }));

    await waitFor(() => {
      expect(createObjectUrlSpy).toHaveBeenCalled();
    });
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:album-export-fallback");
    expect(alertSpy).toHaveBeenCalledWith(
      'Folder picker is unavailable in this browser. Downloaded "album-export.zip" as a ZIP file. Open your Downloads folder to access it.'
    );
  });
});
