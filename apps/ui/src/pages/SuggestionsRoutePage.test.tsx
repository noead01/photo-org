import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { SuggestionsRoutePage } from "./SuggestionsRoutePage";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/suggestions"]}>
      <SuggestionsRoutePage />
    </MemoryRouter>
  );
}

describe("SuggestionsRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders a paginated list of photos with unassigned face top suggestions", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        page: {
          page: 1,
          page_size: 24,
          total_items: 2,
          total_pages: 2
        },
        items: [
          {
            photo_id: "photo-1",
            path: "/photos/photo-1.jpg",
            thumbnail: {
              mime_type: "image/jpeg",
              width: 64,
              height: 48,
              data_base64: "ZmFrZS10aHVtYi1ieXRlcw=="
            },
            faces: [
              {
                face_id: "face-1",
                bbox_x: 10,
                bbox_y: 20,
                bbox_w: 30,
                bbox_h: 40,
                top_suggestion: {
                  person_id: "person-1",
                  display_name: "Alex",
                  confidence: 0.97
                }
              },
              {
                face_id: "face-2",
                bbox_x: 12,
                bbox_y: 22,
                bbox_w: 32,
                bbox_h: 42,
                top_suggestion: {
                  person_id: "person-2",
                  display_name: "Blair",
                  confidence: 0.82
                }
              }
            ]
          }
        ]
      })
    } as Response);

    renderPage();

    expect(await screen.findByRole("heading", { name: "Suggestions", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("/photos/photo-1.jpg")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Preview of /photos/photo-1.jpg" })).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm suggestion for face face-1")).toBeChecked();
    expect(screen.getByLabelText("Confirm suggestion for face face-2")).toBeChecked();
    expect(screen.getByText("Alex (97.0%)")).toBeInTheDocument();
    expect(screen.getByText("Blair (82.0%)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Page 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toHaveAttribute("aria-disabled", "false");
  });

  it("allows unmarking faces and only confirms checked face IDs", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          page: {
            page: 1,
            page_size: 24,
            total_items: 1,
            total_pages: 1
          },
          items: [
            {
              photo_id: "photo-1",
              path: "/photos/photo-1.jpg",
              thumbnail: null,
              faces: [
                {
                  face_id: "face-1",
                  top_suggestion: {
                    person_id: "person-1",
                    display_name: "Alex",
                    confidence: 0.97
                  }
                },
                {
                  face_id: "face-2",
                  top_suggestion: {
                    person_id: "person-2",
                    display_name: "Blair",
                    confidence: 0.82
                  }
                }
              ]
            }
          ]
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          assigned: [
            {
              face_id: "face-1",
              photo_id: "photo-1",
              person_id: "person-1"
            }
          ],
          skipped: []
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          page: {
            page: 1,
            page_size: 24,
            total_items: 0,
            total_pages: 0
          },
          items: []
        })
      } as Response);

    renderPage();

    const firstFaceToggle = await screen.findByLabelText("Confirm suggestion for face face-1");
    const secondFaceToggle = screen.getByLabelText("Confirm suggestion for face face-2");

    expect(firstFaceToggle).toBeChecked();
    expect(secondFaceToggle).toBeChecked();

    await user.click(secondFaceToggle);
    expect(secondFaceToggle).not.toBeChecked();

    await user.click(screen.getByRole("button", { name: "Confirm faces" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/suggestions/confirmations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({ face_ids: ["face-1"] })
      });
    });

    expect(await screen.findByText("Confirmed 1 face suggestion.")).toBeInTheDocument();
  });

  it("navigates between pages", async () => {
    const user = userEvent.setup();

    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          page: {
            page: 1,
            page_size: 24,
            total_items: 2,
            total_pages: 2
          },
          items: [
            {
              photo_id: "photo-1",
              path: "/photos/photo-1.jpg",
              thumbnail: null,
              faces: [
                {
                  face_id: "face-1",
                  top_suggestion: {
                    person_id: "person-1",
                    display_name: "Alex",
                    confidence: 0.97
                  }
                }
              ]
            }
          ]
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          page: {
            page: 2,
            page_size: 24,
            total_items: 2,
            total_pages: 2
          },
          items: [
            {
              photo_id: "photo-2",
              path: "/photos/photo-2.jpg",
              thumbnail: null,
              faces: [
                {
                  face_id: "face-2",
                  top_suggestion: {
                    person_id: "person-2",
                    display_name: "Blair",
                    confidence: 0.88
                  }
                }
              ]
            }
          ]
        })
      } as Response);

    renderPage();

    expect(await screen.findByText("/photos/photo-1.jpg")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Page 2" }));

    expect(await screen.findByText("/photos/photo-2.jpg")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith("/api/v1/suggestions/faces?page=2&page_size=24");
  });

  it("normalizes empty pagination to one disabled page control", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        page: {
          page: 1,
          page_size: 24,
          total_items: 0,
          total_pages: 0
        },
        items: []
      })
    } as Response);

    renderPage();

    expect(await screen.findByText("No pending suggestions.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Previous page" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
    expect(screen.getByRole("button", { name: "Next page" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByText("Page 1 of 0")).not.toBeInTheDocument();
  });
});
