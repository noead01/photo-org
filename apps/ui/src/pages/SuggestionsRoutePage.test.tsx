import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { SuggestionsRoutePage } from "./SuggestionsRoutePage";

type MockReply = {
  body: unknown;
  status?: number;
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/suggestions"]}>
      <SuggestionsRoutePage />
    </MemoryRouter>
  );
}

function reply(body: unknown, status = 200): MockReply {
  return { body, status };
}

function buildPeoplePayload() {
  return [
    {
      person_id: "person-1",
      display_name: "Alex",
      created_ts: "2026-03-28T19:30:00Z",
      updated_ts: "2026-03-28T19:30:00Z"
    },
    {
      person_id: "person-2",
      display_name: "Blair",
      created_ts: "2026-03-28T19:31:00Z",
      updated_ts: "2026-03-28T19:31:00Z"
    },
    {
      person_id: "person-3",
      display_name: "Casey",
      created_ts: "2026-03-28T19:32:00Z",
      updated_ts: "2026-03-28T19:32:00Z"
    }
  ];
}

function buildSuggestionsPayload({
  page = 1,
  totalItems,
  totalPages = 1,
  items
}: {
  page?: number;
  totalItems?: number;
  totalPages?: number;
  items: Array<{
    photo_id: string;
    path: string;
    thumbnail: {
      mime_type: string;
      width: number;
      height: number;
      data_base64: string;
    } | null;
    faces: Array<{
      face_id: string;
      bbox_x?: number;
      bbox_y?: number;
      bbox_w?: number;
      bbox_h?: number;
      top_suggestion: {
        person_id: string;
        display_name: string;
        confidence: number;
      };
    }>;
  }>;
}) {
  return {
    page: {
      page,
      page_size: 24,
      total_items: totalItems ?? items.length,
      total_pages: totalPages
    },
    items
  };
}

function installFetchRoutes(
  fetchMock: ReturnType<typeof vi.fn>,
  routes: Record<string, MockReply | MockReply[]>
) {
  const normalizedRoutes = new Map<string, MockReply[]>(
    Object.entries(routes).map(([key, value]) => [key, Array.isArray(value) ? [...value] : [value]])
  );

  fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const url = typeof input === "string" ? input : input.toString();
    const routeKey = `${method} ${url}`;
    const replies = normalizedRoutes.get(routeKey);
    if (!replies || replies.length === 0) {
      throw new Error(`Unexpected fetch request: ${routeKey}`);
    }
    const currentReply = replies.length > 1 ? replies.shift() : replies[0];
    const status = currentReply?.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => currentReply?.body
    } as Response;
  });
}

