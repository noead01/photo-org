import {
  PRIMARY_ROUTE_DEFINITIONS,
  resolveNavigationState
} from "./routeDefinitions";

describe("Shell handoff expectations", () => {
  it("defines loading and error behavior for each primary route", () => {
    for (const route of PRIMARY_ROUTE_DEFINITIONS) {
      expect(route.handoff.loading).not.toHaveLength(0);
      expect(route.handoff.error).not.toHaveLength(0);
      expect(route.handoff.transition).not.toHaveLength(0);
    }
  });
});

describe("Navigation state", () => {
  it("maps /library to the library primary route and uses it as fallback context", () => {
    const libraryState = resolveNavigationState("/library");

    expect(libraryState.activeRoute.key).toBe("library");
    expect(libraryState.pageContext).toBe("Library");
    expect(libraryState.usesFallback).toBe(false);

    const unknownState = resolveNavigationState("/not-a-real-route");
    expect(unknownState.activeRoute.key).toBe("library");
    expect(unknownState.pageContext).toBe("Library");
    expect(unknownState.usesFallback).toBe(true);
  });

  it("maps an exact primary route pathname to matching nav and context", () => {
    const navigationState = resolveNavigationState("/search");

    expect(navigationState.activeRoute.key).toBe("search");
    expect(navigationState.pageContext).toBe("Search");
    expect(navigationState.usesFallback).toBe(false);
  });

  it("maps nested route pathnames to the owning primary nav destination", () => {
    const navigationState = resolveNavigationState("/operations/activity/123");

    expect(navigationState.activeRoute.key).toBe("operations");
    expect(navigationState.pageContext).toBe("Operations");
    expect(navigationState.usesFallback).toBe(false);
  });

  it("falls back deterministically when pathname is unknown", () => {
    const navigationState = resolveNavigationState("/not-a-real-route");

    expect(navigationState.activeRoute.key).toBe("browse");
    expect(navigationState.pageContext).toBe("Browse");
    expect(navigationState.usesFallback).toBe(true);
  });
});
