import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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
      };
    }>;
  };
};

type PhotoDetailPayload = {
  photo_id: string;
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
  }>;
  thumbnail: {
    mime_type: string;
    width: number;
    height: number;
    data_base64: string;
  } | null;
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

function buildDetailPayload(
  faces: PhotoDetailPayload["faces"],
  photoId = "photo-a"
): PhotoDetailPayload {
  return {
    photo_id: photoId,
    faces,
    thumbnail: {
      mime_type: "image/jpeg",
      width: 100,
      height: 100,
      data_base64: "dGh1bWI="
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

  it("renders library query controls and results scaffold on /library", async () => {
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
    expect(screen.queryByRole("heading", { name: "Ingest status legend" })).not.toBeInTheDocument();
    expect(screen.getByTitle(/Complete: Assets are ready for normal browse\/detail viewing\./)).toBeInTheDocument();
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
      name: "View details for /library/photo-a.jpg"
    });

    expect(thumbnailLink).toHaveAttribute("href", "/library/photo-a");
  });

  it("loads and toggles face bbox overlays for an individual grid photo", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (url === "/api/v1/search") {
        const payload = buildPayload(["photo-a"], 1, true);
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
      }

      if (url === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () =>
            buildDetailPayload([
              {
                face_id: "face-1",
                person_id: "person-1",
                bbox_x: 10,
                bbox_y: 10,
                bbox_w: 20,
                bbox_h: 20,
                label_source: null,
                confidence: null,
                model_version: null,
                provenance: null,
                label_recorded_ts: null
              }
            ])
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Detected face regions for photo-a" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes for photo-a" }));
    expect(await screen.findByRole("list", { name: "Detected face regions for photo-a" })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes for photo-a" }));
    expect(screen.queryByRole("list", { name: "Detected face regions for photo-a" })).not.toBeInTheDocument();
  });

  it("supports a global face bbox toggle for all grid photos", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/operations/activity") {
        return {
          ok: true,
          json: async () => ({ ingest_queue: { summary: { processing_count: 0 } } })
        } as Response;
      }

      if (url === "/api/v1/search") {
        const payload = buildPayload(["photo-a"], 1, true);
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
      }

      if (url === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () =>
            buildDetailPayload([
              {
                face_id: "face-1",
                person_id: "person-1",
                bbox_x: 10,
                bbox_y: 10,
                bbox_w: 20,
                bbox_h: 20,
                label_source: null,
                confidence: null,
                model_version: null,
                provenance: null,
                label_recorded_ts: null
              }
            ])
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Detected face regions for photo-a" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes on all photos" }));
    expect(await screen.findByRole("list", { name: "Detected face regions for photo-a" })).toBeInTheDocument();
  });

  it("advances to the next cursor-backed page when Next is clicked", async () => {
    const user = userEvent.setup();

    const pageOneIds = Array.from({ length: 24 }, (_, index) => `photo-${index + 1}`);
    const pageTwoIds = Array.from({ length: 24 }, (_, index) => `photo-${index + 25}`);
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
        page?: { cursor?: string | null };
      };
      const requestCursor = requestBody.page?.cursor ?? null;

      if (requestCursor === "cursor-page-2") {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 99,
              cursor: "cursor-page-3",
              items: buildPayload(pageTwoIds, 99).hits.items
            }
          })
        } as Response;
      }

      if (requestCursor === "cursor-page-3") {
        return {
          ok: true,
          json: async () => ({
            hits: {
              total: 99,
              cursor: "cursor-page-4",
              items: buildPayload(pageThreeIds, 99).hits.items
            }
          })
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          hits: {
            total: 99,
            cursor: "cursor-page-2",
            items: buildPayload(pageOneIds, 99).hits.items
          }
        })
      } as Response;
    });

    renderLibraryAt("/library");

    expect(await screen.findByText("Showing 24 of 99 photos")).toBeInTheDocument();
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
    const detailLinks = await screen.findAllByRole("link", { name: "View details" });
    expect(detailLinks.length).toBeGreaterThan(0);

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

  it("shows action bar only when active selection scope count is positive", async () => {
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

    const selectionCheckbox = await screen.findByRole("checkbox", { name: "Select photo" });
    await user.click(selectionCheckbox);
    expect(screen.getByLabelText("Library actions")).toBeInTheDocument();
  });

  it("disables both actions while operations conflict is active", async () => {
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

    const selectionCheckbox = await screen.findByRole("checkbox", { name: "Select photo" });
    await user.click(selectionCheckbox);

    expect(screen.getByRole("button", { name: "Add to album" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Export" })).toBeDisabled();
    expect(
      screen.getAllByText("Action temporarily unavailable while ingest processing is active.")
        .length
    ).toBeGreaterThan(0);
  });

  it("supports in-context face assignment from the library quick panel", async () => {
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
          json: async () => buildPayload(["photo-a"], 1, true)
        } as Response;
      }

      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => [{ person_id: "person-1", display_name: "Inez" }]
        } as Response;
      }

      if (url === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () =>
            buildDetailPayload([
              {
                face_id: "face-1",
                person_id: null,
                bbox_x: 10,
                bbox_y: 10,
                bbox_w: 20,
                bbox_h: 20,
                label_source: null,
                confidence: null,
                model_version: null,
                provenance: null,
                label_recorded_ts: null
              }
            ])
        } as Response;
      }

      if (url === "/api/v1/faces/face-1/assignments" && init?.method === "POST") {
        return {
          ok: true,
          status: 201,
          json: async () => ({ face_id: "face-1", photo_id: "photo-a", person_id: "person-1" })
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Review faces" }));
    await user.selectOptions(await screen.findByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("All visible faces assigned.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/faces/face-1/assignments", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Face-Validation-Role": "contributor"
      },
      body: JSON.stringify({ person_id: "person-1" })
    });
  });

  it("renders quick-panel overlays when bbox coordinates are larger than thumbnail dimensions", async () => {
    const user = userEvent.setup();

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
          json: async () => buildPayload(["photo-a"], 1, true)
        } as Response;
      }

      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => [{ person_id: "person-1", display_name: "Inez" }]
        } as Response;
      }

      if (url === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () =>
            buildDetailPayload([
              {
                face_id: "face-1",
                person_id: "person-1",
                bbox_x: 320,
                bbox_y: 160,
                bbox_w: 120,
                bbox_h: 140,
                label_source: null,
                confidence: null,
                model_version: null,
                provenance: null,
                label_recorded_ts: null
              }
            ])
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Review faces" }));

    expect(await screen.findByText("1 face region rendered.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Detected face regions" })).toBeInTheDocument();
    expect(
      screen.queryByText("Face regions are present but could not be rendered on this preview.")
    ).not.toBeInTheDocument();
  });

  it("maps quick-panel overlays using explicit bbox coordinate-space dimensions", async () => {
    const user = userEvent.setup();

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
          json: async () => buildPayload(["photo-a"], 1, true)
        } as Response;
      }

      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => [{ person_id: "person-1", display_name: "Inez" }]
        } as Response;
      }

      if (url === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () =>
            buildDetailPayload([
              {
                face_id: "face-1",
                person_id: "person-1",
                bbox_x: 1000,
                bbox_y: 300,
                bbox_w: 800,
                bbox_h: 600,
                bbox_space_width: 4000,
                bbox_space_height: 3000,
                label_source: null,
                confidence: null,
                model_version: null,
                provenance: null,
                label_recorded_ts: null
              }
            ])
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Review faces" }));

    const region = await screen.findByLabelText("Face region 1 for person-1");
    expect(region).toHaveStyle({
      left: "25%",
      top: "10%",
      width: "20%",
      height: "20%"
    });
  });

  it("supports in-context correction and machine-label confirmation from the library quick panel", async () => {
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
          json: async () => buildPayload(["photo-a"], 1, true)
        } as Response;
      }

      if (url === "/api/v1/people") {
        return {
          ok: true,
          json: async () => [
            { person_id: "person-1", display_name: "Inez" },
            { person_id: "person-2", display_name: "Mateo" }
          ]
        } as Response;
      }

      if (url === "/api/v1/photos/photo-a") {
        return {
          ok: true,
          json: async () =>
            buildDetailPayload([
              {
                face_id: "face-1",
                person_id: "person-1",
                bbox_x: 10,
                bbox_y: 10,
                bbox_w: 20,
                bbox_h: 20,
                label_source: "machine_suggested",
                confidence: 0.92,
                model_version: "v1",
                provenance: {
                  workflow: "face-labeling",
                  surface: "api",
                  action: "auto-apply"
                },
                label_recorded_ts: "2026-05-02T10:00:00Z"
              }
            ])
        } as Response;
      }

      if (url === "/api/v1/faces/face-1/confirmations" && init?.method === "POST") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ face_id: "face-1", photo_id: "photo-a", person_id: "person-1" })
        } as Response;
      }

      if (url === "/api/v1/faces/face-1/corrections" && init?.method === "POST") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            face_id: "face-1",
            photo_id: "photo-a",
            previous_person_id: "person-1",
            person_id: "person-2"
          })
        } as Response;
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });

    renderLibraryAt("/library");
    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Review faces" }));

    await user.click(await screen.findByRole("button", { name: "Confirm label" }));
    expect(await screen.findByText("Confirmed face 1 for Inez.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/faces/face-1/confirmations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Face-Validation-Role": "contributor"
      },
      body: JSON.stringify({ person_id: "person-1" })
    });

    await user.selectOptions(screen.getByLabelText("Correct face 1"), "person-2");
    await user.click(screen.getByRole("button", { name: "Confirm reassignment" }));
    expect(await screen.findByText("Correction recorded: Inez -> Mateo.")).toBeInTheDocument();
  });

  it("shows the Review faces action only when faces are detected", async () => {
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
    expect(screen.queryByRole("button", { name: "Review faces" })).not.toBeInTheDocument();
  });
});
