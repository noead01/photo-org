import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { PhotoDetailRoutePage } from "./PhotoDetailRoutePage";

interface PhotoDetailPayload {
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
    created_ts: string;
    updated_ts: string;
    modified_ts: string | null;
    deleted_ts: string | null;
    faces_count: number;
    faces_detected_ts: string | null;
  };
}

function buildPayload(partial: Partial<PhotoDetailPayload> = {}): PhotoDetailPayload {
  return {
    photo_id: "photo-1",
    path: "/library/photo-1.jpg",
    ext: "jpg",
    camera_make: "Apple",
    orientation: "Rotate 90 CW",
    shot_ts: "2026-03-28T19:30:00Z",
    filesize: 4096,
    tags: ["vacation"],
    people: ["person-1"],
    faces: [
      {
        face_id: "face-1",
        person_id: "person-1",
        bbox_x: 10,
        bbox_y: 20,
        bbox_w: 30,
        bbox_h: 40,
        label_source: null,
        confidence: null,
        model_version: null,
        provenance: null,
        label_recorded_ts: null
      }
    ],
    thumbnail: {
      mime_type: "image/jpeg",
      width: 100,
      height: 100,
      data_base64: "dGh1bWI="
    },
    original: {
      is_available: true,
      availability_state: "active",
      last_failure_reason: null
    },
    metadata: {
      sha256: "sha-1",
      phash: "phash-1",
      shot_ts_source: "exif:DateTimeOriginal",
      camera_model: "iPhone 15 Pro",
      software: "18.1",
      gps_latitude: 12.3456,
      gps_longitude: -45.6789,
      gps_altitude: 123.4,
      created_ts: "2026-03-28T19:30:00Z",
      updated_ts: "2026-03-28T19:30:00Z",
      modified_ts: "2026-03-28T19:30:00Z",
      deleted_ts: null,
      faces_count: 1,
      faces_detected_ts: "2026-03-28T19:30:00Z"
    },
    ...partial
  };
}

