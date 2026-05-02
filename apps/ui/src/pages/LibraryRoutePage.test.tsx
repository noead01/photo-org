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
});
