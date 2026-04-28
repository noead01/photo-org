import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppRouteTree } from "./AppRouter";
import { PRIMARY_ROUTE_DEFINITIONS } from "../routes/routeDefinitions";
import type { SessionIdentity } from "../session/sessionIdentity";

const TEST_SESSION_IDENTITY: SessionIdentity = {
  userId: "test-operator",
  displayName: "Avery Operator",
  email: "avery.operator@example.com"
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

describe("App shell", () => {
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
    renderAtPath("/browse");

    const header = screen.getByRole("banner");
    const nav = screen.getByRole("navigation", { name: "Primary" });

    await user.click(screen.getByRole("link", { name: "Search" }));

    expect(screen.getByRole("banner")).toBe(header);
    expect(screen.getByRole("navigation", { name: "Primary" })).toBe(nav);
    expect(
      screen.getByRole("heading", {
        name: "Search",
        level: 1
      })
    ).toBeInTheDocument();
  });

  it("renders user identity and exposes keyboard-accessible account actions", async () => {
    const user = userEvent.setup();
    renderAtPath("/browse");

    expect(screen.getByText("Avery Operator")).toBeInTheDocument();
    expect(screen.getByText("avery.operator@example.com")).toBeInTheDocument();

    const accountActions = screen.getByRole("button", { name: "Account actions" });
    accountActions.focus();
    await user.keyboard("{Enter}");

    expect(accountActions).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("shows deterministic fallback when identity context is missing", () => {
    renderAtPath("/browse", null);

    expect(screen.getByText("Session unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Account actions unavailable"
      })
    ).toBeDisabled();
  });

  it("switches to fallback state after sign-out entry point", async () => {
    const user = userEvent.setup();
    renderAtPath("/search");

    await user.click(screen.getByRole("button", { name: "Account actions" }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(screen.getByText("Session unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Account actions unavailable"
      })
    ).toBeDisabled();
    expect(screen.getByRole("heading", { name: "Browse", level: 1 })).toBeInTheDocument();
  });
});