function renderDetail(path = "/library/photo-1") {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/library/:photoId" element={<PhotoDetailRoutePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("PhotoDetailRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input) => {
      if (String(input) === "/api/v1/people") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }

      return {
        ok: false,
        status: 500
      } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders detail metadata fields from the backend contract", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("photo-1")).toBeInTheDocument();
    expect(screen.getByText("/library/photo-1.jpg")).toBeInTheDocument();
    expect(screen.getByText("iPhone 15 Pro")).toBeInTheDocument();
    expect(screen.getByText("exif:DateTimeOriginal")).toBeInTheDocument();
    expect(screen.getByText("12.3456, -45.6789")).toBeInTheDocument();
    expect(screen.getByText("1 detected")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Preview for photo-1" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Detected face regions" })).toBeInTheDocument();
    expect(screen.getByLabelText("Face region 1 for person-1")).toBeInTheDocument();

    const photoDetailCalls = fetchMock.mock.calls.filter((call) => call[0] === "/api/v1/photos/photo-1");
    expect(photoDetailCalls).toHaveLength(1);
  });

  it("shows explicit fallback UI for missing optional metadata fields", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          shot_ts: null,
          camera_make: null,
          orientation: null,
          tags: [],
          people: [],
          original: null,
          metadata: {
            ...buildPayload().metadata,
            phash: null,
            shot_ts_source: null,
            camera_model: null,
            software: null,
            gps_latitude: null,
            gps_longitude: null,
            gps_altitude: null,
            modified_ts: null,
            faces_detected_ts: null
          }
        })
    } as Response);

    renderDetail();

    expect((await screen.findAllByText("Not available")).length).toBeGreaterThan(0);
    expect(screen.getByText("No tags")).toBeInTheDocument();
    expect(screen.getByText("No recognized people")).toBeInTheDocument();
    expect(screen.getByText("Unknown availability")).toBeInTheDocument();
    expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
  });

  it("shows explicit no-face state when no face regions are present", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          faces: [],
          people: [],
          metadata: {
            ...buildPayload().metadata,
            faces_count: 0
          }
        })
    } as Response);

    renderDetail();

    expect(await screen.findByText("No face regions detected for this photo.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Detected face regions" })).not.toBeInTheDocument();
  });

  it("keeps face overlays coherent when switching image presentation mode", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    expect(await screen.findByLabelText("Face region 1 for person-1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Actual pixels" }));

    expect(await screen.findByLabelText("Face region 1 for person-1")).toBeInTheDocument();
  });

  it("loads people options and updates local face state after assignment success", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          buildPayload({
            people: [],
            faces: [
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
            ]
          })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            person_id: "person-1",
            display_name: "Inez",
            created_ts: "2026-03-28T19:30:00Z",
            updated_ts: "2026-03-28T19:30:00Z"
          }
        ]
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({
          face_id: "face-1",
          photo_id: "photo-1",
          person_id: "person-1"
        })
      } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    await user.selectOptions(await screen.findByLabelText("Assign face 1"), "person-1");

    expect(await screen.findByText("All visible faces assigned.")).toBeInTheDocument();
    expect(screen.getByText("person-1")).toBeInTheDocument();
  });

  it("updates local face state after correction success and shows correction provenance", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          buildPayload({
            people: ["person-1"],
            faces: [
              {
                face_id: "face-1",
                person_id: "person-1",
                bbox_x: 10,
                bbox_y: 10,
                bbox_w: 20,
                bbox_h: 20,
                label_source: "human_confirmed",
                confidence: null,
                model_version: null,
                provenance: {
                  workflow: "face-labeling",
                  surface: "api",
                  action: "correction"
                },
                label_recorded_ts: "2026-03-28T19:33:00Z"
              }
            ]
          })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            person_id: "person-1",
            display_name: "Inez",
            created_ts: "2026-03-28T19:30:00Z",
            updated_ts: "2026-03-28T19:30:00Z"
          },
          {
            person_id: "person-2",
            display_name: "Mateo",
            created_ts: "2026-03-28T19:30:00Z",
            updated_ts: "2026-03-28T19:30:00Z"
          }
        ]
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          face_id: "face-1",
          photo_id: "photo-1",
          previous_person_id: "person-1",
          person_id: "person-2"
        })
      } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    await user.selectOptions(await screen.findByLabelText("Correct face 1"), "person-2");
    await user.click(screen.getByRole("button", { name: "Confirm reassignment" }));

    expect(await screen.findByText("Correction recorded: Inez -> Mateo.")).toBeInTheDocument();
    expect(screen.getByText("Face 1: Mateo")).toBeInTheDocument();
    expect(screen.getByText("person-2")).toBeInTheDocument();
  });

  it("opens inline provenance details when overlay provenance badge is clicked", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          buildPayload({
            faces: [
              {
                face_id: "face-1",
                person_id: "person-1",
                bbox_x: 10,
                bbox_y: 10,
                bbox_w: 20,
                bbox_h: 20,
                label_source: "human_confirmed",
                confidence: null,
                model_version: null,
                provenance: {
                  workflow: "face-labeling",
                  surface: "api",
                  action: "correction"
                },
                label_recorded_ts: "2026-03-28T19:33:00Z"
              }
            ]
          })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            person_id: "person-1",
            display_name: "Inez",
            created_ts: "2026-03-28T19:30:00Z",
            updated_ts: "2026-03-28T19:30:00Z"
          }
        ]
      } as Response);

    renderDetail();

    expect(await screen.findByLabelText("Face region 1 for person-1")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show provenance details for face region 1" }));

    expect(await screen.findByLabelText("Provenance details for face 1")).toBeInTheDocument();
    expect(screen.getByText("Human confirmed")).toBeInTheDocument();
    expect(screen.getByText("correction")).toBeInTheDocument();
  });

  it("renders deterministic loading and error transitions", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503
    } as Response);

    renderDetail();

    expect(screen.getByText("Loading photo detail.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Could not load photo detail", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Photo detail request failed (503)")).toBeInTheDocument();
  });

  it("retries loading after a failed request", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: false,
        status: 500
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload()
      } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Could not load photo detail", level: 2 })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    });
    const photoDetailCalls = fetchMock.mock.calls.filter((call) => call[0] === "/api/v1/photos/photo-1");
    expect(photoDetailCalls).toHaveLength(2);
  });

  it("renders pending ingest status when face detection is still in progress", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          original: {
            is_available: true,
            availability_state: "active",
            last_failure_reason: null
          },
          metadata: {
            ...buildPayload().metadata,
            faces_detected_ts: null
          }
        })
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Ingest status legend")).toBeInTheDocument();
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
  });

  it("moves keyboard focus to the detail heading when opened", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    const heading = await screen.findByRole("heading", { name: "Photo detail", level: 1 });
    await waitFor(() => {
      expect(heading).toHaveFocus();
    });
  });

  it("renders an explicit empty state when the photo is not found", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo not found", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("This photo is no longer available in the catalog.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to library" })).toBeInTheDocument();
  });
});
