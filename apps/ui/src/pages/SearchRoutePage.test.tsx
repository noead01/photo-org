import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { SearchRoutePage } from "./SearchRoutePage";

vi.mock("./search/LocationRadiusPicker", () => ({
  LocationRadiusPicker: () => <div data-testid="location-radius-picker" />
}));

const SEARCH_ENDPOINT = "/api/v1/search";
const PEOPLE_ENDPOINT = "/api/v1/people";

interface SearchResponsePayload {
  hits: {
    total: number;
    cursor: string | null;
    items: Array<{
      photo_id: string;
      path: string;
      ext: string;
      shot_ts: string | null;
      filesize: number;
    }>;
  };
  facets: {
    has_faces?: Record<string, unknown>;
    path_hints?: Array<{ value: string; count: number }>;
    tags?: Array<{ value: string; count: number }>;
  };
}

interface PersonPayload {
  person_id: string;
  display_name: string;
  created_ts: string;
  updated_ts: string;
}

function buildPayload(
  photoIds: string[],
  total = photoIds.length,
  facets: SearchResponsePayload["facets"] = {},
  cursor: string | null = null
): SearchResponsePayload {
  return {
    hits: {
      total,
      cursor,
      items: photoIds.map((photoId, index) => ({
        photo_id: photoId,
        path: `/library/${photoId}.jpg`,
        ext: "jpg",
        shot_ts: `2026-04-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
        filesize: 1024 + index
      }))
    },
    facets
  };
}

const PEOPLE_FIXTURE: PersonPayload[] = [
  {
    person_id: "person-inez",
    display_name: "Inez Alvarez",
    created_ts: "2026-04-10T12:00:00Z",
    updated_ts: "2026-04-11T12:00:00Z"
  },
  {
    person_id: "person-ana",
    display_name: "Ana Morales",
    created_ts: "2026-04-10T12:00:00Z",
    updated_ts: "2026-04-11T12:00:00Z"
  },
  {
    person_id: "person-andy",
    display_name: "Andy Morgan",
    created_ts: "2026-04-10T12:00:00Z",
    updated_ts: "2026-04-11T12:00:00Z"
  }
];

function renderSearchAt(path = "/search") {
  function SearchLocationProbe() {
    const location = useLocation();
    return <p data-testid="search-location-probe">{location.search}</p>;
  }

  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route
          path="/search"
          element={
            <>
              <SearchRoutePage />
              <SearchLocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

function searchCalls(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.filter(
    ([url]) => typeof url === "string" && url === SEARCH_ENDPOINT
  );
}

function lastSearchBody(fetchMock: ReturnType<typeof vi.fn>) {
  const calls = searchCalls(fetchMock);
  const lastCall = calls[calls.length - 1];
  return JSON.parse(String((lastCall?.[1] as RequestInit).body));
}

describe("SearchRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload([], 0)
      } as Response;
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits a phrase chip with Enter and sends q using chip-order serialization", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "lake weekend{enter}");

    expect(await screen.findByRole("button", { name: "Remove query lake weekend" })).toBeInTheDocument();

    const lastCall = searchCalls(fetchMock)[searchCalls(fetchMock).length - 1];
    expect(lastCall?.[0]).toBe(SEARCH_ENDPOINT);
    const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
    expect(body.q).toBe("lake weekend");
    expect(body.sort).toEqual({ by: "shot_ts", dir: "desc" });
    expect(body.page).toEqual({ limit: 24, cursor: null });
  });

  it("submits with Search button and appends phrase as a new chip", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "first phrase");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.type(input, "second phrase");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByRole("button", { name: "Remove query first phrase" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove query second phrase" })).toBeInTheDocument();

    const body = lastSearchBody(fetchMock);
    expect(body.q).toBe("first phrase second phrase");
  });

  it("submits date-only filters and sends date range under filters.date", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("From date"), "2026-04-01");
    await user.type(screen.getByLabelText("To date"), "2026-04-30");
    await user.click(screen.getByRole("button", { name: "Search" }));

    const body = lastSearchBody(fetchMock);
    expect(body.q).toBe("");
    expect(body.filters).toEqual({
      date: {
        from: "2026-04-01",
        to: "2026-04-30"
      }
    });
  });

  it("ignores whitespace-only submit and keeps existing chips and request count unchanged", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "coastline");
    await user.click(screen.getByRole("button", { name: "Search" }));
    const callsAfterFirstSubmit = searchCalls(fetchMock).length;

    await user.clear(input);
    await user.type(input, "   ");
    await user.keyboard("{Enter}");

    expect(searchCalls(fetchMock).length).toBe(callsAfterFirstSubmit);
    expect(screen.getByRole("button", { name: "Remove query coastline" })).toBeInTheDocument();
  });

  it("removes dismissed chip and re-fetches using remaining chip order", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "alpha");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.type(input, "beta");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.click(screen.getByRole("button", { name: "Remove query alpha" }));

    const body = lastSearchBody(fetchMock);
    expect(body.q).toBe("beta");
    expect(screen.queryByRole("button", { name: "Remove query alpha" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove query beta" })).toBeInTheDocument();
  });

  it("blocks submit for an invalid date range and shows explicit validation messaging", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("From date"), "2026-04-30");
    await user.type(screen.getByLabelText("To date"), "2026-04-01");
    await user.type(screen.getByRole("textbox", { name: "Search query" }), "lake");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(searchCalls(fetchMock)).toHaveLength(0);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "From date must be on or before To date."
    );
  });

  it("removes active date chips and re-fetches with updated date filter state", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("From date"), "2026-04-01");
    await user.type(screen.getByLabelText("To date"), "2026-04-30");
    await user.type(screen.getByRole("textbox", { name: "Search query" }), "coast");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.click(screen.getByRole("button", { name: "Remove from date 2026-04-01" }));

    const fromClearedBody = lastSearchBody(fetchMock);
    expect(fromClearedBody.filters).toEqual({
      date: {
        to: "2026-04-30"
      }
    });

    await user.click(screen.getByRole("button", { name: "Remove to date 2026-04-30" }));
    const toClearedBody = lastSearchBody(fetchMock);
    expect(toClearedBody.filters).toBeUndefined();
  });

  it("renders loading status while the search request is pending", async () => {
    let resolveResponse!: (value: Response) => void;
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      return await new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      });
    });

    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "harbor");
    await user.keyboard("{Enter}");

    expect(screen.getByRole("status")).toHaveTextContent("Loading search workflow.");

    resolveResponse({
      ok: true,
      json: async () => buildPayload([], 0)
    } as Response);

    expect(await screen.findByText("No matching photos for the active query.")).toBeInTheDocument();
  });

  it("maps sort control selections to deterministic backend sort modes", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.selectOptions(screen.getByLabelText("Sort order"), "asc");
    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "lake");
    await user.click(screen.getByRole("button", { name: "Search" }));

    const body = lastSearchBody(fetchMock);
    expect(body.sort).toEqual({ by: "shot_ts", dir: "asc" });
    expect(body.page).toEqual({ limit: 24, cursor: null });
  });

  it("advances and returns pages using deterministic cursor boundaries", async () => {
    const user = userEvent.setup();
    let searchRequestCount = 0;
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      searchRequestCount += 1;
      if (searchRequestCount === 1) {
        return {
          ok: true,
          json: async () => buildPayload(["photo-1"], 3, {}, "cursor-page-2")
        } as Response;
      }

      if (searchRequestCount === 2) {
        return {
          ok: true,
          json: async () => buildPayload(["photo-2"], 3, {}, "cursor-page-3")
        } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-1"], 3, {}, "cursor-page-2")
      } as Response;
    });

    renderSearchAt();
    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "trip");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("photo-1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("photo-2")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();

    const secondRequest = searchCalls(fetchMock)[1]?.[1] as RequestInit;
    expect(JSON.parse(String(secondRequest.body)).page).toEqual({
      limit: 24,
      cursor: "cursor-page-2"
    });

    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(await screen.findByText("photo-1")).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();
  });

  it("resets pagination to page one when filter state changes", async () => {
    const user = userEvent.setup();
    let searchRequestCount = 0;
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      searchRequestCount += 1;
      if (searchRequestCount === 1) {
        return {
          ok: true,
          json: async () =>
            buildPayload(["photo-1"], 3, { has_faces: { true: 2, false: 1 } }, "cursor-page-2")
        } as Response;
      }
      if (searchRequestCount === 2) {
        return {
          ok: true,
          json: async () =>
            buildPayload(["photo-2"], 3, { has_faces: { true: 2, false: 1 } }, "cursor-page-3")
        } as Response;
      }
      return {
        ok: true,
        json: async () => buildPayload(["photo-3"], 2, { has_faces: { true: 1, false: 1 } }, null)
      } as Response;
    });

    renderSearchAt();
    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "lake");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("photo-2")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "With faces (2)" }));
    expect(await screen.findByText("photo-3")).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();

    const filterChangeRequest = searchCalls(fetchMock)[2]?.[1] as RequestInit;
    expect(JSON.parse(String(filterChangeRequest.body)).page).toEqual({ limit: 24, cursor: null });
  });

  it("deterministically falls back to page one when a page boundary is invalid", async () => {
    const user = userEvent.setup();
    let searchRequestCount = 0;
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      searchRequestCount += 1;
      if (searchRequestCount === 1) {
        return {
          ok: true,
          json: async () => buildPayload(["photo-1"], 1, {}, "cursor-page-2")
        } as Response;
      }
      if (searchRequestCount === 2) {
        return {
          ok: true,
          json: async () => buildPayload([], 1, {}, null)
        } as Response;
      }
      return {
        ok: true,
        json: async () => buildPayload(["photo-1"], 1, {}, "cursor-page-2")
      } as Response;
    });

    renderSearchAt();
    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "lake");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(screen.getByRole("button", { name: "Next page" }));

    expect(await screen.findByText("Reset to page 1 because that page position is unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();

    const fallbackRequest = searchCalls(fetchMock)[2]?.[1] as RequestInit;
    expect(JSON.parse(String(fallbackRequest.body)).page).toEqual({ limit: 24, cursor: null });
  });

  it("shows retry UI on failure and retries with active chips", async () => {
    const user = userEvent.setup();

    let searchRequestCount = 0;
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      searchRequestCount += 1;
      if (searchRequestCount === 1) {
        return { ok: false, status: 503 } as Response;
      }

      return {
        ok: true,
        json: async () => buildPayload(["photo-1"], 1)
      } as Response;
    });

    renderSearchAt();
    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "storm coast");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(
      await screen.findByRole("heading", {
        name: "Could not load Search",
        level: 2
      })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    const body = lastSearchBody(fetchMock);
    expect(body.q).toBe("storm coast");
    expect(await screen.findByText("photo-1")).toBeInTheDocument();
  });

  it("adds a fuzzy-matched person filter and submits it as filters.person_names", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const personInput = await screen.findByLabelText("Person filter");
    await user.type(personInput, "inz");
    await user.click(screen.getByRole("button", { name: "Add person filter" }));

    expect(screen.getByRole("button", { name: "Remove person Inez Alvarez" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Search" }));
    const body = lastSearchBody(fetchMock);
    expect(body.filters).toEqual({
      person_names: ["Inez Alvarez"]
    });
  });

  it("surfaces ambiguous fuzzy matches and allows selecting a specific person suggestion", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const personInput = await screen.findByLabelText("Person filter");
    await user.type(personInput, "an");
    await user.click(screen.getByRole("button", { name: "Add person filter" }));

    expect(
      await screen.findByText('Multiple people match "an". Select one from suggestions.')
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ana Morales" }));
    expect(screen.getByRole("button", { name: "Remove person Ana Morales" })).toBeInTheDocument();
  });

  it("shows explicit no-match feedback without blocking other search submission", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const personInput = await screen.findByLabelText("Person filter");
    await user.type(personInput, "zzzz");
    await user.click(screen.getByRole("button", { name: "Add person filter" }));

    expect(
      await screen.findByText('No people match "zzzz". Search still works without this filter.')
    ).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "Search query" }), "coast");
    await user.click(screen.getByRole("button", { name: "Search" }));

    const body = lastSearchBody(fetchMock);
    expect(body.q).toBe("coast");
    expect(body.filters).toBeUndefined();
  });

  it("removes selected person chips and re-fetches without person_names filters", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const personInput = await screen.findByLabelText("Person filter");
    await user.type(personInput, "inez");
    await user.click(screen.getByRole("button", { name: "Add person filter" }));
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.click(screen.getByRole("button", { name: "Remove person Inez Alvarez" }));
    const body = lastSearchBody(fetchMock);
    expect(body.filters).toBeUndefined();
  });

  it("submits valid location filter as filters.location_radius", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("Latitude"), "37.7749");
    await user.type(screen.getByLabelText("Longitude"), "-122.4194");
    await user.type(screen.getByLabelText("Radius (km)"), "12.5");
    await user.click(screen.getByRole("button", { name: "Search" }));

    const body = lastSearchBody(fetchMock);
    expect(body.filters).toEqual({
      location_radius: {
        latitude: 37.7749,
        longitude: -122.4194,
        radius_km: 12.5
      }
    });
  });

  it("blocks submit when location values are invalid", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("Latitude"), "91");
    await user.type(screen.getByLabelText("Longitude"), "-122.4194");
    await user.type(screen.getByLabelText("Radius (km)"), "12");
    await user.type(screen.getByRole("textbox", { name: "Search query" }), "coast");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(searchCalls(fetchMock)).toHaveLength(0);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Latitude must be between -90 and 90."
    );
  });

  it("removes location chip and re-fetches without location_radius filters", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("Latitude"), "37.7749");
    await user.type(screen.getByLabelText("Longitude"), "-122.4194");
    await user.type(screen.getByLabelText("Radius (km)"), "12.5");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.click(
      screen.getByRole("button", { name: "Remove location: 37.7749, -122.4194 (12.5 km)" })
    );

    const body = lastSearchBody(fetchMock);
    expect(body.filters).toBeUndefined();
  });

  it("does not auto-search when location fields change", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("Latitude"), "37.7749");
    await user.type(screen.getByLabelText("Longitude"), "-122.4194");
    await user.type(screen.getByLabelText("Radius (km)"), "12.5");

    expect(searchCalls(fetchMock)).toHaveLength(0);
  });

  it("combines location, person, and date filters in one deterministic request payload", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    await user.type(await screen.findByLabelText("Latitude"), "37.7749");
    await user.type(screen.getByLabelText("Longitude"), "-122.4194");
    await user.type(screen.getByLabelText("Radius (km)"), "12.5");
    await user.type(screen.getByLabelText("From date"), "2026-04-01");

    const personInput = screen.getByLabelText("Person filter");
    await user.type(personInput, "inez");
    await user.click(screen.getByRole("button", { name: "Add person filter" }));

    await user.click(screen.getByRole("button", { name: "Search" }));

    const body = lastSearchBody(fetchMock);
    expect(body.filters).toEqual({
      date: {
        from: "2026-04-01"
      },
      person_names: ["Inez Alvarez"],
      location_radius: {
        latitude: 37.7749,
        longitude: -122.4194,
        radius_km: 12.5
      }
    });
  });

  it("renders has-faces facet counts and toggles has_faces filter deterministically", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      return {
        ok: true,
        json: async () =>
          buildPayload(["photo-1"], 1, {
            has_faces: { true: 5, false: 2 },
            tags: [{ value: "event:lake-weekend", count: 3 }]
          })
      } as Response;
    });

    renderSearchAt();
    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "lake");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByRole("button", { name: "With faces (5)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Without faces (2)" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "With faces (5)" }));
    expect(lastSearchBody(fetchMock).filters).toEqual({ has_faces: true });

    await user.click(screen.getByRole("button", { name: "With faces (5)" }));
    expect(lastSearchBody(fetchMock).filters).toBeUndefined();
  });

  it("uses path-hint facet counts for toggle and clear interactions", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      return {
        ok: true,
        json: async () =>
          buildPayload(["photo-1"], 1, {
            has_faces: { true: 1, false: 0 },
            tags: [
              { value: "event:lake-weekend", count: 4 },
              { value: "event:city-break", count: 2 }
            ]
          })
      } as Response;
    });

    renderSearchAt();
    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "travel");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.click(screen.getByRole("button", { name: "path: city-break (2)" }));
    await user.click(screen.getByRole("button", { name: "path: lake-weekend (4)" }));

    expect(lastSearchBody(fetchMock).filters).toEqual({
      path_hints: ["city-break", "lake-weekend"]
    });

    await user.click(screen.getByRole("button", { name: "Clear path hints" }));
    expect(lastSearchBody(fetchMock).filters).toBeUndefined();
  });

  it("restores active query and filter state from URL params", async () => {
    renderSearchAt(
      "/search?query=lake%20weekend&query=sunset&from=2026-04-01&to=2026-04-30&person=Inez%20Alvarez&lat=37.7749&lng=-122.4194&radiusKm=12.5&hasFaces=true&pathHint=city-break&pathHint=lake-weekend"
    );

    expect(await screen.findByRole("button", { name: "Remove query lake weekend" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove query sunset" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove from date 2026-04-01" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove to date 2026-04-30" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove person Inez Alvarez" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove location: 37.7749, -122.4194 (12.5 km)" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove has faces filter with faces" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove path hint city-break" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove path hint lake-weekend" })).toBeInTheDocument();
    expect(searchCalls(fetchMock)).toHaveLength(0);
  });

  it("drops malformed URL params and keeps only deterministic valid filter state", async () => {
    renderSearchAt(
      "/search?query=%20%20&from=2026-04-99&to=bad-date&person=%20&lat=999&lng=nope&radiusKm=0&hasFaces=maybe&pathHint=&pathHint=lake-weekend"
    );

    expect(await screen.findByRole("button", { name: "Remove path hint lake-weekend" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove has faces filter with faces" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove has faces filter without faces" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove from date/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove to date/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove location/i })).not.toBeInTheDocument();
    expect(searchCalls(fetchMock)).toHaveLength(0);
    expect(screen.getByTestId("search-location-probe")).toHaveTextContent("?pathHint=lake-weekend");
  });

  it("writes active state back to URL deterministically when query and facet filters change", async () => {
    const user = userEvent.setup();
    renderSearchAt("/search");

    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "harbor");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.click(screen.getByRole("button", { name: "With faces (0)" }));

    expect(screen.getByTestId("search-location-probe")).toHaveTextContent(
      "?query=harbor&hasFaces=true"
    );
  });

  it("restores URL state without auto-requesting search on load", async () => {
    fetchMock.mockImplementation(async (input: string) => {
      if (input === PEOPLE_ENDPOINT) {
        return {
          ok: true,
          json: async () => PEOPLE_FIXTURE
        } as Response;
      }

      throw new TypeError("Failed to fetch");
    });

    renderSearchAt("/search?query=lake&from=2026-04-01&hasFaces=true");

    expect(await screen.findByRole("button", { name: "Remove query lake" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove from date 2026-04-01" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove has faces filter with faces" })
    ).toBeInTheDocument();
    expect(searchCalls(fetchMock)).toHaveLength(0);
    expect(screen.queryByRole("heading", { name: "Could not load Search" })).not.toBeInTheDocument();
  });
});
