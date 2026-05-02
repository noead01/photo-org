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
      thumbnail: null;
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
    label_source: "human_confirmed" | "machine_applied" | "machine_suggested" | null;
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
        filesize: 1024 + index,
        people: [],
        faces: [],
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
    expect(screen.getByLabelText("From date")).toBeInTheDocument();
    expect(screen.getByLabelText("To date")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Person filter" })).toBeInTheDocument();
    expect(screen.getByLabelText("Latitude")).toBeInTheDocument();
    expect(screen.getByLabelText("Longitude")).toBeInTheDocument();
    expect(screen.getByLabelText("Radius (km)")).toBeInTheDocument();
    expect(screen.getByLabelText("Facet filters")).toBeInTheDocument();
    expect(await screen.findByRole("list", { name: "Photo gallery" })).toBeInTheDocument();
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
          json: async () => buildPayload(["photo-a"])
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

    await user.click(screen.getByRole("button", { name: "Show face workflow" }));
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
          json: async () => buildPayload(["photo-a"])
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
                label_source: "machine_applied",
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

    await user.click(screen.getByRole("button", { name: "Show face workflow" }));

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
});
