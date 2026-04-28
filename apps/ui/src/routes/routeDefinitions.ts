export type PrimaryRouteKey =
  | "browse"
  | "search"
  | "labeling"
  | "suggestions"
  | "operations";

export interface ShellHandoffExpectations {
  loading: string;
  error: string;
  transition: string;
}

export interface PrimaryRouteDefinition {
  key: PrimaryRouteKey;
  path: string;
  navLabel: string;
  title: string;
  description: string;
  handoff: ShellHandoffExpectations;
}

export interface NavigationState {
  activeRoute: PrimaryRouteDefinition;
  pageContext: string;
  usesFallback: boolean;
}

const baseHandoffExpectation: ShellHandoffExpectations = {
  loading:
    "Keep header and navigation visible while content shows a route-local loading state.",
  error:
    "Keep header and navigation visible while content shows a route-local recoverable error state.",
  transition:
    "Route transitions keep shell regions mounted; only page content swaps."
};

export const PRIMARY_ROUTE_DEFINITIONS: PrimaryRouteDefinition[] = [
  {
    key: "browse",
    path: "/browse",
    navLabel: "Browse",
    title: "Browse",
    description: "Browse workflow surface placeholder.",
    handoff: baseHandoffExpectation
  },
  {
    key: "search",
    path: "/search",
    navLabel: "Search",
    title: "Search",
    description: "Search workflow surface placeholder.",
    handoff: baseHandoffExpectation
  },
  {
    key: "labeling",
    path: "/labeling",
    navLabel: "Labeling",
    title: "Labeling",
    description: "Face-labeling workflow surface placeholder.",
    handoff: baseHandoffExpectation
  },
  {
    key: "suggestions",
    path: "/suggestions",
    navLabel: "Suggestions",
    title: "Suggestions",
    description: "Recognition suggestions workflow surface placeholder.",
    handoff: baseHandoffExpectation
  },
  {
    key: "operations",
    path: "/operations",
    navLabel: "Operations",
    title: "Operations",
    description: "Operational admin workflow surface placeholder.",
    handoff: baseHandoffExpectation
  }
];

export const FALLBACK_PRIMARY_ROUTE = PRIMARY_ROUTE_DEFINITIONS[0];

function normalizePathname(pathname: string): string {
  const withLeadingSlash = pathname.startsWith("/") ? pathname : `/${pathname}`;

  if (withLeadingSlash === "/") {
    return withLeadingSlash;
  }

  return withLeadingSlash.replace(/\/+$/, "");
}

function routeOwnsPathname(route: PrimaryRouteDefinition, pathname: string): boolean {
  return pathname === route.path || pathname.startsWith(`${route.path}/`);
}

export function findPrimaryRoute(pathname: string): PrimaryRouteDefinition | undefined {
  const normalizedPathname = normalizePathname(pathname);

  return PRIMARY_ROUTE_DEFINITIONS.find((route) =>
    routeOwnsPathname(route, normalizedPathname)
  );
}

export function resolveNavigationState(pathname: string): NavigationState {
  const matchedRoute = findPrimaryRoute(pathname);
  const activeRoute = matchedRoute ?? FALLBACK_PRIMARY_ROUTE;

  return {
    activeRoute,
    pageContext: activeRoute.title,
    usesFallback: matchedRoute === undefined
  };
}
