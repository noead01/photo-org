import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NuqsTestingAdapter, type OnUrlUpdateFunction } from "nuqs/adapters/testing";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";
import { SuggestionsRoutePage } from "./SuggestionsRoutePage";

type MockReply = {
  body: unknown;
  status?: number;
};

function renderPage(path = "/suggestions", onUrlUpdate?: OnUrlUpdateFunction) {
  const url = new URL(path, "https://photo-org.test");
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <NuqsTestingAdapter hasMemory searchParams={url.search} onUrlUpdate={onUrlUpdate}>
        <SuggestionsRoutePage />
      </NuqsTestingAdapter>
    </MemoryRouter>
  );
}

function renderPageStrict(path = "/suggestions", onUrlUpdate?: OnUrlUpdateFunction) {
  const url = new URL(path, "https://photo-org.test");
  return render(
    <StrictMode>
      <MemoryRouter
        initialEntries={[path]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <NuqsTestingAdapter hasMemory searchParams={url.search} onUrlUpdate={onUrlUpdate}>
          <SuggestionsRoutePage />
        </NuqsTestingAdapter>
      </MemoryRouter>
    </StrictMode>
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
      suggestions?: Array<{
        person_id: string;
        display_name: string;
        confidence: number;
        rank?: number;
      }>;
    }>;
  }>;
}) {
  const normalizedItems = items.map((photo) => ({
    ...photo,
    faces: photo.faces.map((face) => ({
      ...face,
      suggestions:
        "suggestions" in face && Array.isArray((face as { suggestions?: unknown }).suggestions)
          ? (face as { suggestions: Array<{ person_id: string; display_name: string; confidence: number; rank?: number }> }).suggestions.map(
              (suggestion, index) => ({
                ...suggestion,
                rank: suggestion.rank ?? index + 1
              })
            )
          : [
              {
                ...face.top_suggestion,
                rank: 1
              }
            ]
    }))
  }));

  return {
    page: {
      page,
      page_size: 24,
      total_items: totalItems ?? items.length,
      total_pages: totalPages
    },
    items: normalizedItems
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
    expect(screen.getByLabelText("Choose suggestion for face face-1")).toHaveDisplayValue("Alex");
    expect(screen.getByLabelText("Choose suggestion for face face-2")).toHaveDisplayValue("Blair");
    const overlay = screen.getByRole("list", {
      name: "Detected face regions"
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

  it("supports toggling shared interaction surfaces and opens face assignment from overlay", async () => {
    const user = userEvent.setup();

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/albums": reply([]),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
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
                  bbox_y: 10,
                  bbox_w: 20,
                  bbox_h: 20,
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

    expect(await screen.findByLabelText("Enable face assignment interactions")).toBeChecked();
    expect(screen.getByLabelText("Enable album interactions")).toBeChecked();
    expect(screen.getByRole("region", { name: "Album actions" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open face 1 actions" }));
    expect(await screen.findByRole("dialog", { name: "Face assignment" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close face assignment modal" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Face assignment" })).not.toBeInTheDocument();
    });

    await user.click(screen.getByLabelText("Enable album interactions"));
    expect(screen.queryByRole("region", { name: "Album actions" })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("Enable face assignment interactions"));
    expect(screen.queryByRole("button", { name: "Open face 1 actions" })).not.toBeInTheDocument();
  });

  it("keeps photo selection separate from selected suggestion faces", async () => {
    const user = userEvent.setup();

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/albums": reply([]),
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

    const photoCheckbox = await screen.findByRole("checkbox", { name: /select photo/i });
    const faceCheckbox = screen.getByRole("checkbox", { name: /confirm suggestion for face/i });
    expect(faceCheckbox).toBeChecked();

    await user.click(photoCheckbox);

    expect(photoCheckbox).toBeChecked();
    expect(faceCheckbox).toBeChecked();
  });

  it("uses selected photos for album actions without clearing selected faces", async () => {
    const user = userEvent.setup();

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/albums": reply([]),
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
      ),
      "POST /api/v1/albums": reply({
        album_id: "album-suggestions",
        name: "Suggestions Picks",
        owner_user_id: "demo-operator",
        kind: "editable",
        created_ts: "2026-05-09T12:00:00Z",
        updated_ts: "2026-05-09T12:00:00Z",
        item_count: 0
      }, 201),
      "POST /api/v1/albums/album-suggestions/items": reply({
        album_id: "album-suggestions",
        added_photo_ids: ["photo-1"],
        duplicate_photo_ids: [],
        missing_photo_ids: []
      })
    });

    renderPage();

    const photoCheckbox = await screen.findByRole("checkbox", { name: /select photo/i });
    const faceCheckbox = screen.getByRole("checkbox", { name: /confirm suggestion for face/i });
    expect(faceCheckbox).toBeChecked();
    await user.click(photoCheckbox);
    await user.type(screen.getByLabelText(/new album name/i), "Suggestions Picks");
    await user.click(screen.getByRole("button", { name: /create and add 1 photo/i }));

    expect(faceCheckbox).toBeChecked();
  });

  it("deduplicates initial strict-mode requests", async () => {
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

    renderPageStrict();
    expect(await screen.findByRole("heading", { name: "Suggestions", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("/photos/photo-1.jpg")).toBeInTheDocument();

    await waitFor(() => {
      const requests = fetchMock.mock.calls.map(([requestInput]) => String(requestInput));
      expect(requests.filter((url) => url === "/api/v1/people")).toHaveLength(1);
      expect(requests.filter((url) => url === "/api/v1/suggestions/faces?page=1&page_size=24")).toHaveLength(1);
    });
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
        body: JSON.stringify({
          face_ids: ["face-1"],
          assignments: [{ face_id: "face-1", person_id: "person-1" }]
        })
      });
    });

    expect(await screen.findByText("Confirmed 1 face suggestion.")).toBeInTheDocument();
  });

  it("submits the selected dropdown suggestion for a checked face", async () => {
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
                    },
                    suggestions: [
                      { person_id: "person-1", display_name: "Alex", confidence: 0.97, rank: 1 },
                      { person_id: "person-3", display_name: "Casey", confidence: 0.89, rank: 2 }
                    ]
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
            person_id: "person-3"
          }
        ],
        skipped: []
      })
    });

    renderPage();

    const selector = await screen.findByLabelText("Choose suggestion for face face-1");
    await user.clear(selector);
    await user.type(selector, "Casey");
    await user.click(screen.getByRole("button", { name: "Confirm faces" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/suggestions/confirmations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({
          face_ids: ["face-1"],
          assignments: [{ face_id: "face-1", person_id: "person-3" }]
        })
      });
    });
  });

  it("confirms one face only with a typed unsuggested name", async () => {
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
            items: [
              {
                photo_id: "photo-1",
                path: "/photos/photo-1.jpg",
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
      ],
      "POST /api/v1/people": reply({
        person_id: "person-new",
        display_name: "Dana New",
        created_ts: "2026-05-06T12:00:00Z",
        updated_ts: "2026-05-06T12:00:00Z"
      }, 201),
      "POST /api/v1/faces/face-1/assignments": reply({
        face_id: "face-1",
        photo_id: "photo-1",
        person_id: "person-new"
      }, 201)
    });

    renderPage();

    const faceChoice = await screen.findByLabelText("Choose suggestion for face face-1");
    await user.clear(faceChoice);
    await user.type(faceChoice, "Dana New");
    await user.click(screen.getAllByRole("button", { name: "Confirm face" })[0]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/people", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ display_name: "Dana New" })
      });
    });
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/faces/face-1/assignments", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({ person_id: "person-new" })
      });
    });
  });

  it("orders suggested names by likelihood in the face chooser", async () => {
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
                  },
                  suggestions: [
                    { person_id: "person-2", display_name: "Blair", confidence: 0.76, rank: 2 },
                    { person_id: "person-1", display_name: "Alex", confidence: 0.97, rank: 1 },
                    { person_id: "person-3", display_name: "Casey", confidence: 0.81, rank: 3 }
                  ]
                }
              ]
            }
          ]
        })
      )
    });

    renderPage();

    const faceChoice = await screen.findByLabelText("Choose suggestion for face face-1");
    const listId = faceChoice.getAttribute("list");
    expect(listId).toBeTruthy();
    const datalist = document.getElementById(listId ?? "");
    expect(datalist).not.toBeNull();
    const optionValues = Array.from(datalist?.querySelectorAll("option") ?? []).map(
      (option) => option.getAttribute("value") ?? ""
    );
    expect(optionValues).toEqual(["Alex", "Casey", "Blair"]);
  });

  it("can mark a face as unknown from the face action button", async () => {
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
      "POST /api/v1/faces/face-1/unknown-identities": reply({
        face_id: "face-1",
        photo_id: "photo-1",
        person_id: "unknown-person"
      })
    });

    renderPage();

    await screen.findByLabelText("Choose suggestion for face face-1");
    await user.click(screen.getByRole("button", { name: "Mark face face-1 as unknown" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/faces/face-1/unknown-identities", {
        method: "POST",
        headers: {
          "X-Face-Validation-Role": "contributor"
        }
      });
    });
  });

  it("can discard a face as false positive from the face action button", async () => {
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
      "POST /api/v1/faces/face-1/dismissals": reply({
        face_id: "face-1",
        photo_id: "photo-1"
      })
    });

    renderPage();

    await screen.findByLabelText("Choose suggestion for face face-1");
    await user.click(screen.getByRole("button", { name: "Discard face face-1 as false positive" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/faces/face-1/dismissals", {
        method: "POST",
        headers: {
          "X-Face-Validation-Role": "contributor"
        }
      });
    });
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
        body: JSON.stringify({
          face_ids: ["face-2"],
          assignments: [{ face_id: "face-2", person_id: "person-2" }]
        })
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
                }
              ]
            }
          ]
        })
      ),
      "GET /api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.1": reply(
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
                    confidence: 0.11
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

    const minimumSlider = screen.getByRole("slider", { name: "Minimum suggestion certainty" });
    minimumSlider.focus();
    await user.keyboard("{PageUp}");

    expect(await screen.findByText("/photos/photo-2.jpg")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.1"
    );
  });

  it("applies a certainty range with both minimum and maximum filters", async () => {
    const user = userEvent.setup();

    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24": reply(
        buildSuggestionsPayload({
          totalItems: 3,
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
      "GET /api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.1": reply(
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
                    confidence: 0.15
                  }
                }
              ]
            }
          ]
        })
      ),
      "GET /api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.1&max_confidence=0.9": reply(
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

    const minimumSlider = screen.getByRole("slider", { name: "Minimum suggestion certainty" });
    minimumSlider.focus();
    await user.keyboard("{PageUp}");
    expect(await screen.findByText("/photos/photo-1.jpg")).toBeInTheDocument();
    const maximumSlider = screen.getByRole("slider", { name: "Maximum suggestion certainty" });
    maximumSlider.focus();
    await user.keyboard("{PageDown}");

    expect(await screen.findByText("/photos/photo-2.jpg")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.1&max_confidence=0.9"
    );
  });

  it("loads suggestion filters from URL query params", async () => {
    installFetchRoutes(fetchMock, {
      "GET /api/v1/people": reply(buildPeoplePayload()),
      "GET /api/v1/suggestions/faces?page=1&page_size=24&min_confidence=0.9&max_confidence=0.95&excluded_person_ids=person-2": reply(
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

    renderPage("/suggestions?minConfidence=90&maxConfidence=95&excludedPersonId=person-2");

    expect(await screen.findByText("Minimum certainty: 90%")).toBeInTheDocument();
    expect(screen.getByText("Maximum certainty: 95%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove excluded person Blair" })).toBeInTheDocument();
  });

  it("falls back to defaults when query filter state is invalid", async () => {
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

    renderPage("/suggestions?minConfidence=-20&maxConfidence=not-a-number&excludedPersonId=&excludedPersonId=%20");

    expect(await screen.findByText("Minimum certainty: 0%")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove excluded person/i })).not.toBeInTheDocument();
  });

  it("hides excluded faces, updates URL filters, and omits photos with no visible faces", async () => {
    const onUrlUpdate = vi.fn();

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
      ),
      "GET /api/v1/suggestions/faces?page=1&page_size=24&excluded_person_ids=person-2": reply(
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
    });

    renderPage("/suggestions", onUrlUpdate);

    expect(await screen.findByLabelText("Choose suggestion for face face-2")).toHaveDisplayValue("Blair");
    fireEvent.change(screen.getByLabelText("Add excluded person"), {
      target: { value: "person-2" }
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/suggestions/faces?page=1&page_size=24&excluded_person_ids=person-2"
      );
    });
    expect(screen.queryByLabelText("Choose suggestion for face face-2")).not.toBeInTheDocument();
    expect(await screen.findByText("Pending photos: 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove excluded person Blair" })).toBeInTheDocument();
    await waitFor(() => {
      expect(onUrlUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          queryString: "?excludedPersonId=person-2"
        })
      );
    });
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
      ],
      "GET /api/v1/suggestions/faces?page=1&page_size=24&excluded_person_ids=person-2": [
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

    expect(await screen.findByLabelText("Choose suggestion for face face-2")).toHaveDisplayValue("Blair");
    fireEvent.change(screen.getByLabelText("Add excluded person"), {
      target: { value: "person-2" }
    });
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/suggestions/faces?page=1&page_size=24&excluded_person_ids=person-2"
      );
    });
    await user.click(screen.getByRole("button", { name: "Confirm faces" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/suggestions/confirmations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({
          face_ids: ["face-1"],
          assignments: [{ face_id: "face-1", person_id: "person-1" }]
        })
      });
    });
  });
});