describe("SuggestionsRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a paginated list of photos with unassigned face top suggestions", async () => {
    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
          totalItems: 2,
          totalPages: 2,
          items: [
            {
              photo_id: "photo-1",
              path: "/storage-sources/source-1/family/trip/photo-1.jpg",
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
      )
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "Suggestions", level: 1 })).toBeInTheDocument();
    expect(screen.getByText(".../family/trip/photo-1.jpg")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Preview of /storage-sources/source-1/family/trip/photo-1.jpg" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "Open details for /storage-sources/source-1/family/trip/photo-1.jpg"
      })
    ).toHaveAttribute("href", "/library/photo-1");
    expect(screen.getByLabelText("Confirm suggestion for face face-1")).toBeChecked();
    expect(screen.getByLabelText("Confirm suggestion for face face-2")).toBeChecked();
    expect(screen.getByText("Face 1: Alex (97.0%)")).toBeInTheDocument();
    expect(screen.getByText("Face 2: Blair (82.0%)")).toBeInTheDocument();
    const overlay = screen.getByRole("list", {
      name: "Suggested face regions for /storage-sources/source-1/family/trip/photo-1.jpg"
    });
    expect(within(overlay).getByText("1")).toBeInTheDocument();
    expect(within(overlay).getByText("2")).toBeInTheDocument();
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

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": [
        reply(
          buildSuggestionsPayload({
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
        ),
        reply(
          buildSuggestionsPayload({
            totalItems: 0,
            totalPages: 0,
            items: []
          })
        )
      ],
      "POST /api/v1/suggestions/confirmations": reply({
        assigned: [
          {
            face_id: "face-1",
            photo_id: "photo-1",
            person_id: "person-1"
          }
        ],
        skipped: []
      })
    });

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

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
          totalItems: 2,
          totalPages: 2,
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
      ),
      "GET /api/v1/suggestions/faces?page=2&page_size=24": reply(
        buildSuggestionsPayload({
          page: 2,
          totalItems: 2,
          totalPages: 2,
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
      )
    });

    renderPage();

    expect(await screen.findByText("/photos/photo-1.jpg")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Page 2" }));

    expect(await screen.findByText("/photos/photo-2.jpg")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/suggestions/faces?page=2&page_size=24");
  });

  it("confirms only checked face assignments from the current page", async () => {
    const user = userEvent.setup();

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
          totalItems: 2,
          totalPages: 2,
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
      ),
      "GET /api/v1/suggestions/faces?page=2&page_size=24": [
        reply(
          buildSuggestionsPayload({
            page: 2,
            totalItems: 2,
            totalPages: 2,
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
        ),
        reply(
          buildSuggestionsPayload({
            page: 2,
            totalItems: 0,
            totalPages: 0,
            items: []
          })
        )
      ],
      "POST /api/v1/suggestions/confirmations": reply({
        assigned: [
          {
            face_id: "face-2",
            photo_id: "photo-2",
            person_id: "person-2"
          }
        ],
        skipped: []
      })
    });

    renderPage();
    expect(await screen.findByText("/photos/photo-1.jpg")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Page 2" }));
    expect(await screen.findByText("/photos/photo-2.jpg")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm faces" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/suggestions/confirmations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({ face_ids: ["face-2"] })
      });
    });
  });

  it("normalizes empty pagination to one disabled page control", async () => {
    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
          totalItems: 0,
          totalPages: 0,
          items: []
        })
      )
    });

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

  it("applies minimum certainty slider as a global suggestions filter", async () => {
    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
          totalItems: 2,
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
      ),
      "GET /api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.9": reply(
        buildSuggestionsPayload({
          totalItems: 1,
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
                    confidence: 0.91
                  }
                }
              ]
            }
          ]
        })
      )
    });

    renderPage();
    expect(await screen.findByText("/photos/photo-1.jpg")).toBeInTheDocument();

    const thresholdSlider = screen.getByLabelText("Minimum suggestion certainty");
    fireEvent.change(thresholdSlider, { target: { value: "90" } });

    expect(await screen.findByText("/photos/photo-2.jpg")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.9"
    );
  });

  it("restores persisted minimum certainty and excluded people from local storage", async () => {
    window.localStorage.setItem(
      "photo-org:suggestions:filters",
      JSON.stringify({
        minConfidencePercent: 90,
        excludedPersonIds: ["person-2"]
      })
    );

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.9": reply(
        buildSuggestionsPayload({
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
      )
    });

    renderPage();

    expect(await screen.findByDisplayValue("90")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exclude Blair" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("falls back to defaults when persisted filter state is invalid", async () => {
    window.localStorage.setItem("photo-org:suggestions:filters", "{bad json");

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
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
      )
    });

    renderPage();

    expect(await screen.findByDisplayValue("0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exclude Alex" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("hides excluded faces, persists filter changes, and omits photos with no visible faces", async () => {
    const user = userEvent.setup();

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
          totalItems: 2,
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
            },
            {
              photo_id: "photo-2",
              path: "/photos/photo-2.jpg",
              thumbnail: null,
              faces: [
                {
                  face_id: "face-3",
                  top_suggestion: {
                    person_id: "person-2",
                    display_name: "Blair",
                    confidence: 0.87
                  }
                }
              ]
            }
          ]
        })
      )
    });

    renderPage();

    expect(await screen.findByText("Face 2: Blair (82.0%)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Exclude Blair" }));

    expect(screen.queryByText("Face 2: Blair (82.0%)")).not.toBeInTheDocument();
    expect(screen.queryByText("/photos/photo-2.jpg")).not.toBeInTheDocument();
    expect(screen.getByText("Pending photos: 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exclude Blair" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(window.localStorage.getItem("photo-org:suggestions:filters")).toContain("person-2");
  });

  it("confirms only currently visible face ids after exclusions are applied", async () => {
    const user = userEvent.setup();

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": [
        reply(
          buildSuggestionsPayload({
            totalItems: 2,
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
              },
              {
                photo_id: "photo-2",
                path: "/photos/photo-2.jpg",
                thumbnail: null,
                faces: [
                  {
                    face_id: "face-3",
                    top_suggestion: {
                      person_id: "person-2",
                      display_name: "Blair",
                      confidence: 0.87
                    }
                  }
                ]
              }
            ]
          })
        ),
        reply(
          buildSuggestionsPayload({
            totalItems: 1,
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
        )
      ],
      "POST /api/v1/suggestions/confirmations": reply({
        assigned: [
          {
            face_id: "face-1",
            photo_id: "photo-1",
            person_id: "person-1"
          }
        ],
        skipped: []
      })
    });

    renderPage();

    expect(await screen.findByText("Face 2: Blair (82.0%)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Exclude Blair" }));
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
  });
});
