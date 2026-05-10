import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { LibraryRoutePage } from "./LibraryRoutePage";
import { buildLibraryViewStateStorageKey } from "./library/libraryRouteMemory";

vi.mock("./search/LocationRadiusPicker", () => ({
  LocationRadiusPicker: () => <div data-testid="location-radius-picker" />
}));

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
        face_id?: string;
        person_id: string | null;
        bbox_x?: number | null;
        bbox_y?: number | null;
        bbox_w?: number | null;
        bbox_h?: number | null;
        bbox_space_width?: number | null;
        bbox_space_height?: number | null;
        label_source?: "human_confirmed" | "machine_suggested" | null;
        confidence?: number | null;
        suggestions?: Array<{
          person_id: string;
          display_name: string;
          rank: number;
          confidence: number;
          model_version: string | null;
          provenance: Record<string, unknown> | null;
        }>;
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

type PhotoDetailPayload = {
  photo_id: string;
  path: string;
  ext: string;
  camera_make: string | null;
  orientation: string | null;
  shot_ts: string | null;
  filesize: number;
  tags: string[];
  people: string[];
  faces: Array<{
    face_id: string;
    person_id: string | null;
    bbox_x: number | null;
    bbox_y: number | null;
    bbox_w: number | null;
    bbox_h: number | null;
    bbox_space_width?: number | null;
    bbox_space_height?: number | null;
    label_source: "human_confirmed" | "machine_suggested" | null;
    confidence: number | null;
    model_version: string | null;
    provenance: Record<string, unknown> | null;
    label_recorded_ts: string | null;
    suggestions?: Array<{
      person_id: string;
      display_name: string;
      rank: number;
      confidence: number;
      model_version: string | null;
      provenance: Record<string, unknown> | null;
    }>;
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
  } | null;
  metadata: {
    sha256: string;
    phash: string | null;
    shot_ts_source: string | null;
    camera_model: string | null;
    software: string | null;
    gps_latitude: number | null;
    gps_longitude: number | null;
    gps_altitude: number | null;
    exif_attributes: Record<string, unknown> | null;
    created_ts: string;
    updated_ts: string;
    modified_ts: string | null;
    deleted_ts: string | null;
    faces_count: number;
    faces_detected_ts: string | null;
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

function buildPhotoDetailPayload(photoId: string): PhotoDetailPayload {
  return {
    photo_id: photoId,
    path: `/library/${photoId}.jpg`,
    ext: "jpg",
    camera_make: null,
    orientation: null,
    shot_ts: "2026-04-01T12:00:00Z",
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
      sha256: `${photoId}-sha`,
      phash: null,
      shot_ts_source: null,
      camera_model: null,
      software: null,
      gps_latitude: null,
      gps_longitude: null,
      gps_altitude: null,
      exif_attributes: null,
      created_ts: "2026-04-01T12:00:00Z",
      updated_ts: "2026-04-01T12:00:00Z",
      modified_ts: null,
      deleted_ts: null,
      faces_count: 0,
      faces_detected_ts: null
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

function renderLibraryAtStrict(path = "/library") {
  return render(
    <StrictMode>
      <MemoryRouter
        initialEntries={[path]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/library" element={<LibraryRoutePage />} />
        </Routes>
      </MemoryRouter>
    </StrictMode>
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
    window.sessionStorage.clear();
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
    expect(screen.getByRole("button", { name: "Date filter type" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Person filter type" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Location filter type" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Album filter type" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Path hints filter type" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Has faces filter type" })).toBeInTheDocument();
    expect(screen.queryByLabelText("From date")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Date filter type" }));

    expect(screen.getByLabelText("From date")).toBeInTheDocument();
    expect(screen.getByLabelText("To date")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Person filter" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Person filter type" }));

    expect(screen.getByRole("textbox", { name: "Person filter" })).toBeInTheDocument();
    expect(screen.getByLabelText("Person certainty mode")).toBeInTheDocument();
    expect(screen.queryByLabelText("From date")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Location filter type" }));

    expect(screen.getByLabelText("Latitude")).toBeInTheDocument();
    expect(screen.getByLabelText("Longitude")).toBeInTheDocument();
    expect(screen.getByLabelText("Radius (km)")).toBeInTheDocument();
    expect(await screen.findByRole("list", { name: "Photo gallery" })).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Review faces" })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Select photo photo-a" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Show face boxes on all photos" })).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Enable album assignment widgets" })
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View details" })).not.toBeInTheDocument();
  });

  it("opens one filter panel at a time from filter chips", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (input === "/api/v1/albums") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library");
    await screen.findByRole("heading", { name: "Library", level: 1 });

    await user.click(screen.getByRole("button", { name: "Person filter type" }));
    expect(screen.getByLabelText("Person filter")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Album filter type" }));
    expect(screen.queryByLabelText("Person filter")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Done album filters" })).toBeInTheDocument();
  });

  it("reverts date edits on cancel", async () => {
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

    renderLibraryAt("/library?from=2024-01-01&to=2024-01-31");
    await screen.findByRole("heading", { name: "Library", level: 1 });

    await user.click(screen.getByRole("button", { name: "Date filter type" }));
    await user.clear(screen.getByLabelText("From date"));
    await user.type(screen.getByLabelText("From date"), "2024-02-01");
    await user.click(screen.getByRole("button", { name: "Cancel date filters" }));

    await user.click(screen.getByRole("button", { name: "Date filter type" }));
    expect(screen.getByLabelText("From date")).toHaveValue("2024-01-01");
  });

  it("auto-closes date panel when both dates are chosen", async () => {
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
    await screen.findByRole("heading", { name: "Library", level: 1 });

    await user.click(screen.getByRole("button", { name: "Date filter type" }));
    await user.type(screen.getByLabelText("From date"), "2024-01-01");
    await user.type(screen.getByLabelText("To date"), "2024-01-31");

    expect(screen.queryByLabelText("From date")).not.toBeInTheDocument();
  });

  it("applies valid location and closes panel on apply", async () => {
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
    await screen.findByRole("heading", { name: "Library", level: 1 });

    await user.click(screen.getByRole("button", { name: "Location filter type" }));
    await user.type(screen.getByLabelText("Latitude"), "40.7");
    await user.type(screen.getByLabelText("Longitude"), "-74.0");
    await user.type(screen.getByLabelText("Radius (km)"), "3");
    await user.click(screen.getByRole("button", { name: "Apply location filters" }));

    expect(screen.queryByLabelText("Latitude")).not.toBeInTheDocument();
  });

  it("reverts location edits on cancel", async () => {
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

    renderLibraryAt("/library?lat=40.7&lng=-74.0&radiusKm=2");
    await screen.findByRole("heading", { name: "Library", level: 1 });

    await user.click(screen.getByRole("button", { name: "Location filter type" }));
    await user.clear(screen.getByLabelText("Latitude"));
    await user.type(screen.getByLabelText("Latitude"), "12.3");
    await user.click(screen.getByRole("button", { name: "Cancel location filters" }));

    await user.click(screen.getByRole("button", { name: "Location filter type" }));
    expect(screen.getByLabelText("Latitude")).toHaveValue("40.7");
  });

  it("cycles has-faces chip any with without any", async () => {
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
    await screen.findByRole("heading", { name: "Library", level: 1 });

    const chip = screen.getByRole("button", { name: "Has faces filter type" });
    await user.click(chip);
    expect(screen.getByRole("button", { name: "Remove has faces filter with faces" })).toBeInTheDocument();
    await user.click(chip);
    expect(screen.getByRole("button", { name: "Remove has faces filter without faces" })).toBeInTheDocument();
    await user.click(chip);
    expect(screen.queryByText(/has faces:/i)).not.toBeInTheDocument();
  });

  it("shows shared album assignment widgets when enabled", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (input === "/api/v1/albums") {
        return {
          ok: true,
          json: async () => [
            {
              album_id: "album-1",
              name: "Family",
              owner_user_id: "operator-1",
              kind: "editable",
              created_ts: "2026-05-08T12:00:00Z",
              updated_ts: "2026-05-08T12:00:00Z",
              item_count: 3,
              saved_filter: null
            }
          ]
        } as Response;
      }

      if (input === "/api/v1/albums/album-1/items") {
        return {
          ok: true,
          json: async () => ({
            album_id: "album-1",
            added_photo_ids: ["photo-a"],
            duplicate_photo_ids: [],
            missing_photo_ids: []
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Album actions" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Enable album assignment widgets" }));
    expect(await screen.findByRole("region", { name: "Album actions" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Album target"), "album-1");
    await user.click(screen.getByRole("button", { name: "Add 1 photo" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([requestInput]) => String(requestInput) === "/api/v1/albums/album-1/items")
      ).toBe(true);
    });
  });

  it("shows face action widgets when face boxes are enabled", async () => {
    const user = userEvent.setup();
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
      payload.hits.items[0].faces = [
        {
          face_id: "face-1",
          person_id: null
        }
      ];

      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open face 1 actions" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes on all photos" }));
    expect(await screen.findByRole("button", { name: "Open face 1 actions" })).toBeInTheDocument();
  });

  it("does not fan out per-photo detail requests when face boxes are enabled", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      const payload = buildPayload(["photo-a", "photo-b"]);
      payload.hits.items[0].thumbnail = {
        mime_type: "image/jpeg",
        width: 120,
        height: 80,
        data_base64: "dGh1bWI="
      };
      payload.hits.items[1].thumbnail = {
        mime_type: "image/jpeg",
        width: 120,
        height: 80,
        data_base64: "dGh1bWI="
      };
      payload.hits.items[0].faces = [{ face_id: "face-a", person_id: null, bbox_x: 1, bbox_y: 1, bbox_w: 10, bbox_h: 10 }];
      payload.hits.items[1].faces = [{ face_id: "face-b", person_id: null, bbox_x: 1, bbox_y: 1, bbox_w: 10, bbox_h: 10 }];

      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes on all photos" }));

    await screen.findAllByRole("button", { name: "Open face 1 actions" });

    const detailCalls = fetchMock.mock.calls.filter(([requestInput]) => String(requestInput).startsWith("/api/v1/photos/"));
    expect(detailCalls).toHaveLength(0);
  });

  it("requests search face regions when face boxes are enabled", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (input === "/api/v1/search") {
        return {
          ok: true,
          json: async () => buildPayload(["photo-a"])
        } as Response;
      }

      return {
        ok: true,
        json: async () => []
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    const initialSearchCall = fetchMock.mock.calls.find(([requestInput]) => requestInput === "/api/v1/search");
    expect(initialSearchCall).toBeDefined();
    const initialSearchBody = JSON.parse(String(initialSearchCall?.[1]?.body ?? "{}")) as Record<string, unknown>;
    expect(initialSearchBody.include_face_info).toBeUndefined();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes on all photos" }));

    await waitFor(() => {
      const searchCalls = fetchMock.mock.calls.filter(([requestInput]) => requestInput === "/api/v1/search");
      expect(searchCalls.length).toBeGreaterThan(1);
    });

    const searchCalls = fetchMock.mock.calls
      .filter(([requestInput]) => requestInput === "/api/v1/search");
    const latestSearchCall = searchCalls[searchCalls.length - 1];
    const latestSearchBody = JSON.parse(String(latestSearchCall?.[1]?.body ?? "{}")) as Record<string, unknown>;
    expect(latestSearchBody.include_face_info).toBe(true);
  });

  it("keeps face assignment modal open when detail face ids differ from library search payload", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (input === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () => ({
            ...buildPhotoDetailPayload("photo-a"),
            faces: [
              {
                face_id: "face-real-1",
                person_id: null,
                bbox_x: 12,
                bbox_y: 14,
                bbox_w: 20,
                bbox_h: 24,
                bbox_space_width: 120,
                bbox_space_height: 80,
                label_source: null,
                confidence: null,
                model_version: null,
                provenance: null,
                label_recorded_ts: null,
                suggestions: []
              }
            ],
            thumbnail: {
              mime_type: "image/jpeg",
              width: 120,
              height: 80,
              data_base64: "dGh1bWI="
            }
          })
        } as Response;
      }

      const payload = buildPayload(["photo-a"]);
      payload.hits.items[0].thumbnail = {
        mime_type: "image/jpeg",
        width: 120,
        height: 80,
        data_base64: "dGh1bWI="
      };
      payload.hits.items[0].faces = [
        {
          person_id: null,
          bbox_x: 0.1,
          bbox_y: 0.2,
          bbox_w: 0.2,
          bbox_h: 0.2
        }
      ];

      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes on all photos" }));
    await user.click(await screen.findByRole("button", { name: "Open face 1 actions" }));

    expect(await screen.findByRole("dialog", { name: "Face assignment" })).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([requestInput]) => String(requestInput) === "/api/v1/photos/photo-a")
    ).toBe(false);
    expect(screen.getByRole("dialog", { name: "Face assignment" })).toBeInTheDocument();
  });

  it("updates face label locally after saving assignment from the modal", async () => {
    const user = userEvent.setup();
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
          json: async () => [
            {
              person_id: "person-1",
              display_name: "Inez",
              created_ts: "2026-05-09T12:00:00Z",
              updated_ts: "2026-05-09T12:00:00Z"
            }
          ]
        } as Response;
      }

      if (url === "/api/v1/faces/face-1/candidates?enforce_min_confidence=false") {
        return {
          ok: true,
          json: async () => ({
            face_id: "face-1",
            candidates: [
              {
                person_id: "person-1",
                display_name: "Inez",
                matched_face_id: "face-7",
                distance: 0.11,
                confidence: 0.88
              }
            ],
            suggestion_policy: {
              decision: "review_needed",
              review_threshold: 0.5,
              auto_accept_threshold: 0.9,
              top_candidate_confidence: 0.88
            },
            review_needed_suggestion: null,
            auto_applied_assignment: null
          })
        } as Response;
      }

      if (url === "/api/v1/faces/face-1/assignments" && init?.method === "POST") {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            face_id: "face-1",
            photo_id: "photo-a",
            person_id: "person-1"
          })
        } as Response;
      }

      const payload = buildPayload(["photo-a"]);
      payload.hits.items[0].thumbnail = {
        mime_type: "image/jpeg",
        width: 120,
        height: 80,
        data_base64: "dGh1bWI="
      };
      payload.hits.items[0].faces = [
        {
          face_id: "face-1",
          person_id: null,
          bbox_x: 10,
          bbox_y: 10,
          bbox_w: 30,
          bbox_h: 30,
          bbox_space_width: 120,
          bbox_space_height: 80,
          suggestions: [
            {
              person_id: "person-top",
              display_name: "Alex",
              rank: 1,
              confidence: 0.92,
              model_version: "recognition-v1",
              provenance: null
            }
          ]
        }
      ];

      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes on all photos" }));
    const openFaceButton = await screen.findByRole("button", { name: "Open face 1 actions" });
    expect(openFaceButton).toHaveTextContent("Alex");

    await user.click(openFaceButton);
    expect(await screen.findByRole("dialog", { name: "Face assignment" })).toBeInTheDocument();

    const assignPersonInput = screen.getByLabelText("Assign person");
    await user.clear(assignPersonInput);
    await user.type(assignPersonInput, "Inez");
    await user.click(screen.getByRole("button", { name: "Save and close" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Face assignment" })).not.toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: "Open face 1 actions" })).toHaveTextContent("Inez");
    expect(
      fetchMock.mock.calls.some(([requestInput]) => String(requestInput) === "/api/v1/photos/photo-a")
    ).toBe(false);
  });

  it("deduplicates initial strict-mode service requests", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/search") {
        await new Promise((resolve) => setTimeout(resolve, 1));
        return {
          ok: true,
          json: async () => buildPayload(["photo-a"])
        } as Response;
      }
      if (url === "/api/v1/operations/activity") {
        await new Promise((resolve) => setTimeout(resolve, 1));
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }
      if (url === "/api/v1/people") {
        await new Promise((resolve) => setTimeout(resolve, 1));
        return {
          ok: true,
          json: async () => []
        } as Response;
      }
      if (url === "/api/v1/albums") {
        await new Promise((resolve) => setTimeout(resolve, 1));
        return {
          ok: true,
          json: async () => []
        } as Response;
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAtStrict("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await waitFor(() => {
      const requests = fetchMock.mock.calls.map(([requestInput]) => String(requestInput));
      expect(requests.filter((url) => url === "/api/v1/search")).toHaveLength(1);
      expect(requests.filter((url) => url === "/api/v1/operations/activity")).toHaveLength(1);
      expect(requests.filter((url) => url === "/api/v1/people")).toHaveLength(1);
      expect(requests.filter((url) => url === "/api/v1/albums")).toHaveLength(1);
    });
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

  it("keeps library photo selection while opening metadata from a shared photo surface", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }
      if (url === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () => buildPhotoDetailPayload("photo-a")
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library");

    const selection = await screen.findByRole("checkbox", { name: "Select photo photo-a" });
    await user.click(selection);
    await user.click(screen.getByRole("button", { name: "Show metadata for photo-a.jpg" }));

    expect(screen.getByRole("checkbox", { name: "Select photo photo-a" })).toBeChecked();
    expect(
      await screen.findByRole("complementary", { name: "Metadata for photo-a.jpg" })
    ).toBeInTheDocument();
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

  it("shows consolidated face summary on cards", async () => {
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
        { person_id: "person-2", label_source: "human_confirmed", confidence: null },
        {
          person_id: null,
          label_source: null,
          confidence: null,
          suggestions: [
            {
              person_id: "person-1",
              display_name: "Alex",
              rank: 1,
              confidence: 0.82,
              model_version: "recognition-v1",
              provenance: null
            }
          ]
        },
        {
          person_id: null,
          label_source: null,
          confidence: null,
          suggestions: [
            {
              person_id: "person-2",
              display_name: "Blair",
              rank: 1,
              confidence: 0.79,
              model_version: "recognition-v1",
              provenance: null
            }
          ]
        }
      ];
      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    expect(screen.queryByText(/Faces detected\/assigned:/i)).not.toBeInTheDocument();
    expect(screen.queryByText("People assigned (human)")).not.toBeInTheDocument();
    expect(screen.queryByText("Machine suggestions")).not.toBeInTheDocument();
  });

  it("applies certainty mode and threshold when adding a person filter", async () => {
    const user = userEvent.setup();

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
          json: async () => [{ person_id: "person-inez", display_name: "Inez Rivera" }]
        } as Response;
      }

      if (url !== "/api/v1/search") {
        throw new Error(`Unhandled fetch: ${url}`);
      }

      const payload = buildPayload(["photo-a"]);
      return {
        ok: true,
        json: async () => payload
      } as Response;
    });

    renderLibraryAt("/library?page=2");

    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Person filter type" }));
    await user.selectOptions(screen.getByLabelText("Person certainty mode"), "include_suggestions");
    const suggestionThresholdSlider = screen.getByRole("slider", { name: "Suggestion threshold" });
    suggestionThresholdSlider.focus();
    await user.keyboard("{PageUp}{ArrowRight}");
    await user.type(screen.getByRole("textbox", { name: "Person filter" }), "inez");
    await user.click(screen.getByRole("button", { name: "Add person filter" }));
    expect(
      await screen.findByRole("button", { name: "Remove person Inez Rivera with 91% certainty" })
    ).toBeInTheDocument();
    expect(screen.getByText("person: Inez Rivera (91%)")).toBeInTheDocument();

    await waitFor(() => {
      const searchBodies = fetchMock.mock.calls
        .filter(([requestInput]) => String(requestInput) === "/api/v1/search")
        .map(([, requestInit]) =>
          JSON.parse((requestInit?.body as string | undefined) ?? "{}") as {
            filters?: {
              person_names?: string[];
              person_certainty_mode?: string;
              suggestion_confidence_min?: number;
            };
          }
        );

      const personFilterRequest = searchBodies.find(
        (body) => body.filters?.person_names?.includes("Inez Rivera")
      );

      expect(personFilterRequest).toEqual(
        expect.objectContaining({
          filters: expect.objectContaining({
            person_certainty_mode: "include_suggestions",
            suggestion_confidence_min: 0.91
          })
        })
      );
    });
  });

  it("shows album filter controls and chips with album names", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (url === "/api/v1/albums") {
        return {
          ok: true,
          json: async () => [
            {
              album_id: "album-1",
              name: "Family Trip",
              owner_user_id: "operator-1",
              kind: "editable",
              created_ts: "2026-05-08T12:00:00Z",
              updated_ts: "2026-05-08T12:00:00Z",
              item_count: 3,
              saved_filter: null
            }
          ]
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
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library?album=album-1");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("album: Family Trip")).toBeInTheDocument();
    expect(screen.queryByText("album: album-1")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Album filter type" }));
    expect(screen.getByRole("button", { name: "album: Family Trip" })).toBeInTheDocument();
  });

  it("shows 100% certainty on person chips for human-only mode", async () => {
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
          json: async () => [{ person_id: "person-inez", display_name: "Inez Rivera" }]
        } as Response;
      }

      if (url !== "/api/v1/search") {
        throw new Error(`Unhandled fetch: ${url}`);
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-a"])
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Person filter type" }));
    await user.type(screen.getByRole("textbox", { name: "Person filter" }), "inez");
    await user.click(screen.getByRole("button", { name: "Add person filter" }));

    expect(
      await screen.findByRole("button", { name: "Remove person Inez Rivera with 100% certainty" })
    ).toBeInTheDocument();
    expect(screen.getByText("person: Inez Rivera (100%)")).toBeInTheDocument();
  });

  it("advances to the next offset-backed page when Next is clicked", async () => {
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
        page?: { offset?: number };
      };
      const requestOffset = requestBody.page?.offset ?? 0;

      if (requestOffset === 60) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 181,
              cursor: null,
              items: buildPayload(pageTwoIds, 181).hits.items
            }
          })
        } as Response;
      }

      if (requestOffset === 120) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 181,
              cursor: null,
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
            cursor: null,
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
    const pageThreeButton = await screen.findByRole("button", { name: "Page 3" });
    await waitFor(() => {
      expect(pageThreeButton).toHaveAttribute("aria-current", "page");
    });

    const searchRequestOffsets = fetchMock.mock.calls
      .filter(([input]) => String(input) === "/api/v1/search")
      .map(([, init]) => {
        const parsedBody = JSON.parse((init?.body as string | undefined) ?? "{}") as {
          page?: { offset?: number };
        };
        return parsedBody.page?.offset ?? 0;
      });

    expect(searchRequestOffsets).toContain(60);
    expect(searchRequestOffsets).toContain(120);
  });

  it("jumps directly to a requested page using offset", async () => {
    const user = userEvent.setup();
    const pageOneIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 1}`);
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
        page?: { offset?: number };
      };
      const requestOffset = requestBody.page?.offset ?? 0;
      if (requestOffset === 120) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 241,
              cursor: null,
              items: buildPayload(pageThreeIds, 241).hits.items
            }
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 241,
            cursor: null,
            items: buildPayload(pageOneIds, 241).hits.items
          }
        })
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByText("Showing 60 of 241 photos")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Page 3" }));
    expect(await screen.findByRole("button", { name: "Page 3" })).toHaveAttribute(
      "aria-current",
      "page"
    );

    const searchRequestOffsets = fetchMock.mock.calls
      .filter(([input]) => String(input) === "/api/v1/search")
      .map(([, init]) => {
        const parsedBody = JSON.parse((init?.body as string | undefined) ?? "{}") as {
          page?: { offset?: number };
        };
        return parsedBody.page?.offset ?? 0;
      });

    expect(searchRequestOffsets).toContain(120);
    expect(searchRequestOffsets.filter((offset) => offset === 120)).toHaveLength(1);
  });

  it("updates search page limit when photos-per-page selector changes", async () => {
    const user = userEvent.setup();

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
        page?: { offset?: number };
      };
      const requestOffset = requestBody.page?.offset ?? 0;
      if (requestOffset === 60) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 121,
              cursor: null,
              items: buildPayload(Array.from({ length: 60 }, (_, index) => `photo-${index + 61}`), 121).hits.items
            }
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 121,
            cursor: null,
            items: buildPayload(Array.from({ length: 60 }, (_, index) => `photo-${index + 1}`), 121).hits.items
          }
        })
      } as Response;
    });

    renderLibraryAt("/library");
    expect(await screen.findByText("Showing 60 of 121 photos")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("button", { name: "Page 2" })).toHaveAttribute(
      "aria-current",
      "page"
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "Photos per page" }), "24");
    const pageThreeButton = await screen.findByRole("button", { name: "Page 3" });
    await waitFor(() => {
      expect(pageThreeButton).toHaveAttribute("aria-current", "page");
    });

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
        page?: { offset?: number };
      };
      const requestOffset = requestBody.page?.offset ?? 0;

      if (requestOffset === 60) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 121,
              cursor: null,
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
            cursor: null,
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

  it("keeps selected page size when navigating to detail and back", async () => {
    const user = userEvent.setup();
    const pageOneIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 1}`);
    const pageTwoIds = Array.from({ length: 60 }, (_, index) => `photo-${index + 61}`);
    const pageThreeIds = Array.from({ length: 24 }, (_, index) => `photo-${index + 49}`);

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
        page?: { offset?: number };
      };
      const requestOffset = requestBody.page?.offset ?? 0;

      if (requestOffset === 60) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 121,
              cursor: null,
              items: buildPayload(pageTwoIds, 121).hits.items
            }
          })
        } as Response;
      }

      if (requestOffset === 48) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 121,
              cursor: null,
              items: buildPayload(pageThreeIds, 121).hits.items
            }
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 121,
            cursor: null,
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

    await user.selectOptions(screen.getByRole("combobox", { name: "Photos per page" }), "24");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Page 3" })).toHaveAttribute(
        "aria-current",
        "page"
      );
    });

    await user.click(screen.getByRole("link", { name: "Open details for /library/photo-61.jpg" }));
    expect(await screen.findByRole("heading", { name: "Library test detail", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Back to library" }));

    expect(await screen.findByRole("button", { name: "Page 3" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getByRole("combobox", { name: "Photos per page" })).toHaveValue("24");
  });

  it("restores a selected page on fresh reload from session storage", async () => {
    const pageOneIds = Array.from({ length: 24 }, (_, index) => `photo-${index + 1}`);
    const pageTwoIds = Array.from({ length: 24 }, (_, index) => `photo-${index + 25}`);
    const initialSearch = "?page=2&pageSize=24&sort=asc";

    window.sessionStorage.setItem(
      buildLibraryViewStateStorageKey(initialSearch),
      JSON.stringify({
        sortDirection: "asc",
        page: 2,
        pageSize: 24
      })
    );

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
        page?: { offset?: number };
      };
      const requestOffset = requestBody.page?.offset ?? 0;

      if (requestOffset === 24) {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 48,
              cursor: null,
              items: buildPayload(pageTwoIds, 48).hits.items
            }
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 48,
            cursor: null,
            items: buildPayload(pageOneIds, 48).hits.items
          }
        })
      } as Response;
    });

    renderLibraryAt(`/library${initialSearch}`);

    expect(await screen.findByRole("button", { name: "Page 2" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getByRole("checkbox", { name: "Select photo photo-25" })).toBeInTheDocument();
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

  it("opens add-to-album modal with editable and saved-filter options", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }
      if (url === "/api/v1/search") {
        return {
          ok: true,
          json: async () => buildPayload(["photo-a"])
        } as Response;
      }
      if (url === "/api/v1/albums") {
        return {
          ok: true,
          json: async () => ({
            album_id: "album-2",
            name: "Needs review",
            owner_user_id: "operator-1",
            kind: "saved_filter",
            created_ts: "2026-05-07T12:00:00Z",
            updated_ts: "2026-05-07T12:00:00Z",
            item_count: 0,
            saved_filter: { person_names: ["Inez"] }
          })
        } as Response;
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "This page" }));
    await user.click(screen.getByRole("button", { name: "Add to album" }));

    expect(await screen.findByRole("radio", { name: "Editable" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Saved Filter" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Album type info" })).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Saved Filter" }));
    await user.clear(screen.getByLabelText("Album name"));
    await user.type(screen.getByLabelText("Album name"), "Needs review");
    await user.click(screen.getByRole("button", { name: "Save to album" }));

    let createCall: [RequestInfo | URL, RequestInit | undefined] | undefined;
    await waitFor(() => {
      createCall = fetchMock.mock.calls.find(
        ([requestInput, requestInit]) =>
          String(requestInput) === "/api/v1/albums" && requestInit?.method === "POST"
      ) as [RequestInfo | URL, RequestInit | undefined] | undefined;
      expect(createCall).toBeDefined();
    });
    const createBody = JSON.parse((createCall?.[1]?.body as string | undefined) ?? "{}") as {
      name?: string;
      kind?: string;
      filter_json?: Record<string, unknown>;
    };
    expect(createBody.name).toBe("Needs review");
    expect(createBody.kind).toBe("saved_filter");
    expect(createBody.filter_json).toBeDefined();

    expect(
      await screen.findByText('Saved-filter album "Needs review" created from active filters.')
    ).toBeInTheDocument();
  });

  it("exports the active selection as a zip file", async () => {
    const user = userEvent.setup();
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
    const createObjectUrlSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:photo-export");
    const revokeObjectUrlSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }
      if (url === "/api/v1/search") {
        return {
          ok: true,
          json: async () => buildPayload(["photo-a"])
        } as Response;
      }
      if (url === "/api/v1/exports/photos") {
        return new Response(new Blob([new Uint8Array([1, 2, 3])], { type: "application/zip" }), {
          status: 200,
          headers: {
            "Content-Type": "application/zip",
            "Content-Disposition": 'attachment; filename="library-export.zip"',
            "X-Photo-Org-Exported-Count": "1",
            "X-Photo-Org-Skipped-Count": "0"
          }
        });
      }
      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "This page" }));
    await user.click(screen.getByRole("button", { name: "Export" }));

    expect(createObjectUrlSpy).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:photo-export");
    expect(
      await screen.findByText("Export completed: 1 photo, 0 skipped.")
    ).toBeInTheDocument();
  });
});
