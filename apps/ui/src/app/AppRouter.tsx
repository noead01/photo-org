import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useNavigate,
  useLocation
} from "react-router-dom";
import { useState } from "react";
import { AppShell } from "./AppShell";
import {
  findPrimaryRoute,
  PRIMARY_ROUTE_DEFINITIONS,
  type PrimaryRouteDefinition
} from "../routes/routeDefinitions";
import { PrimaryRoutePage } from "../pages/PrimaryRoutePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import {
  resolveInitialSessionIdentity,
  type SessionIdentity
} from "../session/sessionIdentity";

interface AppShellLayoutProps {
  sessionIdentity: SessionIdentity | null;
  onSignOut: () => void;
}

function AppShellLayout({ sessionIdentity, onSignOut }: AppShellLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeRoute =
    findPrimaryRoute(location.pathname) ?? PRIMARY_ROUTE_DEFINITIONS[0];

  function handleSignOut() {
    onSignOut();
    navigate("/browse", { replace: true });
  }

  return (
    <AppShell
      activeRoute={activeRoute}
      sessionIdentity={sessionIdentity}
      onSignOut={handleSignOut}
    >
      <Outlet />
    </AppShell>
  );
}

function routePath(route: PrimaryRouteDefinition): string {
  return route.path.replace(/^\//, "");
}

interface AppRouteTreeProps {
  initialSessionIdentity?: SessionIdentity | null;
}

export function AppRouteTree({ initialSessionIdentity }: AppRouteTreeProps = {}) {
  const [sessionIdentity, setSessionIdentity] = useState<SessionIdentity | null>(() => {
    if (initialSessionIdentity !== undefined) {
      return initialSessionIdentity;
    }

    return resolveInitialSessionIdentity();
  });

  return (
    <Routes>
      <Route
        element={
          <AppShellLayout
            sessionIdentity={sessionIdentity}
            onSignOut={() => setSessionIdentity(null)}
          />
        }
      >
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
