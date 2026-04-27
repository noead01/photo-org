import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppRouteTree } from "./AppRouter";
import { PRIMARY_ROUTE_DEFINITIONS } from "../routes/routeDefinitions";

function renderAtPath(path: string) {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <AppRouteTree />
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
});
