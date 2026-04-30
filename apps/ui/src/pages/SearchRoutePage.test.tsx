import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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
  facets: Record<string, unknown>;
}

interface PersonPayload {
  person_id: string;
  display_name: string;
  created_ts: string;
  updated_ts: string;
}

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
        filesize: 1024 + index
      }))
    },
    facets: {}
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
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/search" element={<SearchRoutePage />} />
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
});
