import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
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
        bbox_space_width: null,
        bbox_space_height: null,
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
      shot_ts_source: "exif_ifd:DateTimeOriginal",
      camera_model: "iPhone 15 Pro",
      software: "18.1",
      gps_latitude: 12.3456,
      gps_longitude: -45.6789,
      gps_altitude: 123.4,
      exif_attributes: {
        "exif.DateTime": "2026:03:28 19:30:00",
        "exif_ifd.DateTimeOriginal": "2026:03:28 19:30:00"
      },
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

function renderDetailWithPhotoSwitcher(path = "/library/photo-1") {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route
          path="/library/:photoId"
          element={
            <>
              <PhotoDetailRoutePage />
              <Link to="/library/photo-2">Open photo 2</Link>
            </>
          }
        />
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
    expect(screen.getByText("exif_ifd:DateTimeOriginal")).toBeInTheDocument();
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
            exif_attributes: null,
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
  });

  it("keeps EXIF attributes collapsed by default and reveals them on demand", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          metadata: {
            ...buildPayload().metadata,
            exif_attributes: {
              "exif.CustomNote": "test-note",
              "gps_ifd.GPSLatitude": ["42.0", "11.0", "20.95"]
            }
          }
        })
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Show details" }));

    expect(screen.getByRole("button", { name: "Show all EXIF attributes" })).toBeInTheDocument();
    expect(screen.queryByText("exif.CustomNote")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show all EXIF attributes" }));
    expect(screen.getByRole("button", { name: "Hide all EXIF attributes" })).toBeInTheDocument();
    expect(screen.getByText("exif.CustomNote")).toBeInTheDocument();
    expect(screen.getByText("test-note")).toBeInTheDocument();
    expect(screen.getByText("gps_ifd.GPSLatitude")).toBeInTheDocument();
    expect(screen.getByText("[\"42.0\",\"11.0\",\"20.95\"]")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Hide all EXIF attributes" }));
    expect(screen.queryByText("exif.CustomNote")).not.toBeInTheDocument();
  });

  it("truncates long EXIF attribute values with an ellipsis", async () => {
    const user = userEvent.setup();
    const longExifValue = "123456789012345678901234567890EXTRA-MAKERNOTE-DATA";
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          metadata: {
            ...buildPayload().metadata,
            exif_attributes: {
              "exif_ifd.MakerNote": longExifValue
            }
          }
        })
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Show details" }));
    await user.click(screen.getByRole("button", { name: "Show all EXIF attributes" }));

    expect(screen.getByText("exif_ifd.MakerNote")).toBeInTheDocument();
    expect(screen.getByText("123456789012345678901234567890...")).toBeInTheDocument();
    expect(screen.queryByText(longExifValue)).not.toBeInTheDocument();
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

  it("renders face overlays when bbox coordinates use a larger source-image space", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          faces: [
            {
              face_id: "face-1",
              person_id: "person-1",
              bbox_x: 320,
              bbox_y: 160,
              bbox_w: 120,
              bbox_h: 140,
              bbox_space_width: null,
              bbox_space_height: null,
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
          }
        })
    } as Response);

    renderDetail();

    expect(await screen.findByText("1 face region rendered.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Detected face regions" })).toBeInTheDocument();
    expect(screen.getByLabelText("Face region 1 for person-1")).toBeInTheDocument();
    expect(
      screen.queryByText("Face regions are present but could not be rendered on this preview.")
    ).not.toBeInTheDocument();
  });

  it("maps face overlays using explicit bbox coordinate-space dimensions when provided", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          faces: [
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
          ],
          thumbnail: {
            mime_type: "image/jpeg",
            width: 100,
            height: 75,
            data_base64: "dGh1bWI="
          }
        })
    } as Response);

    renderDetail();

    const region = await screen.findByLabelText("Face region 1 for person-1");
    expect(region).toHaveStyle({
      left: "25%",
      top: "10%",
      width: "20%",
      height: "20%"
    });
  });

  it("keeps face overlays coherent while adjusting photo size", async () => {
    const user = userEvent.setup();

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    expect(await screen.findByLabelText("Face region 1 for person-1")).toBeInTheDocument();

    const sizeSlider = screen.getByRole("slider", { name: "Photo size" });
    fireEvent.change(sizeSlider, { target: { value: "120" } });

    expect(await screen.findByLabelText("Face region 1 for person-1")).toBeInTheDocument();
  });

  it("does not render preview mode toggle buttons", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Preview controls" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Preview display mode" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Fit to panel" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Actual pixels" })).not.toBeInTheDocument();
  });

  it("loads the full-resolution original image when available", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    const image = await screen.findByRole("img", { name: "Preview for photo-1" });
    expect(image).toHaveAttribute("src", "/api/v1/photos/photo-1/original");
  });

  it("prefers loading the original preview even when availability metadata is stale", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          original: {
            is_available: false,
            availability_state: "missing",
            last_failure_reason: "stale status"
          }
        })
    } as Response);

    renderDetail();

    const image = await screen.findByRole("img", { name: "Preview for photo-1" });
    expect(image).toHaveAttribute("src", "/api/v1/photos/photo-1/original");
  });

  it("falls back to the thumbnail when original-image loading fails", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    const image = await screen.findByRole("img", { name: "Preview for photo-1" });
    expect(image).toHaveAttribute("src", "/api/v1/photos/photo-1/original");
    fireEvent.error(image);

    await waitFor(() => {
      expect(image).toHaveAttribute("src", "data:image/jpeg;base64,dGh1bWI=");
    });
  });

  it("retries original-image rendering using fetched bytes before falling back", async () => {
    const originalCreateObjectUrl = URL.createObjectURL;
    const originalRevokeObjectUrl = URL.revokeObjectURL;
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:photo-1")
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn()
    });
    fetchMock.mockImplementation(async (input) => {
      const requestPath = String(input);
      if (requestPath === "/api/v1/people") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }
      if (requestPath === "/api/v1/photos/photo-1") {
        return {
          ok: true,
          json: async () => buildPayload()
        } as Response;
      }
      if (requestPath === "/api/v1/photos/photo-1/original") {
        return {
          ok: true,
          headers: new Headers({ "content-type": "image/jpeg" }),
          blob: async () => new Blob(["original"], { type: "image/jpeg" })
        } as unknown as Response;
      }
      return {
        ok: false,
        status: 500
      } as Response;
    });

    renderDetail();

    const image = await screen.findByRole("img", { name: "Preview for photo-1" });
    expect(image).toHaveAttribute("src", "/api/v1/photos/photo-1/original");
    fireEvent.error(image);

    await waitFor(() => {
      expect(image).toHaveAttribute("src", "blob:photo-1");
    });

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: originalCreateObjectUrl
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: originalRevokeObjectUrl
    });
  });

  it("ignores stale original-image errors after navigating to another photo", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input) => {
      const requestPath = String(input);
      if (requestPath === "/api/v1/people") {
        return {
          ok: true,
          json: async () => []
        } as Response;
      }
      if (requestPath === "/api/v1/photos/photo-1") {
        return {
          ok: true,
          json: async () => buildPayload()
        } as Response;
      }
      if (requestPath === "/api/v1/photos/photo-2") {
        return {
          ok: true,
          json: async () =>
            buildPayload({
              photo_id: "photo-2",
              path: "/library/photo-2.jpg",
              metadata: {
                ...buildPayload().metadata,
                sha256: "sha-2"
              }
            })
        } as Response;
      }
      return {
        ok: false,
        status: 500
      } as Response;
    });

    renderDetailWithPhotoSwitcher();

    expect(await screen.findByRole("img", { name: "Preview for photo-1" })).toHaveAttribute(
      "src",
      "/api/v1/photos/photo-1/original"
    );

    await user.click(screen.getByRole("link", { name: "Open photo 2" }));

    const image = await screen.findByRole("img", { name: "Preview for photo-2" });
    expect(image).toHaveAttribute("src", "/api/v1/photos/photo-2/original");

    Object.defineProperty(image, "currentSrc", {
      configurable: true,
      value: "http://localhost/api/v1/photos/photo-1/original"
    });
    fireEvent.error(image);

    expect(image).toHaveAttribute("src", "/api/v1/photos/photo-2/original");
  });

  it("allows toggling face bbox overlays in the preview", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => buildPayload()
    } as Response);

    renderDetail();

    expect(await screen.findByLabelText("Face region 1 for person-1")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Show face boxes" }));
    expect(screen.queryByRole("list", { name: "Detected face regions" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Show face boxes" }));
    expect(await screen.findByLabelText("Face region 1 for person-1")).toBeInTheDocument();
  });

  it("opens the face-assignment modal when clicking the face bounding box", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => buildPayload()
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
        json: async () => ({
          face_id: "face-1",
          candidates: [],
          suggestion_policy: {
            decision: "no_suggestion",
            review_threshold: 0.5,
            auto_accept_threshold: 0.9,
            top_candidate_confidence: null
          },
          review_needed_suggestion: null,
          auto_applied_assignment: null
        })
      } as Response);

    renderDetail();

    await user.click(await screen.findByLabelText("Face region 1 for person-1"));
    expect(await screen.findByRole("dialog", { name: "Face assignment" })).toBeInTheDocument();
  });

  it("does not auto-assign from candidates payload and only updates on explicit save", async () => {
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
        json: async () => ({
          face_id: "face-1",
          candidates: [
            {
              person_id: "person-1",
              display_name: "Inez",
              matched_face_id: "face-7",
              distance: 0.09,
              confidence: 0.87
            }
          ],
          auto_applied_assignment: {
            person_id: "person-2"
          }
        })
      } as Response);

    renderDetail();

    expect(await screen.findByRole("heading", { name: "Photo detail", level: 1 })).toBeInTheDocument();
    await user.click(
      await screen.findByRole("button", { name: "Open face assignment for face region 1" })
    );
    expect(await screen.findByRole("dialog", { name: "Face assignment" })).toBeInTheDocument();
    expect(screen.getByLabelText("Assign person")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Open face assignment for face region 1" })).toHaveTextContent("?");
    expect(screen.queryByText("person-2")).not.toBeInTheDocument();
  });

  it("opens a face-assignment modal from the overlay badge and assigns a person from suggestions", async () => {
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
        json: async () => ({
          face_id: "face-1",
          candidates: [
            {
              person_id: "person-1",
              display_name: "Inez",
              matched_face_id: "face-7",
              distance: 0.09,
              confidence: 0.87
            }
          ],
          suggestion_policy: {
            decision: "review_needed",
            review_threshold: 0.5,
            auto_accept_threshold: 0.9,
            top_candidate_confidence: 0.87
          },
          review_needed_suggestion: null,
          auto_applied_assignment: null
        })
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
    expect(await screen.findByRole("button", { name: "Open face assignment for face region 1" })).toHaveTextContent(
      "?"
    );
    await user.click(
      await screen.findByRole("button", { name: "Open face assignment for face region 1" })
    );
    expect(await screen.findByRole("dialog", { name: "Face assignment" })).toBeInTheDocument();
    expect(screen.getByText("Inez (87.0%)")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Assign person"));
    await user.type(screen.getByLabelText("Assign person"), "ine");
    await user.click(screen.getByRole("button", { name: "Save and close" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Face assignment" })).not.toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: "Open face assignment for face region 1" })).toHaveTextContent(
      "I"
    );
    expect(screen.getByText("person-1")).toBeInTheDocument();
  });

  it("updates local face state after correction success when saving from the modal", async () => {
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
        json: async () => ({
          face_id: "face-1",
          candidates: [],
          suggestion_policy: {
            decision: "no_suggestion",
            review_threshold: 0.5,
            auto_accept_threshold: 0.9,
            top_candidate_confidence: null
          },
          review_needed_suggestion: null,
          auto_applied_assignment: null
        })
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
    await user.click(
      await screen.findByRole("button", { name: "Open face assignment for face region 1" })
    );
    await user.clear(screen.getByLabelText("Assign person"));
    await user.type(screen.getByLabelText("Assign person"), "mat");
    await user.click(screen.getByRole("button", { name: "Save and close" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Face assignment" })).not.toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: "Open face assignment for face region 1" })).toHaveTextContent(
      "M"
    );
    expect(screen.getByText("person-2")).toBeInTheDocument();
  });

  it("creates a new person name from typed input when no exact match exists", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          buildPayload({
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
        json: async () => ({
          face_id: "face-1",
          candidates: [],
          suggestion_policy: {
            decision: "no_suggestion",
            review_threshold: 0.5,
            auto_accept_threshold: 0.9,
            top_candidate_confidence: null
          },
          review_needed_suggestion: null,
          auto_applied_assignment: null
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({
          person_id: "person-2",
          display_name: "Nova",
          created_ts: "2026-03-28T19:31:00Z",
          updated_ts: "2026-03-28T19:31:00Z"
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({
          face_id: "face-1",
          photo_id: "photo-1",
          person_id: "person-2"
        })
      } as Response);

    renderDetail();

    expect(await screen.findByLabelText("Face region 1")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open face assignment for face region 1" }));
    await user.clear(screen.getByLabelText("Assign person"));
    await user.type(screen.getByLabelText("Assign person"), "Nova");
    await user.click(screen.getByRole("button", { name: 'Create and assign "Nova"' }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Face assignment" })).not.toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: "Open face assignment for face region 1" })).toHaveTextContent(
      "N"
    );
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

  it("renders pending ingest status without an ingest legend section", async () => {
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
    expect(screen.queryByText("Ingest status legend")).not.toBeInTheDocument();
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
