import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { AppRouteTree } from "./AppRouter";
import { PRIMARY_ROUTE_DEFINITIONS } from "../routes/routeDefinitions";
import type { SessionIdentity } from "../session/sessionIdentity";
import { PRIMARY_ROUTE_LOADING_LABELS } from "../pages/PrimaryRoutePage";

const TEST_SESSION_IDENTITY: SessionIdentity = {
  userId: "test-operator",
  displayName: "Avery Operator",
  email: "avery.operator@example.com",
  capabilities: {
    addToAlbum: true,
    export: true
  }
};

function renderAtPath(path: string, sessionIdentity: SessionIdentity | null = TEST_SESSION_IDENTITY) {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <AppRouteTree initialSessionIdentity={sessionIdentity} />
    </MemoryRouter>
  );
}

function QueryParamBumpButton() {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      onClick={() => {
        navigate({
          search: "?demoState=error&panel=secondary"
        });
      }}
    >
      Bump query
    </button>
  );
}

function renderAtPathWithQueryBump(
  path: string,
  sessionIdentity: SessionIdentity | null = TEST_SESSION_IDENTITY
) {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <QueryParamBumpButton />
      <AppRouteTree initialSessionIdentity={sessionIdentity} />
    </MemoryRouter>
  );
}

function expectShellContextText(text: string) {
  const shellContext = document.querySelector(".shell-context");
  expect(shellContext).not.toBeNull();
  expect(shellContext).toHaveTextContent(text);
}

const ROUTES_WITH_PRIMARY_PAGE_FEEDBACK = PRIMARY_ROUTE_DEFINITIONS.filter(
  (route) => route.key !== "library" && route.key !== "labeling"
);

describe("App shell", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(
      () => new Promise<Response>(() => undefined)
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(PRIMARY_ROUTE_DEFINITIONS)(
    "renders shared shell regions for $path",
    ({ path, title }) => {
      renderAtPath(path);

      expect(screen.getByRole("banner")).toBeInTheDocument();
      expect(
        screen.getByRole("navigation", {
          name: "Primary"
        })
      ).toBeInTheDocument();
      expect(screen.getByRole("main")).toBeInTheDocument();
      expect(
        screen.getByRole("heading", {
          name: title,
          level: 1
        })
      ).toBeInTheDocument();
    }
  );

  it("keeps shell regions mounted while navigating between primary routes", async () => {
    const user = userEvent.setup();
    renderAtPath("/library");

    const header = screen.getByRole("banner");
    const nav = screen.getByRole("navigation", { name: "Primary" });

    await user.click(screen.getByRole("link", { name: "Labeling" }));

    expect(screen.getByRole("banner")).toBe(header);
    expect(screen.getByRole("navigation", { name: "Primary" })).toBe(nav);
    expect(
      screen.getByRole("heading", {
        name: "Labeling",
        level: 1
      })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Labeling" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Library" })).not.toHaveAttribute("aria-current");
    expectShellContextText("Labeling");
  });

  it("renders user identity and exposes keyboard-accessible account actions", async () => {
    const user = userEvent.setup();
    renderAtPath("/library");

    expect(screen.getByText("Avery Operator")).toBeInTheDocument();
    expect(screen.getByText("avery.operator@example.com")).toBeInTheDocument();

    const accountActions = screen.getByRole("button", { name: "Account actions" });
    accountActions.focus();
    await user.keyboard("{Enter}");

    expect(accountActions).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("shows deterministic fallback when identity context is missing", () => {
    renderAtPath("/library", null);

    expect(screen.getByText("Session unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Account actions unavailable"
      })
    ).toBeDisabled();
  });

  it("switches to fallback state after sign-out entry point", async () => {
    const user = userEvent.setup();
    renderAtPath("/library");

    await user.click(screen.getByRole("button", { name: "Account actions" }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(screen.getByText("Session unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Account actions unavailable"
      })
    ).toBeDisabled();
    expect(screen.getByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
  });

  it("uses deterministic fallback nav and context for unknown route paths", () => {
    renderAtPath("/unknown-route");

    expect(screen.getByRole("heading", { name: "Page Not Found", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Library" })).toHaveAttribute("aria-current", "page");
    expectShellContextText("Library");
  });

  it.each(ROUTES_WITH_PRIMARY_PAGE_FEEDBACK)(
    "routes $title through shared loading feedback surface",
    ({ key, path }) => {
      renderAtPath(`${path}?demoState=loading`);

      expect(screen.getByRole("status")).toHaveTextContent(PRIMARY_ROUTE_LOADING_LABELS[key]);
      expect(screen.getByRole("banner")).toBeInTheDocument();
      expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    }
  );

  it("transitions from route error to ready on retry for primary-placeholder routes", async () => {
    const user = userEvent.setup();
    renderAtPath("/operations?demoState=error");

    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Could not load Operations",
        level: 2
      })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(screen.getByRole("heading", { name: "Operations", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Operations is ready.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByText("Operations is ready.")).not.toBeInTheDocument();
  });

  it("does not reset feedback state when unrelated query params change", async () => {
    const user = userEvent.setup();
    renderAtPathWithQueryBump("/operations?demoState=error&panel=primary");

    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(screen.getByText("Operations is ready.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Bump query" }));

    expect(screen.getByRole("heading", { name: "Operations", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.getByText("Operations is ready.")).toBeInTheDocument();
  });

  it("renders only Library as the discovery workflow route", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ hits: { total: 0, cursor: null, items: [] }, facets: {} })
    } as Response);

    renderAtPath("/library");

    expect(await screen.findByRole("heading", { name: "Library", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Library" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: "Browse" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Search" })).not.toBeInTheDocument();
  });

  it("renders people-management controls on the /labeling route", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => []
    } as Response);

    renderAtPath("/labeling");

    expect(await screen.findByRole("heading", { name: "Labeling", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Create person display name" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create person" })).toBeInTheDocument();
  });
});
