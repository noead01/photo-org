import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { PeopleManagementRoutePage } from "./PeopleManagementRoutePage";

const PEOPLE_ENDPOINT = "/api/v1/people";

type PersonPayload = {
  person_id: string;
  display_name: string;
  created_ts: string;
  updated_ts: string;
};

function createPerson(personId: string, displayName: string): PersonPayload {
  return {
    person_id: personId,
    display_name: displayName,
    created_ts: "2026-04-20T12:00:00Z",
    updated_ts: "2026-04-20T12:00:00Z"
  };
}

function renderLabelingPage() {
  return render(
    <MemoryRouter
      initialEntries={["/labeling"]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/labeling" element={<PeopleManagementRoutePage />} />
      </Routes>
    </MemoryRouter>
  );
}

function buildPeopleFetch(
  peopleSeed: PersonPayload[],
  options: {
    inUseIds?: string[];
    failFirstListRequest?: number;
  } = {}
) {
  const people = [...peopleSeed];
  const inUseIds = new Set(options.inUseIds ?? []);
  let remainingListFailures = options.failFirstListRequest ?? 0;

  return vi.fn(async (input: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";

    if (input === PEOPLE_ENDPOINT && method === "GET") {
      if (remainingListFailures > 0) {
        remainingListFailures -= 1;
        return { ok: false, status: 503 } as Response;
      }

      return {
        ok: true,
        json: async () => [...people]
      } as Response;
    }

    if (input === PEOPLE_ENDPOINT && method === "POST") {
      const payload = JSON.parse(String(init?.body)) as { display_name: string };
      const trimmed = payload.display_name.trim();
      const created = createPerson(`person-${people.length + 1}`, trimmed);
      people.push(created);

      return {
        ok: true,
        status: 201,
        json: async () => created
      } as Response;
    }

    if (input.startsWith(`${PEOPLE_ENDPOINT}/`) && method === "PATCH") {
      const personId = input.replace(`${PEOPLE_ENDPOINT}/`, "");
      const person = people.find((candidate) => candidate.person_id === personId);
      if (!person) {
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: "Person not found" })
        } as Response;
      }

      const payload = JSON.parse(String(init?.body)) as { display_name: string };
      person.display_name = payload.display_name.trim();
      person.updated_ts = "2026-04-21T12:00:00Z";

      return {
        ok: true,
        json: async () => ({ ...person })
      } as Response;
    }

    if (input.startsWith(`${PEOPLE_ENDPOINT}/`) && method === "DELETE") {
      const personId = input.replace(`${PEOPLE_ENDPOINT}/`, "");
      const index = people.findIndex((candidate) => candidate.person_id === personId);
      if (index < 0) {
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: "Person not found" })
        } as Response;
      }

      if (inUseIds.has(personId)) {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: "Person is referenced by face or label data" })
        } as Response;
      }

      people.splice(index, 1);
      return {
        ok: true,
        status: 204
      } as Response;
    }

    throw new Error(`Unexpected request: ${method} ${input}`);
  });
}

describe("PeopleManagementRoutePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads and renders deterministic people ordering", async () => {
    const fetchMock = buildPeopleFetch([
      createPerson("person-2", "Zoe Carter"),
      createPerson("person-1", "Ana Gomez"),
      createPerson("person-3", "Ana Carter")
    ]);
    vi.stubGlobal("fetch", fetchMock);

    renderLabelingPage();

    expect(await screen.findByRole("heading", { name: "Labeling", level: 1 })).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "People records" });
    const labels = within(list)
      .getAllByRole("heading", { level: 2 })
      .map((item) => item.textContent);

    expect(labels).toEqual(["Ana Carter", "Ana Gomez", "Zoe Carter"]);
  });

  it("shows a deterministic empty state", async () => {
    const fetchMock = buildPeopleFetch([]);
    vi.stubGlobal("fetch", fetchMock);

    renderLabelingPage();

    expect(await screen.findByText("No people yet. Create the first person to start labeling.")).toBeInTheDocument();
  });

  it("shows load error and retries successfully", async () => {
    const user = userEvent.setup();
    const fetchMock = buildPeopleFetch(
      [createPerson("person-1", "Ana Gomez")],
      { failFirstListRequest: 1 }
    );
    vi.stubGlobal("fetch", fetchMock);

    renderLabelingPage();

    expect(await screen.findByRole("heading", { name: "Could not load people directory", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("People request failed (503)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("Ana Gomez")).toBeInTheDocument();
  });

  it("creates and renames people with inline validation", async () => {
    const user = userEvent.setup();
    const fetchMock = buildPeopleFetch([createPerson("person-1", "Ana Gomez")]);
    vi.stubGlobal("fetch", fetchMock);

    renderLabelingPage();

    expect(await screen.findByText("Ana Gomez")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Create person display name"), "  ");
    await user.click(screen.getByRole("button", { name: "Create person" }));
    expect(screen.getByText("Display name is required.")).toBeInTheDocument();

    const createInput = screen.getByLabelText("Create person display name");
    await user.clear(createInput);
    await user.type(createInput, "Inez Alvarez");
    await user.click(screen.getByRole("button", { name: "Create person" }));

    expect(await screen.findByText("Inez Alvarez")).toBeInTheDocument();

    const renameInput = screen.getByLabelText("Display name for person Ana Gomez");
    await user.clear(renameInput);
    await user.type(renameInput, "Ana Morales");
    await user.click(screen.getByRole("button", { name: "Rename person Ana Gomez" }));

    expect(await screen.findByText("Ana Morales")).toBeInTheDocument();
  });

  it("surfaces delete conflicts and removes deletable people", async () => {
    const user = userEvent.setup();
    const fetchMock = buildPeopleFetch(
      [
        createPerson("person-1", "In Use Person"),
        createPerson("person-2", "Free Person")
      ],
      { inUseIds: ["person-1"] }
    );
    vi.stubGlobal("fetch", fetchMock);

    renderLabelingPage();

    expect(await screen.findByText("In Use Person")).toBeInTheDocument();
    expect(screen.getByText("Free Person")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete person In Use Person" }));
    expect(await screen.findByText("Person is referenced by face or label data")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete person Free Person" }));
    expect(screen.queryByText("Free Person")).not.toBeInTheDocument();
    expect(screen.getByText("In Use Person")).toBeInTheDocument();
  });
});
