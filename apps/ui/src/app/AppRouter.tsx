import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation
} from "react-router-dom";
import { AppShell } from "./AppShell";
import {
  findPrimaryRoute,
  PRIMARY_ROUTE_DEFINITIONS,
  type PrimaryRouteDefinition
} from "../routes/routeDefinitions";
import { PrimaryRoutePage } from "../pages/PrimaryRoutePage";
import { NotFoundPage } from "../pages/NotFoundPage";

function AppShellLayout() {
  const location = useLocation();
  const activeRoute =
    findPrimaryRoute(location.pathname) ?? PRIMARY_ROUTE_DEFINITIONS[0];

  return (
    <AppShell activeRoute={activeRoute}>
      <Outlet />
    </AppShell>
  );
}

function routePath(route: PrimaryRouteDefinition): string {
  return route.path.replace(/^\//, "");
}

export function AppRouteTree() {
  return (
    <Routes>
      <Route element={<AppShellLayout />}>
        <Route path="/" element={<Navigate to="/browse" replace />} />
        {PRIMARY_ROUTE_DEFINITIONS.map((route) => (
          <Route
            key={route.key}
            path={routePath(route)}
            element={<PrimaryRoutePage route={route} />}
          />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <AppRouteTree />
    </BrowserRouter>
  );
}
